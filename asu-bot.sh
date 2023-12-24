#!/bin/bash

env_name="venv"
# shellcheck disable=SC1090
source "./$env_name/bin/activate"
python3 ./asu-bot.py
