#!/bin/bash
docker run -d --restart always --user elan2mqtt:elan2mqtt --name elan2mqtt -v $PWD/elan2mqtt/config.json:/elan2mqtt/config.json elan2mqtt

