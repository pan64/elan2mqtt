#!/bin/sh

echo "Run.sh starting"
ELAN2MQTT_VERSION=1.16.0
ARCHIVE=elan2mqtt-$ELAN2MQTT_VERSION

echo "Starting gateway"
export PYTHONPATH=/$ARCHIVE
python3 main_worker.py -log-level trace -disable-autodiscovery false &
python3 socket_listener.py -log-level trace
