#!/bin/bash

env_name="venv"
# shellcheck disable=SC1090
source "./$env_name/bin/activate"

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    python3 ./asu-notifier.py -h
    exit 0
elif [ "$1" = "--version" ] || [ "$1" = "-v" ]; then
    python3 ./asu-notifier.py -v
    exit 0
else
    # shellcheck disable=SC2068
    python3 ./asu-notifier.py $@
    exit 0
fi
