#!/usr/bin/env python3
import socket
import struct
import os
import logging
import threading
import time

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MQTTSNServer:
    def __init__(self):
        self.host = '0.0.0.0'
        self.port = 1885
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Configurações do Asterisk AMI
        self.asterisk_host = os.getenv('ASTERISK_HOST', 'asterisk')
        self.asterisk_port = int(os.getenv('ASTERISK_PORT', '5038'))
        self.ami_user = os.getenv('ASTERISK_AMI_USER', 'admin')
        self.ami_secret = os.getenv('ASTERISK_AMI_SECRET', 'senha123')

        # MODIFICAÇÃO: Apenas ramal 2000 para alertas
        self.alert_phone = '2000'  # Fixado para ramal 2000

        # Limite de temperatura
        self.temp_threshold = float(os.getenv('TEMP_THRESHOLD', '80'))

        logger.info(f"Servidor MQTT-SN iniciado em {self.host}:{self.port}")
        logger.info(f"Limite de temperatura: {self.temp_threshold}°C")
        logger.info(f"📞 Ramal de alerta configurado: {self.alert_phone}")

    def parse_mqttsn_message(self, data):
        if len(data) < 2:
            return None

        msg_type = data[1]

        if msg_type == 0x0C and len(data) >= 7:
            topic_id = struct.unpack('>H', data[4:6])[0]
            payload = data[7:].decode('utf-8', errors='ignore').strip().rstrip('\x00')
            return {'type': 'PUBLISH', 'topic_id': topic_id, 'payload': payload}

        if msg_type == 0x04:
            return {'type': 'CONNECT'}

        return None

    def send_connack(self, addr):
        self.socket.sendto(bytearray([3, 0x05, 0x00]), addr)
        logger.info(f"CONNACK enviado para {addr}")

    def send_puback(self, addr, topic_id):
        msg = bytearray([7, 0x0D, 0x00, 0x00])
        msg.extend(struct.pack('>H', topic_id))
        msg.append(0x00)
        self.socket.sendto(msg, addr)
        logger.info(f"PUBACK enviado para {addr}")

    def process_temperature(self, temp_str):
        try:
            temp_clean = ''.join(c for c in temp_str if c.isdigit() or c == '.')
            if not temp_clean:
                raise ValueError("valor vazio")

            temperature = float(temp_clean)
            logger.info(f"🌡️  Temperatura recebida: {temperature}°C")

            if temperature > self.temp_threshold:
                logger.warning(f"🚨 ALERTA CRÍTICO! {temperature}°C acima de {self.temp_threshold}°C")
                
                # Salvar alerta em arquivo
                self.save_alert_log(temperature)

                # Enviar alerta telefônico APENAS para ramal 2000
                logger.info(f"📞 Iniciando chamada de alerta para ramal {self.alert_phone}")
                threading.Thread(target=self.send_asterisk_alert, args=(temperature, self.alert_phone)).start()
            else:
                logger.info(f"✅ Temperatura {temperature}°C está normal (abaixo de {self.temp_threshold}°C)")

        except Exception as e:
            logger.error(f"❌ Erro ao processar temperatura '{temp_str}': {e}")

    def save_alert_log(self, temperature):
        """Salva alerta de temperatura em arquivo de log"""
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"{timestamp}: 🚨 ALERTA CRÍTICO - Temperatura {temperature}°C detectada no ramal 2000!\n"

            with open("/tmp/alertas_temperatura.log", "a") as f:
                f.write(log_message)

            logger.info(f"📝 Alerta gravado em log: {temperature}°C")
        except Exception as e:
            logger.error(f"❌ Erro ao salvar log: {e}")

    def send_ami_command(self, ami_socket, action_data):
        """Envia comando AMI via socket raw"""
        command = ""
        for key, value in action_data.items():
            command += f"{key}: {value}\r\n"
        command += "\r\n"

        ami_socket.send(command.encode('utf-8'))

        # Lê resposta
        response = ""
        while True:
            data = ami_socket.recv(1024).decode('utf-8')
            response += data
            if "\r\n\r\n" in response:
                break

        return response

    def send_asterisk_alert(self, temperature, phone):
        logger.info(f"🚨 Disparando alerta SIP para ramal {phone}: {temperature}°C")
        ami_socket = None

        try:
            # Conecta ao AMI via socket raw
            ami_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ami_socket.settimeout(10)
            ami_socket.connect((self.asterisk_host, self.asterisk_port))

            # Lê banner de boas-vindas
            banner = ami_socket.recv(1024).decode('utf-8')
            logger.debug(f"AMI Banner: {banner.strip()}")

            # Login
            login_response = self.send_ami_command(ami_socket, {
                'Action': 'Login',
                'Username': self.ami_user,
                'Secret': self.ami_secret
            })

            if "Success" not in login_response:
                raise Exception(f"Falha no login AMI: {login_response}")

            logger.debug("✅ Login AMI realizado com sucesso")

            # COMANDO ORIGINATE OTIMIZADO PARA LINPHONE/SIP
            originate_response = self.send_ami_command(ami_socket, {
                'Action': 'Originate',
                'Channel': f'SIP/{phone}',                    # Canal SIP direto
                'Context': 'temperatura-alert',               # Contexto de alerta
                'Exten': 's',                                # Extensão de entrada
                'Priority': '1',                             # Prioridade 1
                'CallerID': f'Sistema Temp <{phone}>',       # Identificador da chamada
                'Variable': f'TEMPERATURA={int(temperature)}', # Variável com temperatura
                'Timeout': '30000',                          # Timeout de 30 segundos
                'Async': 'true'                              # Execução assíncrona
            })

            if "Response: Success" in originate_response:
                logger.info(f"✅ Chamada SIP para ramal {phone}: Comando enviado com sucesso")
                logger.info(f"📞 Linphone no ramal {phone} deve receber chamada em instantes")
            elif "Event: FullyBooted" in originate_response:
                logger.info(f"✅ Sistema processando chamada para ramal {phone}")
            else:
                logger.warning(f"⚠️  Resposta inesperada para ramal {phone}: {originate_response.strip()}")

            # Logout
            self.send_ami_command(ami_socket, {'Action': 'Logoff'})
            logger.debug("🔓 Logout AMI realizado")

        except Exception as e:
            logger.error(f"❌ Erro AMI para ramal {phone}: {e}")
        finally:
            if ami_socket:
                try:
                    ami_socket.close()
                except:
                    pass

    def run(self):
        self.socket.bind((self.host, self.port))
        logger.info("🚀 Servidor MQTT-SN aguardando mensagens...")
        logger.info(f"📡 Monitorando temperatura com limite de {self.temp_threshold}°C")
        logger.info(f"📞 Alertas serão enviados para o ramal SIP/{self.alert_phone}")

        while True:
            try:
                data, addr = self.socket.recvfrom(1024)
                logger.info(f"📨 Mensagem recebida de {addr}: {data.hex()}")

                msg = self.parse_mqttsn_message(data)
                if not msg:
                    continue

                if msg['type'] == 'CONNECT':
                    self.send_connack(addr)
                    logger.info(f"🤝 Cliente {addr} conectado")
                elif msg['type'] == 'PUBLISH':
                    self.send_puback(addr, msg['topic_id'])
                    if msg['topic_id'] == 1:  # Topic ID 1 = temperatura
                        self.process_temperature(msg['payload'])

            except Exception as e:
                logger.error(f"❌ Erro no loop principal: {e}")

if __name__ == "__main__":
    logger.info("🌡️  Sistema de Alerta de Temperatura - Ramal 2000 via SIP")
    logger.info("=" * 60)
    MQTTSNServer().run()
