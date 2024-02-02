#!/usr/bin/env python3

# Apple Security Updates Notifier v0.4.2
# File: asu-notifier.py
# Description: Main component of ASU Notifier, used to create config.json file, initialize the database, and set a
# cronjob which will run the secondary component of ASU Notifier hourly.

import argparse
import json
import os
import re
import textwrap
import urllib.request
import sqlite3
import pycountry
import pytz
import requests
import logging
import contextlib
from sqlite3 import Error, Connection
from crontab import CronTab
from typing import TypeVar

# SQL queries
sql_check_empty_database: str = """ SELECT COUNT(name) FROM sqlite_master WHERE type='table' AND name='main' """
sql_create_main_table: str = """CREATE TABLE IF NOT EXISTS main ( main_id integer PRIMARY KEY AUTOINCREMENT, log_date 
text NOT NULL, file_hash text NOT NULL, log_message text NOT NULL );"""
sql_create_updates_table: str = """CREATE TABLE IF NOT EXISTS updates ( update_id integer PRIMARY KEY AUTOINCREMENT, 
update_date text NOT NULL, update_product text NOT NULL, update_target text NOT NULL, update_link text, 
file_hash text NOT NULL );"""

def create_connection(file):
    if not os.path.isfile(file):
        logging.info(f'\'{file}\' database created.')
    conn = TypeVar('conn', Connection, None)
    try:
        conn: Connection = sqlite3.connect(file)
    except Error as error:
        logging.error(str(error))
    return conn

def create_table(conn, sql_create_table, table_name, file):
    with contextlib.suppress(Error):
        try:
            conn.cursor().execute(sql_create_table)
            logging.info(f'\'{file}\' - \'{table_name}\' table created.')
        except Error as error:
            logging.error(str(error))

def get_config(local_path):
    config = open(f'{local_path}/asu-notifier.json', 'r')
    data = json.loads(config.read())
    prog_name_short = data['prog_name_short']
    prog_name_long = data['prog_name_long']
    version = data['version']
    apple_url = data['apple_url']
    return prog_name_short, prog_name_long, version, apple_url

def create_config_json(local_path, apple_url, prog_name, bot_token, chat_ids, tzone):
    config_str = f"""  "apple_url": "{apple_url}",
  "db_file": "{local_path}/{prog_name}.db",
  "log_file": "{local_path}/{prog_name}.log",
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
    with open(f"{local_path}/config.json", "w") as file:
        file.write(config_str)
    return f'{local_path}/{prog_name}.log', f'{local_path}/{prog_name}.db'

def crontab_job(working_dir):
    cronjob = CronTab(user=True)
    comment = "asu-notifier"
    comment_found = any(job.comment == comment for job in cronjob)
    if not comment_found:
        job = cronjob.new(command=f'python3 {working_dir}/asu-bot.py', comment='asu-notifier')
        job.setall('0 */6 * * *')
        job.enable()
    cronjob.write()

def token_validator(bot_token):
    token_json = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe")
    token_info = token_json.json()
    return token_info["ok"]

def timezone_selection(country_code):
    country_name = pycountry.countries.get(alpha_2=country_code).name
    country_timezones = pytz.country_timezones[country_code]
    country_tz_len = len(country_timezones)
    selection = False
    print(f'{country_name} [{country_code}] timezones:')
    print('0: Switch back to default timezone (UTC)')
    if country_tz_len == 1:
        return country_timezones[0]
    for i, tz in enumerate(country_timezones):
        print(f'{i + 1}: {tz}')
    while not selection:
        tz_selection = input("Select a timezone: ")
        index = int(tz_selection) - 1
        if int(tz_selection) == 0:
            selection = True
            return 'UTC'
        elif country_tz_len >= int(tz_selection) > 0:
            selection = True
            return country_timezones[index]
        else:
            print(f'Wrong choice, pick a number between 0 and {country_tz_len}')

def undefined_timezone():
    external_ip = urllib.request.urlopen('https://ident.me').read().decode('utf8')
    location_data = requests.get(f'https://ipapi.co/{external_ip}/json/').json()
    country_name = location_data.get("country_name")
    country_code = location_data.get("country_code")
    if country_code is None or country_name is None:
        print(f"I can´t identify your country based on your IP [{external_ip}], so you have to set timezone or "
              f"country manually.")
        exit(1)
    else:
        print(f"""According to your IP address [{external_ip}], it seems that your country is {country_name} 
[{country_code}]""")
        selection = False
        while not selection:
            answer = input("Is this correct? (y/n): ")
            if answer == 'n':
                print("""I can´t identify your country based on your IP, so you have to set timezone or country 
manually.""")
                selection = True
                exit(1)
            elif answer == 'y':
                selection = True
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
        print(f'\nTimezone is set to it\'s default value [UTC].')
        selection = False
        while not selection:
            answer = input("Are you OK with it? (y/n): ")
            if answer == 'n':
                selection = True
                return undefined_timezone()
            elif answer == 'y':
                selection = True
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
    selection = False
    counter = 1
    while not selection:
        answer = input(f'Type in chat id #{counter}: ')
        if answer == '0':
            selection = True
            return chat_ids
        elif re.search(regex, answer):
            chat_ids.append(answer)
            counter += 1
        else:
            print("Incorrect format, try again.")

def argument_parser(progname_short, progname_long, ver):
    description = f'{progname_long} is python program that will notify you through Telegram, about new Apple updates.'
    epilog = """Bot token is made-up of a numerical string of 8-10 digits followed by a ":", and finishes with a 35 
alphanumeric string. For ISO Alpha-2 codes refer to http://iban.com/country-codes. Chat ids must be provided one 
after another separated by a space, like \"-123456 -4567890\"."""
    parser = argparse.ArgumentParser(prog=f"{progname_short}",
                                     description=textwrap.dedent(f"{description}"),
                                     epilog=f"{epilog}",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-b', '--bot-token', help='set Telegram bot token', required=True)
    parser.add_argument('-t', '--timezone', default='UTC', help='[optional] Set bot timezone. Use X or x as argument '
                                                                'to allow identification your timezone according to '
                                                                'your IP address')
    parser.add_argument('-c', '--country', help='[optional] Define a country in order to select an appropriate '
                                                'timezone. Use X or x as argument to allow identification your '
                                                'country according to your IP address')
    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {ver}',
                        help='Show %(prog)s version information and exit')
    parser.add_argument('-i', '--chat-ids', default=None, action="extend", nargs="*", type=str, help='[optional] '
                                                                                                     'Define allowed '
                                                                                                     'chat ids at '
                                                                                                     'startup. If not '
                                                                                                     'set at startup, '
                                                                                                     'it will be '
                                                                                                     'prompted later '
                                                                                                     'in the script')
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
    local_file = __file__
    local_path = os.path.dirname(local_file)

    prog_name_short, prog_name_long, version, apple_url = get_config(local_path)
    bot_token, timezone, chat_ids = argument_parser(prog_name_short, prog_name_long, version)
    log_file, db_file = create_config_json(local_path, apple_url, prog_name_short, bot_token, chat_ids, timezone)

    # logging
    log_format = '%(asctime)s -- %(message)s'
    logging.basicConfig(filename=log_file, encoding='utf-8', format=log_format, level=logging.INFO)

    # create a database connection
    conn: Connection = create_connection(db_file)
    cursor = conn.cursor()
    empty_database = cursor.execute(sql_check_empty_database).fetchone()[0] == 0
    if empty_database:
        # create database tables and populate them
        create_table(conn, sql_create_main_table, 'main', db_file)
        create_table(conn, sql_create_updates_table, 'updates', db_file)

    crontab_job(local_path)

if __name__ == '__main__':
    main()
