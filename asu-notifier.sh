#!/bin/sh

# filename: asu-notifier.sh

LOCAL_DIR=$(pwd)

sudo cp $LOCAL_DIR/asu-notifier.service /etc/systemd/system/asu-notifier.service

sudo systemctl daemon-reload
sudo systemctl enable asu-notifier.service
sudo systemctl start asu-notifier.service
