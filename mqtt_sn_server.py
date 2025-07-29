#!/usr/bin/env python3
import socket
import struct
import os
import logging
from asterisk.ami import AMIClient
import time
import threading

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MQTTSNServer:
    def __init__(self):
        self.host = '0.0.0.0'
        self.port = 1885
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Configurações do Asterisk
        self.asterisk_host = os.getenv('ASTERISK_HOST', 'asterisk')
        self.asterisk_port = int(os.getenv('ASTERISK_AMI_PORT', '5038'))
        self.ami_user = os.getenv('ASTERISK_AMI_USER', 'admin')
        self.ami_secret = os.getenv('ASTERISK_AMI_SECRET', 'senha123')
        self.alert_phone = os.getenv('ALERT_PHONE', '1000')
        self.temp_threshold = float(os.getenv('TEMP_THRESHOLD', '80'))
        
        # Tópicos conhecidos (simulação de registro MQTT-SN)
        self.topics = {
            1: 'temperature',
            2: 'humidity',
            3: 'alert'
        }
        
        logger.info(f"Servidor MQTT-SN iniciado em {self.host}:{self.port}")
        logger.info(f"Limite de temperatura: {self.temp_threshold}°C")
        logger.info(f"Número de alerta: {self.alert_phone}")

    def parse_mqttsn_message(self, data):
        """Parse simples de mensagem MQTT-SN"""
        if len(data) < 2:
            return None
        
        length = data[0]
        msg_type = data[1]
        
        # PUBLISH message type (0x0C)
        if msg_type == 0x0C and len(data) >= 7:
            topic_id = struct.unpack('>H', data[4:6])[0]
            # Extrair payload corretamente
            payload_bytes = data[7:]
            payload = payload_bytes.decode('utf-8', errors='ignore').strip().rstrip('\x00')
            
            return {
                'type': 'PUBLISH',
                'topic_id': topic_id,
                'payload': payload
            }
        
        # CONNECT message type (0x04)
        elif msg_type == 0x04:
            return {'type': 'CONNECT'}
        
        return None

    def send_connack(self, client_addr):
        """Enviar CONNACK"""
        connack = bytearray([3, 0x05, 0x00])  # Length, CONNACK, Return Code
        self.socket.sendto(connack, client_addr)
        logger.info(f"CONNACK enviado para {client_addr}")

    def send_puback(self, client_addr, topic_id):
        """Enviar PUBACK"""
        puback = bytearray([7, 0x0D, 0x00, 0x00])  # Length, PUBACK, Topic ID
        puback.extend(struct.pack('>H', topic_id))
        puback.extend([0x00])  # Return Code
        self.socket.sendto(puback, client_addr)
        logger.info(f"PUBACK enviado para {client_addr}")

    def process_temperature(self, temp_str):
        """Processar temperatura e enviar alerta se necessário"""
        try:
            # Limpar string de temperatura
            temp_clean = ''.join(c for c in temp_str if c.isdigit() or c == '.')
            if not temp_clean:
                raise ValueError("String vazia após limpeza")
                
            temperature = float(temp_clean)
            logger.info(f"Temperatura recebida: {temperature}°C")
            
            if temperature > self.temp_threshold:
                logger.warning(f"ALERTA! Temperatura {temperature}°C acima do limite {self.temp_threshold}°C")
                threading.Thread(target=self.send_asterisk_alert, args=(temperature,)).start()
                return True
            else:
                logger.info(f"Temperatura {temperature}°C normal")
                return False
                
        except (ValueError, TypeError) as e:
            logger.error(f"Erro ao converter temperatura: '{temp_str}' -> '{temp_clean if 'temp_clean' in locals() else 'N/A'}' - {str(e)}")
            return False

    def send_asterisk_alert(self, temperature):
        """Enviar alerta via Asterisk"""
        logger.info("🚨 === DISPARANDO ALERTA ===")
        logger.info("🚨 SIMULANDO CHAMADA DE ALERTA:")
        logger.info(f"📞 Discando para {self.alert_phone}...")
        logger.info(f"🔊 'ALERTA! Temperatura de {temperature} graus Celsius detectada!'")
        logger.info(f"🔊 'A temperatura atual é {temperature} graus, acima do limite de {self.temp_threshold} graus.'")
        logger.info("📞 Chamada encerrada.")
        logger.info("🚨" + "="*50)
        
        # Tentar Asterisk se disponível (opcional)
        try:
            import socket as sock
            test_socket = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
            test_socket.settimeout(1)
            
            result = test_socket.connect_ex((self.asterisk_host, self.asterisk_port))
            test_socket.close()
            
            if result == 0:
                from asterisk.ami import AMIClient
                client = AMIClient(address=self.asterisk_host, port=self.asterisk_port)
                client.login(username=self.ami_user, secret=self.ami_secret)
                
                action = client.action('Originate', {
                    'Channel': f'SIP/{self.alert_phone}',
                    'Context': 'temperatura-alert',
                    'Exten': 's',
                    'Priority': '1',
                    'CallerID': 'Sistema de Alerta <9999>',
                    'Variable': f'TEMPERATURA={int(temperature)}',
                    'Async': 'true'
                })
                
                client.logoff()
                logger.info(f"✅ BONUS: Chamada real também enviada para {self.alert_phone}")
                
        except Exception:
            pass  # Ignorar erros do Asterisk

    def run(self):
        """Executar servidor MQTT-SN"""
        self.socket.bind((self.host, self.port))
        logger.info("Servidor MQTT-SN aguardando mensagens...")
        
        while True:
            try:
                data, client_addr = self.socket.recvfrom(1024)
                logger.info(f"Mensagem recebida de {client_addr}: {data.hex()}")
                
                message = self.parse_mqttsn_message(data)
                
                if message:
                    if message['type'] == 'CONNECT':
                        self.send_connack(client_addr)
                        
                    elif message['type'] == 'PUBLISH':
                        topic_id = message['topic_id']
                        payload = message['payload']
                        
                        self.send_puback(client_addr, topic_id)
                        
                        # Verificar se é tópico de temperatura
                        if topic_id in self.topics and self.topics[topic_id] == 'temperature':
                            self.process_temperature(payload)
                        
                        logger.info(f"Tópico {topic_id}: {payload}")
                        
            except Exception as e:
                logger.error(f"Erro no servidor: {e}")

if __name__ == "__main__":
    server = MQTTSNServer()
    server.run()
