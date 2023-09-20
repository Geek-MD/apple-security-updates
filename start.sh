#!/bin/sh
# filename: asu-notifier.sh
pip install -r requirements.txt > requirements.log
path="$PWD"
python3 "$path"/asu-notifier.py -h