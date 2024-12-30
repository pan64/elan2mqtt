#!/bin/sh

echo "Run.sh starting"
ELAN2MQTT_VERSION=1.17.0
ARCHIVE=elan2mqtt-$ELAN2MQTT_VERSION

echo "Starting gateway"
export PYTHONPATH=/$ARCHIVE
exec python3 elan2mqtt.py
