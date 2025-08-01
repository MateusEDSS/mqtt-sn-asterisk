#!/usr/bin/env python3
"""
Cliente MQTT-SN simples para testar o sistema
Envia temperaturas para o servidor
"""
import socket
import struct
import time
import sys

class MQTTSNClient:
    def __init__(self, server_host='localhost', server_port=1885):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(5)

    def connect(self):
        """Conectar ao servidor MQTT-SN"""
        # CONNECT message: Length(1) + MsgType(1) + Flags(1) + ProtocolId(1) + Duration(2) + ClientId
        client_id = b'temp_sensor'
        connect_msg = bytearray([
            4 + len(client_id),  # Length
            0x04,               # CONNECT
            0x00,               # Flags
            0x01,               # Protocol ID
        ])
        connect_msg.extend(struct.pack('>H', 30))  # Duration (30 seconds)
        connect_msg.extend(client_id)
        
        print(f"Enviando CONNECT para {self.server_host}:{self.server_port}")
        self.socket.sendto(connect_msg, (self.server_host, self.server_port))
        
        # Aguardar CONNACK
        try:
            response, addr = self.socket.recvfrom(1024)
            if len(response) >= 3 and response[1] == 0x05:  # CONNACK
                print("✓ Conectado ao servidor MQTT-SN")
                return True
        except socket.timeout:
            print("✗ Timeout ao conectar")
            return False

    def publish_temperature(self, temperature):
        """Publicar temperatura"""
        # PUBLISH message: Length + MsgType + Flags + TopicId + MsgId + Data
        temp_str = str(temperature)
        topic_id = 1  # ID do tópico temperature
        
        publish_msg = bytearray([
            7 + len(temp_str),   # Length
            0x0C,               # PUBLISH
            0x00,               # Flags
            0x00,               # TopicIdType
        ])
        publish_msg.extend(struct.pack('>H', topic_id))  # Topic ID
        publish_msg.extend(struct.pack('>H', 1))         # Message ID
        publish_msg.extend(temp_str.encode('utf-8'))     # Payload
        
        print(f"Enviando temperatura: {temperature}°C")
        self.socket.sendto(publish_msg, (self.server_host, self.server_port))
        
        # Aguardar PUBACK
        try:
            response, addr = self.socket.recvfrom(1024)
            if len(response) >= 1 and response[1] == 0x0D:  # PUBACK
                print("✓ Temperatura enviada com sucesso")
                return True
        except socket.timeout:
            print("✗ Timeout ao publicar")
            return False

    def close(self):
        """Fechar conexão"""
        self.socket.close()

def main():
    client = MQTTSNClient()
    
    if not client.connect():
        return
    
    print("\n=== TESTE DE TEMPERATURAS ===")
    print("Enviando diferentes temperaturas...")
    print("(Alerta será disparado para temperaturas > 80°C)\n")
    
    # Teste com diferentes temperaturas
    temperatures = [45, 70, 85]
    
    for temp in temperatures:
        print(f"\n--- Enviando {temp}°C ---")
        client.publish_temperature(temp)
        
        if temp > 80:
            print("🚨 Esta temperatura deve disparar um alerta!")
            print("Aguarde alguns segundos para o Asterisk processar...")
            time.sleep(5)
        else:
            print("ℹ️  Temperatura normal")
            time.sleep(2)
    
    # Modo interativo
    print("\n=== MODO INTERATIVO ===")
    print("Digite temperaturas para enviar (digite 'quit' para sair):")
    
    while True:
        try:
            user_input = input("\nTemperatura: ").strip()
            if user_input.lower() == 'quit':
                break
            
            temp = float(user_input)
            client.publish_temperature(temp)
            
            if temp > 80:
                print("🚨 Alerta será disparado!")
                time.sleep(3)
                
        except ValueError:
            print("Por favor, digite um número válido ou 'quit'")
        except KeyboardInterrupt:
            break
    
    client.close()
    print("\nCliente desconectado.")

if __name__ == "__main__":
    main()
