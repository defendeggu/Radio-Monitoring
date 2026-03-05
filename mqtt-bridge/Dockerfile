FROM python:3.11-slim

RUN pip install --no-cache-dir paho-mqtt==2.1.0

WORKDIR /app
COPY mqtt_to_logstash_bridge.py .

CMD ["python", "mqtt_to_logstash_bridge.py"]
