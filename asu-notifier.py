#!/usr/bin/env python3

# Apple Security Updates Notifier v0.5.0
# File: asu-notifier.py
# Description: Main component of ASU Notifier, used to create config.json file, initialize the database, and set a
# cronjob which will run the secondary component of ASU Notifier.

import argparse
import contextlib
import datetime
import json
import logging
import os
import re
import sqlite3
import textwrap
import urllib.request
from datetime import datetime
from sqlite3 import Error, Connection
from typing import TypeVar

import pycountry
import pytz
import requests
from crontab import CronTab
from telegram import Bot

# SQL queries
sql_check_empty_database: str = """ SELECT COUNT(name) FROM sqlite_master WHERE type='table' AND name='main' """
sql_create_main_table: str = """CREATE TABLE IF NOT EXISTS main ( main_id integer PRIMARY KEY AUTOINCREMENT, log_date 
text NOT NULL, file_hash text NOT NULL, log_message text NOT NULL );"""
sql_create_updates_table: str = """CREATE TABLE IF NOT EXISTS updates ( update_id integer PRIMARY KEY AUTOINCREMENT, 
update_date text NOT NULL, update_product text NOT NULL, update_target text NOT NULL, update_link text, 
file_hash text NOT NULL );"""


def get_init(init_file):
    try:
        init = open(init_file, "r")
        data = json.loads(init.read())
        progname = data["progname"]
        prog_name_short = data["prog_name_short"]
        prog_name_long = data["prog_name_long"]
        version = data["version"]
        apple_url = data["apple_url"]
        return progname, prog_name_short, prog_name_long, version, apple_url
    except json.JSONDecodeError as e:
        print(f"Error when decoding JSON file: {e}")
        exit(1)


def argument_parser(progname, progname_short, progname_long, ver):
    description = f"{progname_long} is a Python program that will notify you through Telegram, about new Apple updates."
    epilog = ("bot token is made-up of a numerical string of 8-10 digits followed by a \":\", and finishes with a 35 "
              "alphanumeric string.\nfor ISO Alpha-2 codes refer to http://iban.com/country-codes.\nchannel ids must "
              "be provided one after another separated by a space, like \"-123456 -4567890\".")
    parser = argparse.ArgumentParser(
        prog=f"{progname}",
        description=textwrap.dedent(f"{description}"),
        epilog=f"{epilog}",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"{progname_short} {ver}",
        help=f"show {progname_short} version information and exit.",
    )
    parser.add_argument(
        "-c",
        "--cron",
        required=False,
        action="store",
        metavar="cron",
        nargs="?",
        default="0 */6 * * *",
        help="[optional] used to schedule packages update via crontab. default cron is '0 */6 * * *'. for aditional "
             "examples refer to https://crontab.guru.",
    )
    parser.add_argument(
        "-b",
        "--bot-token",
        action="store",
        nargs="?",
        metavar="bot-token",
        default=None,
        required=True,
        help="set Telegram bot token",
    )
    parser.add_argument(
        "-t",
        "--timezone",
        action="store",
        nargs="?",
        metavar="timezone",
        default=None,
        help="[optional] set bot timezone. You can use a country code for the argument in order to select an "
             "appropriate timezone. if you leave the argument empty, the script will try to guess your timezone based "
             "on your IP address. if IP address can't be determined, timezone will be set to UTC.",
    )
    parser.add_argument(
        "-ch",
        "--channels",
        default=None,
        action="extend",
        metavar="channels",
        nargs="*",
        type=str,
        help="[optional] define allowed channel ids at startup. if not set at startup, it will be prompted later in "
             "the script.",
    )
    args = parser.parse_args()
    config = vars(args)
    cron = config["cron"]
    bot_token = config["bot_token"]
    timezone = config["timezone"]
    channels = config["channels"]
    cron = regex_cronjob(cron)
    bot_token = regex_bot_token(bot_token)
    timezone = check_timezone(timezone)
    channels = check_channels(channels, bot_token)
    return cron, bot_token, timezone, channels


def regex_cronjob(cron):
    regex = ("^(\*|([0-9]|[1-5][0-9])(,([0-9]|[1-5][0-9]))*|\*\/([0-9]|[1-5][0-9])|([0-9]|[1-5][0-9])-([0-9]|[1-5]["
             "0-9])) (\*|([0-9]|[1][0-9]|[2][0-3])(,([0-9]|[1][0-9]|[2][0-3]))*|\*\/([0-9]|[1][0-9]|[2][0-3])|(["
             "0-9]|[1][0-9]|[2][0-3])-([0-9]|[1][0-9]|[2][0-3])) (\*|([1-9]|[1-2][0-9]|[3][0-1])(,([1-9]|[1-2][0-9]|["
             "3][0-1]))*|\*\/([1-9]|[1-2][0-9]|[3][0-1])|([1-9]|[1-2][0-9]|[3][0-1])-([1-9]|[1-2][0-9]|[3][0-1])) ("
             "\*|([1-9]|[1][0-2])(,([1-9]|[1][0-2]))*|\*\/([1-9]|[1][0-2])|([1-9]|[1][0-2])-([1-9]|[1][0-2])) (\*|(["
             "0-7])(,([0-7]))*|\*\/([0-7])|([0-7])-([0-7]))$")
    if re.match(regex, cron) is True:
        return cron
    elif cron is None:
        return cron
    else:
        log_message("Cron format is incorrect.")
        exit(1)


def regex_bot_token(bot_token):
    regex = "^[0-9]*:[a-zA-Z0-9_-]{35}$"
    if bot_token is None:
        log_message("You must provide a 'bot token'.")
        exit(1)
    elif re.search(regex, bot_token):
        if token_validator(bot_token) == "ok":
            log_message("Bot token OK.")
            return bot_token
        else:
            log_message("Bot token is invalid. Check the information generated by BotFather when you created the bot.")
            exit(1)
    else:
        log_message("Bot token format is incorrect. Check './asu-notifier.sh -h' for more information.")
        exit(1)


def check_timezone(timezone):
    timezones_list = pytz.all_timezones
    if timezone is None:
        timezone = guess_timezone()
        log_message(f"Timezone set to {timezone}")
        return timezone
    elif timezone in timezones_list:
        log_message(f"Timezone set to {timezone}")
        return timezone
    elif timezone.upper() in pytz.country_names:
        timezone = set_timezone(timezone.upper())
        log_message(f"Timezone set to {timezone}")
        return timezone
    else:
        log_message("Incorrect timezone or country code.\nFor ISO Alpha-2 country codes refer to "
                    "http://iban.com/country-codes.")
        exit(1)


def check_channels(chat_ids, bot_token):
    if type(chat_ids) is list:
        return get_channels(bot_token, chat_ids)
    elif chat_ids is None:
        log_message("channel ids must be provided one after another separated by a space, like '-123456 -4567890'.")
        exit(1)
    else:
        log_message("channel ids must be provided one after another separated by a space, like '-123456 -4567890'.")
        exit(1)


def get_channels(bot_token, *args):
    regex = "(-[0-9]+)"
    if args:
        channel_ids = args
        for element in channel_ids:
            if re.search(regex, element) is True:
                continue
            else:
                log_message(f"Incorrect format for {element}.")
                exit(1)
    else:
        channel_ids = []
        print("\nType in channel ids where the script will notify Apple Updates. To finish input, type \"0\".")
        print("Remember to include the minus sign before each channel id like \"-6746386747\".")
        counter = 1
        while True:
            answer = input(f"Type in channel id #{counter}: ").strip().lower()
            if answer == "0":
                break
            elif re.search(regex, answer) is True:
                channel_ids.append(answer)
                counter += 1
            else:
                log_message(f"Incorrect format for {answer}, try again.")
    channel_ids = verify_channels(channel_ids, bot_token)
    return channel_ids


async def verify_channels(channel_ids, bot_token):
    bot = Bot(bot_token)
    for chat_id in channel_ids:
        bot_info = await bot.get_me()
        bot_id = bot_info.id
        chat_member = await bot.get_chat_member(chat_id, bot_id)
        if chat_member.status != 'left':
            continue
        else:
            log_message(f'The bot is not a member of channel {chat_id}.')
            exit(1)
    return channel_ids


def guess_timezone():
    external_ip = urllib.request.urlopen("https://ident.me").read().decode("utf8")
    location_data = requests.get(f"https://ipapi.co/{external_ip}/json/").json()
    country_name = location_data.get("country_name")
    country_code = location_data.get("country_code")
    if country_code is None or country_name is None:
        log_message(f"I can't identify your country based on your IP [{external_ip}], so I will set timezone to UTC.")
        return "UTC"
    else:
        print(f"According to your IP address [{external_ip}], it seems that your country is {country_name} "
              f"[{country_code}].")
        while True:
            answer = input("Is this correct? (y/n): ").strip().lower()
            if answer in ["y", "n"]:
                break
            else:
                print("Invalid input. Please, enter \"y\" or \"n\".")
        if answer == "n":
            log_message(f"I can't identify your country based on your IP [{external_ip}], so I will set timezone to "
                        f"UTC.")
            return "UTC"
        elif answer == "y":
            return set_timezone(country_code)


def set_timezone(country_code):
    country_name = pycountry.countries.get(alpha_2=country_code).name
    country_timezones = pytz.country_timezones[country_code]
    country_tz_len = len(country_timezones)
    print(f"{country_name} [{country_code}] timezones:")
    print("0: Set timezone to UTC")
    if country_tz_len == 1:
        return country_timezones[0]
    for i, tz in enumerate(country_timezones):
        print(f'{i + 1}: {tz}')
    while True:
        answer = input("Select a timezone: ").strip().lower()
        index = int(answer) - 1
        if int(answer) in range(0, country_tz_len):
            break
        else:
            print(f"Wrong choice, pick a number between 0 and {country_tz_len}.")
    if int(answer) == 0:
        log_message(f"You have selected UTC (Universal Time Coordinated).")
        return "UTC"
    else:
        log_message(f"You have selected {country_timezones[index]}.")
        return country_timezones[index]


def token_validator(bot_token):
    token_json = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe")
    token_info = token_json.json()
    return token_info["ok"]


def update_config(config_file, cron, bot_token, timezone, channels):
    config = {
        "cron": cron,
        "timezone": timezone,
        "bot_token": bot_token,
        "channels": channels
    }
    json_config = json.dumps(config)
    with open(config_file, 'w') as file:
        file.write(json_config)


def get_config(config_file):
    try:
        config = open(config_file, "r")
        data = json.loads(config.read())
        cron = data["cron"]
        timezone = data["timezone"]
        bot_token = data["bot_token"]
        channels = data["channels"]
        if regex_bot_token(bot_token) and check_channels(channels, bot_token):
            return cron, bot_token, timezone, channels
        if bot_token is None or channels is None:
            log_message("There's not 'bot token' or 'channels' data available, you must provide it at least at the "
                        "first execution.")
            exit(1)
    except FileNotFoundError as e:
        log_message(f"File '{config_file}' does not exist. Run the script again providing at least 'bot token' and "
                    f"'channels' so the script can recreate the file.\n{e}")
        exit(1)
    except json.JSONDecodeError as e:
        log_message(f"Error when decoding JSON file: {e}")
        exit(1)


def check_config(config_file, cron, bot_token, timezone, channels, *args):
    # funcion no está terminada
    if args:
        cron2 = args[0]
        bot_token2 = args[1]
        timezone2 = args[2]
        channels2 = args[3]
        if regex_cronjob(cron2) and cron != cron2:
            print(f"The cronjob provided ({cron2}) is different from the one stored at config.json.")
            while True:
                answer = input("Do you want to replace actual cron with the new one? (y/n): ").strip().lower()
                if answer in ["y", "n"]:
                    break
                else:
                    print("Invalid input. Please, enter \"y\" or \"n\".")
            if answer == "n":
                print("Actual cron was not modified.")
            elif answer == "y":
                print("Cron updated with new info.")
                cron = cron2
        if regex_bot_token(bot_token2) and bot_token != bot_token2:
            print(f"The bot token provided ({bot_token2}) is different from the one stored at config.json.")
            while True:
                answer = input("Do you want to replace actual bot token with the new one? (y/n): ").strip().lower()
                if answer in ["y", "n"]:
                    break
                else:
                    print("Invalid input. Please, enter \"y\" or \"n\".")
                    if answer == "n":
                        print("Actual bot token was not modified.")
                    elif answer == "y":
                        print("Bot token updated with new info.")
                        bot_token = bot_token2
        if check_timezone(timezone2) and timezone != timezone2:
            print(f"The timezone provided ({timezone}) is different from the one stored at config.json.")
            while True:
                answer = input("Do you want to replace actual timezone with the new one? (y/n): ").strip().lower()
                if answer in ["y", "n"]:
                    break
                else:
                    print("Invalid input. Please, enter \"y\" or \"n\".")
                    if answer == "n":
                        print("Actual timezone was not modified.")
                    elif answer == "y":
                        print("Timezone updated with new info.")
                        timezone = timezone2
        if check_channels(channels2, bot_token) and channels != channels2:
            print(f"The channels provided ({channels}) are different from the ones stored at config.json.")
            while True:
                answer = input("Do you want to replace actual channels with the new ones? (y/n): ").strip().lower()
                if answer in ["y", "n"]:
                    break
                else:
                    print("Invalid input. Please, enter \"y\" or \"n\".")
                    if answer == "n":
                        print("Actual channels were not modified.")
                    elif answer == "y":
                        print("Telegram channels updated with new info.")
                        channels = channels2
        update_config(config_file, cron, bot_token, timezone, channels)
    return cron, bot_token, timezone, channels


def crontab_job(cron, working_dir):
    cronjob = CronTab(user=True)
    comment = "asu-notifier"
    comment_found = any(job.comment == comment for job in cronjob)
    if not comment_found:
        job = cronjob.new(command=f"bash {working_dir}/asu-bot.sh", comment="asu-notifier")
        job.setall(cron)
        job.enable()
    cronjob.write()


def create_connection(file):
    log_date = datetime.now()
    if not os.path.isfile(file):
        logging.info(f"'{log_date} -- {file}' database created.")
    conn = TypeVar('conn', Connection, None)
    try:
        conn: Connection = sqlite3.connect(file)
    except Error as error:
        logging.error(f"{log_date} -- {str(error)}")
    return conn


def create_table(conn, sql_create_table, table_name, file):
    log_date = datetime.now()
    with contextlib.suppress(Error):
        try:
            conn.cursor().execute(sql_create_table)
            logging.info(f"{log_date} -- '{file}' - '{table_name}' table created.")
        except Error as error:
            logging.error(f"{log_date} -- {str(error)}")


def log_message(msg):
    log_date = datetime.now()
    print(msg)
    logging.info(f'{log_date} -- {msg}')


def main():
    local_path = os.path.dirname(__file__)
    init_file = f"{local_path}/init.json"
    config_file = f"{local_path}/config.json"
    log_file = f"{local_path}/asu-notifier.log"
    db_file = f"{local_path}/asu-notifier.db"

    # logging
    log_format = "%(asctime)s -- %(message)s"
    logging.basicConfig(
        filename=log_file, encoding="utf-8", format=log_format, level=logging.INFO
    )

    progname, progname_short, progname_long, version, apple_url = get_init(init_file)
    config_file_check = os.path.exists(config_file)

    if config_file_check is False:
        cron, bot_token, timezone, channels = argument_parser(progname, progname_short, progname_long, version)
        update_config(config_file, cron, bot_token, timezone, channels)
    else:
        cron, bot_token, timezone, channels = get_config(config_file)
        cron2, bot_token2, timezone2, channels2 = argument_parser(progname, progname_short, progname_long, version)
        cron, bot_token, timezone, channels = check_config(config_file, cron, bot_token, timezone, channels,
                                                           cron2, bot_token2, timezone2, channels2)

    # create a database connection
    conn: Connection = create_connection(db_file)
    cursor = conn.cursor()
    empty_database = cursor.execute(sql_check_empty_database).fetchone()[0] == 0
    if empty_database:
        # create database tables and populate them
        create_table(conn, sql_create_main_table, "main", db_file)
        create_table(conn, sql_create_updates_table, "updates", db_file)

    crontab_job(cron, local_path)


if __name__ == "__main__":
    main()
