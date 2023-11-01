#!/bin/bash

echo "Run.sh starting"
DIR=/home/pan/elan2mqtt/elan2mqtt/elan2mqtt
CONFIG_PATH=/$DIR/config.json
SYSTEM_USER=/$DIR/system_user.json

ELAN_URL=$(jq --raw-output ".options.eLanURL" $CONFIG_PATH)
MQTT_SERVER=$(jq --raw-output ".options.MQTTserver" $CONFIG_PATH)
USERNAME=$(jq --raw-output ".options.username" $CONFIG_PATH)
PASSWORD=$(jq --raw-output ".options.password" $CONFIG_PATH)
LOGLEVEL=$(jq --raw-output ".options.log_level" $CONFIG_PATH)
DISABLEAUTODISCOVERY=$(jq --raw-output ".options.disable_autodiscovery" $CONFIG_PATH)

#echo "Installing requirements"
#pip3 install -r requirements.txt

#trap 'kill $PID' exit

echo "Starting gateway"
echo elan url: ${ELAN_URL}
echo mqtt server: ${MQTT_SERVER}
echo "Loglevel:" ${LOGLEVEL} 
echo "Autodiscovery disabled:" ${DISABLEAUTODISCOVERY}
echo python3 main_worker.py ${ELAN_URL} ${MQTT_SERVER} -elan-user ${USERNAME} -elan-password ${PASSWORD} -log-level ${LOGLEVEL} -disable-autodiscovery ${DISABLEAUTODISCOVERY} &
#PID=$!
echo python3 socket_listener.py ${ELAN_URL} ${MQTT_SERVER} -elan-user ${USERNAME} -elan-password ${PASSWORD} -log-level ${LOGLEVEL} 
