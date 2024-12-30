ARG BUILD_FROM=invalid
FROM $BUILD_FROM

# Add env
ENV LANG=C.UTF-8
ENV ELAN2MQTT_VERSION=1.17.0
ENV ARCHIVE=elan2mqtt

# Install requirements for add-on
#RUN apk add --no-cache --update python3 py3-pip
#RUN apk add --no-cache --update gcc g++ libc-dev python3-dev 
RUN mkdir -p /$ARCHIVE

# install python packages
COPY requirements.txt /$ARCHIVE/requirements.txt
RUN pip install --no-cache-dir -r /$ARCHIVE/requirements.txt

# Copy data for add-on
COPY run.sh /$ARCHIVE/run.sh
COPY elan2mqtt.py /$ARCHIVE/elan2mqtt.py
COPY elan_client.py /$ARCHIVE/elan_client.py
COPY mqtt_client.py /$ARCHIVE/mqtt_client.py
COPY device.py /$ARCHIVE/device.py
# COPY config.json /$ARCHIVE/config.json

# Let's set it to our add-on persistent data directory.
WORKDIR /$ARCHIVE


# RUN apk del gcc g++ libc-dev python3-dev

RUN ["chmod", "a+x", "./run.sh"]
RUN echo 'elan2mqtt:x:1002:1002::/home/elan2mqtt:/bin/sh' >> /etc/passwd && \
    echo 'elan2mqtt:x:1002:' >> /etc/group && \
    mkdir /home/elan2mqtt && \
    chown elan2mqtt:elan2mqtt /home/elan2mqtt 

CMD [ "./run.sh" ]
