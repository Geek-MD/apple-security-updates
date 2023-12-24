#!/usr/bin/env python3

# Apple Security Updates Notifier v0.5.0
# File: asu-bot.py
# Description: Secondary component of ASU Notifier, which will run hourly and notify via Telegram of any new security
# update.

import datetime
import hashlib
import json
import logging
import os
import os.path
import re
import sqlite3
from datetime import datetime
from sqlite3 import Error, Connection
from typing import TypeVar

import pytz
import requests
from apprise import Apprise
from bs4 import BeautifulSoup

# SQL queries
sql_main_table_hash_check: str = """ SELECT COUNT(*) FROM main WHERE file_hash = ? """
sql_main_table: str = """ INSERT INTO main (log_date, file_hash, log_message) VALUES (?, ?, ?); """
sql_updates_table: str = """ INSERT INTO updates (update_date, update_product, update_target, update_link, file_hash) 
VALUES (?, ?, ?, ?, ?); """
sql_get_updates: str = """SELECT update_date, update_product, update_target, update_link FROM updates ORDER BY 
update_id DESC;"""
sql_get_updates_count: str = """ SELECT count(update_date) FROM updates WHERE update_date = ?; """
sql_get_last_updates: str = """SELECT update_date, update_product, update_target, update_link FROM updates WHERE 
update_date = ?;"""
sql_get_last_update_date: str = """ SELECT update_date FROM updates ORDER BY update_id DESC LIMIT 1; """
sql_get_update_dates: str = """ SELECT DISTINCT update_date FROM updates ORDER BY update_id DESC; """
sql_get_date_update: str = """SELECT update_date, update_product, update_target, update_link FROM updates WHERE 
update_date = ? ORDER BY update_id DESC;"""
sql_empty_database: str = """SELECT COUNT(*) FROM main;"""


def get_config(local_path):
    init_file = f"{local_path}/init.json"
    config_file = f"{local_path}/config.json"
    log_file = f"{local_path}/asu-notifier.log"
    db_file = f"{local_path}/asu-notifier.db"

    init = open(init_file, 'r')
    init_data = json.loads(init.read())
    apple_url = init_data['apple_url']

    config = open(config_file, 'r')
    config_data = json.loads(config.read())
    timezone = config_data['timezone']
    localtime = pytz.timezone(timezone)
    bot_token = config_data['bot_token']
    channels = config_data['channels']
    return apple_url, db_file, log_file, localtime, bot_token, channels

def create_connection(file):
    if not os.path.isfile(file):
        logging.info(f'\'{file}\' database created.')
    conn = TypeVar('conn', Connection, None)
    try:
        conn: Connection = sqlite3.connect(file)
    except Error as error:
        logging.error(str(error))
    return conn

def get_updates(conn, full_update, apple_url, localtime):
    recent_updates = []
    cursor = conn.cursor()
    response = requests.get(apple_url)
    content = response.content
    file_hash = hashlib.sha256(content).hexdigest()
    available_updates = cursor.execute(sql_main_table_hash_check, [file_hash]).fetchone()[0] < 1
    if not available_updates:
        logging.info('No updates available.')
        conn.close()
        return False, recent_updates
    else:
        recent_updates = populate_tables(conn, content, file_hash, full_update, localtime)
        conn.close()
        return True, recent_updates

def populate_tables(conn, content, file_hash, full_update, localtime):
    log_date = datetime.now(tz=localtime)
    populate_main_table(conn, log_date, file_hash, full_update)
    return populate_updates_table(conn, file_hash, content, full_update)

def populate_main_table(conn, log_date, file_hash, full_update):
    cursor = conn.cursor()
    if full_update:
        log_message = f'First \'main\' table population - SHA256: {file_hash}.'
    else:
        log_message = f'\'main\' table updated - SHA256: {file_hash}.'
    cursor.execute(sql_main_table, (log_date, file_hash, log_message))
    logging.info(log_message)
    conn.commit()

def populate_updates_table(conn, file_hash, content, full_update):
    cursor = conn.cursor()
    soup = BeautifulSoup(content, 'html.parser')
    updates_table = soup.find('div', id="tableWraper").find_all('tr')
    recent_updates = formatted_content(updates_table)
    if full_update:
        log_message = f'First \'updates\' table population - SHA256: {file_hash}.'
    else:
        log_message = f'\'updates\' table updated - SHA256: {file_hash}.'
        query = cursor.execute(sql_get_updates).fetchall()
        old_updates = [list(t) for t in query]
        for element in old_updates:
            recent_updates.remove(element)
    for element in reversed(recent_updates):
        cursor.execute(sql_updates_table, (element[0], element[1], element[2], element[3], file_hash))
    logging.info(log_message)
    conn.commit()
    return recent_updates

def formatted_content(content):
    content_list = []
    for i, row in enumerate(content):
        if i == 0:
            continue
        columns = row.find_all('td')
        date_str = columns[2].get_text().strip().replace('\xa0', ' ')
        update_date = check_date(date_str)
        update_product = columns[0].get_text().strip().replace(
            'Esta actualización no tiene ninguna entrada de CVE publicada.', '').replace('\xa0', ' ').replace('\n', '')
        update_target = columns[1].get_text().replace('\xa0', ' ').replace('\n', '')
        try:
            update_link = columns[0].find('a')['href']
        except Exception:
            update_link = None
        element = [update_date, update_product, update_target, update_link]
        content_list.append(element)
    return content_list

def check_date(date_str):
    pattern = r'(\d{1,2}) de (\w+) de (\d{4})'
    try:
        match = re.match(pattern, date_str)
        day = int(match[1])
        month = match[2]
        year = int(match[3])
        month_list = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
                      'noviembre', 'diciembre']
        month_num = month_list.index(month) + 1
        return datetime(year, month_num, day)
    except Exception:
        return date_str

def apprise_notification(conn, updates, full_update, bot_token, channels):
    apprise_object = Apprise()
    apprise_message = build_message(conn, updates, full_update)
    apprise_syntax = f'tgram://{bot_token}/'
    for channel in channels:
        apprise_syntax += f'{channel}/'
    apprise_syntax += '?format=markdown'
    apprise_object.add(apprise_syntax, tag='telegram')
    apprise_object.notify(apprise_message, tag="telegram")

def build_message(conn, last_updates, full_update):
    max_updates = 5
    cursor = conn.cursor()
    if full_update:
        last_updates = []
        update_dates = cursor.execute(sql_get_update_dates).fetchall()
        for index, element in enumerate(update_dates):
            if max_updates > 0:
                value = element[index]
                query = cursor.execute(sql_get_date_update, value).fetchall()
                query_count = cursor.execute(sql_get_updates_count, value).fetchone()[0]
                updates = [list(t) for t in query]
                last_updates += updates
                max_updates -= query_count
        apprise_message = '*Últimas actualizaciones de Apple.*\n\n'
    else:
        apprise_message = '*Nuevas actualizaciones de Apple.*\n\n'
    for element in last_updates:
        if element[0] == 'Preinstalado':
            date_time = element[0]
        else:
            date = datetime.strptime(str(element[0]), "%Y-%m-%d %H:%M:%S")
            date_time = date.strftime("%d/%m/%Y")
        apprise_message += f'_{date_time}_'
        if element[3] is not None:
            apprise_message += f' - [{element[1]}]({element[3]})'
        else:
            apprise_message += f' - _{element[1]}_'
        apprise_message += f' - {element[2]}\n'
    return apprise_message

def main():
    local_file = __file__
    local_path = os.path.dirname(local_file)
    apple_url, db_file, log_file, localtime, bot_token, channels = get_config(local_path)

    # logging
    log_format = '%(asctime)s -- %(message)s'
    logging.basicConfig(filename=log_file, encoding='utf-8', format=log_format, level=logging.INFO)

    # check if database is empty or not
    conn: Connection = create_connection(db_file)
    full_update = conn.cursor().execute(sql_empty_database).fetchone()[0] == 0

    # run first database update
    updates_check, updates = get_updates(conn, full_update, apple_url, localtime)

    # run notifications
    if updates_check:
        apprise_notification(conn, updates, full_update, bot_token, channels)

if __name__ == '__main__':
    main()
