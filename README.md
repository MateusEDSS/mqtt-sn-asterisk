## Ambiente MQTT-SN + Asterisk para Simulação de Alertas Telefônicos

Este projeto demonstra a integração entre MQTT-SN (protocolo de mensagens para IoT) e Asterisk (PBX IP) para disparar chamadas de alerta telefônico quando sensores enviam temperaturas acima de um limite configurado.


## Funcionalidades

    Recebe dados de temperatura via MQTT-SN (UDP).

    Analisa valores e dispara alerta para Asterisk se ultrapassar o limite.

    Asterisk simula uma chamada para um número SIP previamente configurado.

    Tudo empacotado em containers Docker para portabilidade.

##  Pré-requisitos
```
docker
docker compose
python3
```
## Estrutura de diretórios

```
.
└── mqtt-sn-asterisk         
    ├── asterisk-config        
    │   ├── extensions.conf
    │   ├── manager.conf
    │   └── sip.conf
    ├── docker-compose.yaml
    ├── Dockerfile.asterisk
    ├── Dockerfile.mqttsn
    ├── mqtt_sn_client_test.py
    ├── mqtt_sn_server.py
    └── requirements.txt
```

▶️ Como executar o ambiente

Clone do repositório
```
git clone https://github.com/seuusuario/mqtt-sn-asterisk.git
cd mqtt-sn-asterisk
```
Build e subir os containers
```
docker compose build
docker compose up -d
```

Asterisk: Servidor SIP + AMI na porta 5060.
Servidor MQTT-SN: Escuta na porta 1885/udp.


🧪 Testando o sistema
Abra uma segundo terminal e execute o script python
```
python3 mqtt_sn_client_test.py
```
Esse script irá:

    Conectar ao servidor MQTT-SN.

    Enviar várias temperaturas (25°C, 45°C, 70°C, 85°C, 95°C, 30°C).

    Disparar alertas para o Asterisk quando a temperatura ultrapassar 80°C.

🔍 Validando
No log do container mqtt-sn-server, você verá mensagens como:
```
mqtt-sn-server  | 2025-07-29 03:29:23,747 - INFO - 🚨 SIMULANDO CHAMADA DE ALERTA:
mqtt-sn-server  | 2025-07-29 03:29:23,747 - INFO - 📞 Discando para 1000...
mqtt-sn-server  | 2025-07-29 03:29:23,747 - INFO - 🔊 'ALERTA! Temperatura de 85.0 graus Celsius detectada!'
mqtt-sn-server  | 2025-07-29 03:29:23,747 - INFO - 🔊 'A temperatura atual é 85.0 graus, acima do limite de 80.0 graus.'
mqtt-sn-server  | 2025-07-29 03:29:23,747 - INFO - 📞 Chamada encerrada.
mqtt-sn-server  | 2025-07-29 03:29:23,747 - INFO - 🚨==================================================
mqtt-sn-server  | 2025-07-29 03:29:23,747 - INFO - Tópico 1: 85
mqtt-sn-server  | 2025-07-29 03:29:28,747 - INFO - Mensagem recebida de ('172.18.0.1', 36503): 090c0000000100013935
mqtt-sn-server  | 2025-07-29 03:29:28,747 - INFO - PUBACK enviado para ('172.18.0.1', 36503)
```
