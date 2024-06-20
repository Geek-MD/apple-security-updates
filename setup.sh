#!/bin/sh
# filename: setup.sh

path="$PWD"
chmod u+x "$path"/asu-notifier.py
python3 "$path"/asu-notifier.py -h