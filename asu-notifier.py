#!/usr/bin/env python3

# This script recreates config.json and asu-notifier.service files.

import argparse
import json
import os
import re
import subprocess
import textwrap
import urllib.request

import pycountry
import pytz
import requests


def get_config():
    config = open('asu-notifier.json', 'r')
    data = json.loads(config.read())
    prog_name_short = data['prog_name_short']
    prog_name_long = data['prog_name_long']
    version = data['version']
    apple_url = data['apple_url']
    return prog_name_short, prog_name_long, version, apple_url

def create_service_file(working_dir, pythonpath, progname):
    service_str = f"""[Unit]
Description={progname}
After=multi-user.target

[Service]
Type=simple
Environment=DISPLAY=:0
ExecStartPre=/bin/sleep 60
ExecStart=/usr/bin/python3 {working_dir}/asu-bot.py
Restart=on-failure
RestartSec=30s
KillMode=process
TimeoutSec=infinity
Environment="PYTHONPATH=$PYTHONPATH:{pythonpath}/"

[Install]
WantedBy=multi-user.target"""
    with open("asu-notifier.service", "w") as file:
        file.write(service_str)

def create_config_json(apple_url, prog_name, bot_token, chat_ids, tzone):
    config_str = f"""  "apple_url": "{apple_url}",
  "db_file": "{prog_name}.db",
  "log_file": "{prog_name}.log",
  "timezone": "{tzone}",
  "bot_token": "{bot_token}",
  "chat_ids": [
"""
    for i, value in enumerate(chat_ids):
        if i+1 < len(chat_ids):
            config_str += f'    "{value}", \n'
        else:
            config_str += f'    "{value}"\n'
    config_str += "  ]"
    config_str = "{\n" + config_str + "\n}"
    with open("config.json", "w") as file:
        file.write(config_str)

def token_validator(bot_token):
    token_json = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe")
    token_info = token_json.json()
    return token_info["ok"]

def timezone_selection(country_code):
    country_name = pycountry.countries.get(alpha_2=country_code).name
    country_timezones = pytz.country_timezones[country_code]
    country_tz_len = len(country_timezones)
    selection_bool = False
    print(f'{country_name} [{country_code}] timezones:')
    print('0: Switch back to default timezone (UTC)')
    if country_tz_len == 1:
        return country_timezones[0]
    for i, tz in enumerate(country_timezones):
        print(f'{i + 1}: {tz}')
    while not selection_bool:
        tz_selection = input("Select a timezone: ")
        index = int(tz_selection) - 1
        if int(tz_selection) == 0:
            selection_bool = True
            return 'UTC'
        elif country_tz_len >= int(tz_selection) > 0:
            selection_bool = True
            return country_timezones[index]
        else:
            print(f'Wrong choice, pick a number between 0 and {country_tz_len}')

def undefined_timezone():
    external_ip = urllib.request.urlopen('https://ident.me').read().decode('utf8')
    location_data = requests.get(f'https://ipapi.co/{external_ip}/json/').json()
    country_name = location_data.get("country_name")
    country_code = location_data.get("country_code")
    if country_code is None or country_name is None:
        print(f"I can´t identify your country based on your IP [{external_ip}], so you have to set timezone or country manually.")
        exit(1)
    else:
        print(f'According to your IP address [{external_ip}], it seems that your country is {country_name} [{country_code}]')
        selection_bool = False
        while not selection_bool:
            selection = input("Is this correct? (y/n): ")
            if selection == 'n':
                print("I can´t identify your country based on your IP, so you have to set timezone or country manually.")
                selection_bool = True
                exit(1)
            elif selection == 'y':
                selection_bool = True
                return timezone_selection(country_code)

def set_timezone(country_code):
    country_names = pytz.country_names
    if country_code.upper() == 'X':
        return undefined_timezone()
    elif country_code.upper() not in country_names:
        print("Incorrect country code.\nFor ISO Alpha-2 codes refer to http://iban.com/country-codes")
        exit(1)
    else:
        return timezone_selection(country_code.upper())

def check_timezone(timezone):
    timezones_list = pytz.all_timezones
    if timezone.upper() == "X":
        return undefined_timezone()
    elif timezone == 'UTC':
        print (f'\nTimezone is set to it\'s default value [UTC].')
        selection_bool = False
        while not selection_bool:
            selection = input("Are you OK with it? (y/n): ")
            if selection == 'n':
                selection_bool = True
                return undefined_timezone()
            elif selection == 'y':
                selection_bool = True
                return 'UTC'
    elif timezone not in timezones_list:
        print("Incorrect timezone.")
        exit(1)
    else:
        return timezone

def check_chat_ids(chat_ids):
    if type(chat_ids) is list:
        return chat_ids
    print('Wrong format of "chat ids", it must me a list. Defaulting to UTC.')
    return 'UTC'

def check_bot_token(bot_token):
    regex = "^[0-9]*:[a-zA-Z0-9_-]{35}$"
    if re.search(regex, bot_token):
        if token_check := token_validator(bot_token):
            return token_check
        else:
            exit(1)
    else:
        exit(1)

def get_chat_ids():
    regex = "(-[0-9]+)"
    chat_ids = []
    print("\nType in chat ids where the script will notify Apple Updates. To finish input, type \"0\".")
    print("Remember to include the minus sign before each chat id like \"-6746386747\".")
    selection_bool = False
    counter = 1
    while not selection_bool:
        selection = input(f'Type in chat id #{counter}: ')
        if selection == '0':
            selection_bool = True
            return chat_ids
        elif re.search(regex, selection):
            chat_ids.append(selection)
            counter += 1
        else:
            print("Incorrect format, try again.")

def argument_parser(progname_short, progname_long, ver):
    description = f'script used to setup {progname_long}. It creates the systemd service file, config file and starts the service'
    epilog = """bot token is made-up of a numerical string of 8-10 digits followed by a ":", and finishes with a 35 alphanumeric string.
for ISO Alpha-2 codes refer to http://iban.com/country-codes.
chat ids must be provided one after another separated by a space, like \"-123456 -4567890\"."""
    parser = argparse.ArgumentParser(prog=f"{progname_short}",
                                     description=textwrap.dedent(f"{description}"),
                                     epilog=f"{epilog}",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-b', '--bot-token', help='set Telegram bot token', required=True)
    parser.add_argument('-t', '--timezone', default='UTC', help='[optional] set bot timezone. Use X or x as argument to allow identification your timezone according to your IP address')
    parser.add_argument('-c', '--country', help='[optional] define a country in order to select an appropriate timezone. Use X or x as argument to allow identification your country according to your IP address')
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {ver}',
                        help='show %(prog)s version information and exit')
    parser.add_argument('-i', '--chat-ids', default=None, action="extend", nargs="*", type=str, help='[optional] define allowed chat ids at startup. If not set at startup, it will be prompted later in the script')
    args = parser.parse_args()
    config = vars(args)
    bot_token = config['bot_token']
    country = config['country']
    chat_ids = config['chat_ids']
    timezone = set_timezone(country) if country is not None else config['timezone']
    timezone = check_timezone(timezone)
    chat_ids = get_chat_ids() if chat_ids is None else check_chat_ids(chat_ids)
    if check_bot_token(bot_token):
        return bot_token, timezone, chat_ids

def main():
    python_path = subprocess.check_output("which python", shell=True).strip().decode('utf-8')
    working_dir = os.getcwd()

    prog_name_short, prog_name_long, version, apple_url = get_config()
    bot_token, timezone, chat_ids = argument_parser(prog_name_short, prog_name_long, version)
    create_service_file(python_path, working_dir, prog_name_long)
    create_config_json(apple_url, prog_name_short, bot_token, chat_ids, timezone)
    subprocess.run(f'{working_dir}/asu-notifier.sh')

if __name__ == '__main__':
    main()
