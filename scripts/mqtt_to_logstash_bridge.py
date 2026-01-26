#!/usr/bin/env python3
"""
MQTT to Logstash HTTP Bridge

Subscribes to Intercept MQTT topics and forwards messages to Logstash HTTP input.
This bridges the gap between Mosquitto MQTT broker and Logstash.

Usage:
    python3 mqtt_to_logstash_bridge.py

Environment Variables:
    MQTT_HOST       - MQTT broker host (default: localhost)
    MQTT_PORT       - MQTT broker port (default: 1883)
    MQTT_TOPIC      - MQTT topic pattern (default: intercept/#)
    LOGSTASH_URL    - Logstash HTTP endpoint (default: http://localhost:9605)
"""

import os
import sys
import json
import time
import logging
import signal
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: paho-mqtt not installed. Run: pip install paho-mqtt")
    sys.exit(1)

# Configuration from environment
MQTT_HOST = os.environ.get('MQTT_HOST', 'localhost')
MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
MQTT_TOPIC = os.environ.get('MQTT_TOPIC', 'intercept/#')
LOGSTASH_URL = os.environ.get('LOGSTASH_URL', 'http://localhost:9605')

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Statistics
stats = {
    'messages_received': 0,
    'messages_forwarded': 0,
    'errors': 0,
    'start_time': None
}

running = True


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    global running
    logger.info("Shutdown signal received, stopping...")
    running = False


def forward_to_logstash(payload: dict) -> bool:
    """Forward a message to Logstash HTTP endpoint."""
    try:
        data = json.dumps(payload).encode('utf-8')
        req = Request(LOGSTASH_URL, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')

        with urlopen(req, timeout=5) as response:
            if response.status == 200:
                return True
            else:
                logger.warning(f"Logstash returned status {response.status}")
                return False
    except HTTPError as e:
        logger.error(f"HTTP error forwarding to Logstash: {e.code} - {e.reason}")
        return False
    except URLError as e:
        logger.error(f"URL error forwarding to Logstash: {e.reason}")
        return False
    except Exception as e:
        logger.error(f"Error forwarding to Logstash: {e}")
        return False


def on_connect(client, userdata, flags, rc, properties=None):
    """Callback when connected to MQTT broker."""
    if rc == 0:
        logger.info(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        logger.info(f"Subscribed to topic: {MQTT_TOPIC}")
    else:
        logger.error(f"Failed to connect to MQTT broker, return code: {rc}")


def on_disconnect(client, userdata, rc, properties=None):
    """Callback when disconnected from MQTT broker."""
    if rc != 0:
        logger.warning(f"Unexpected disconnection from MQTT broker (rc={rc})")


def on_message(client, userdata, msg):
    """Callback when a message is received."""
    global stats
    stats['messages_received'] += 1

    try:
        # Parse the message payload
        payload = json.loads(msg.payload.decode('utf-8'))

        # Extract decoder type from topic (intercept/pocsag -> pocsag)
        topic_parts = msg.topic.split('/')
        if len(topic_parts) >= 2:
            decoder_type = topic_parts[1]
            payload['decoder'] = decoder_type

        # Ensure timestamp exists
        if '@timestamp' not in payload and 'timestamp' not in payload:
            payload['@timestamp'] = datetime.utcnow().isoformat() + 'Z'

        # Add source info
        payload['_mqtt_topic'] = msg.topic

        # Forward to Logstash
        if forward_to_logstash(payload):
            stats['messages_forwarded'] += 1
            logger.debug(f"Forwarded message from {msg.topic}")
        else:
            stats['errors'] += 1

    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in message from {msg.topic}: {e}")
        stats['errors'] += 1
    except Exception as e:
        logger.error(f"Error processing message from {msg.topic}: {e}")
        stats['errors'] += 1


def print_stats():
    """Print current statistics."""
    if stats['start_time']:
        uptime = time.time() - stats['start_time']
        logger.info(
            f"Stats: received={stats['messages_received']}, "
            f"forwarded={stats['messages_forwarded']}, "
            f"errors={stats['errors']}, "
            f"uptime={uptime:.0f}s"
        )


def main():
    """Main entry point."""
    global running, stats

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 60)
    logger.info("MQTT to Logstash Bridge")
    logger.info("=" * 60)
    logger.info(f"MQTT Broker: {MQTT_HOST}:{MQTT_PORT}")
    logger.info(f"MQTT Topic:  {MQTT_TOPIC}")
    logger.info(f"Logstash:    {LOGSTASH_URL}")
    logger.info("=" * 60)

    # Create MQTT client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="mqtt-logstash-bridge")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Connect to broker
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")
        sys.exit(1)

    stats['start_time'] = time.time()

    # Start the MQTT loop in a non-blocking way
    client.loop_start()

    # Main loop - print stats periodically
    last_stats_time = time.time()
    while running:
        time.sleep(1)

        # Print stats every 60 seconds
        if time.time() - last_stats_time >= 60:
            print_stats()
            last_stats_time = time.time()

    # Cleanup
    logger.info("Stopping MQTT client...")
    client.loop_stop()
    client.disconnect()

    print_stats()
    logger.info("Bridge stopped.")


if __name__ == '__main__':
    main()
