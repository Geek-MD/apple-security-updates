#!/usr/bin/env python3

# Apple Security Updates Notifier v0.4.3
# File: asu-bot.py
# Description: Secondary component of Apple Security Updates Notifier, which will run hourly and notify via Telegram any
# new security update.

import hashlib
import json
import logging
import os
import os.path
import re
import sqlite3
from sqlite3 import Error, Connection
from typing import TypeVar

import pytz
import requests
from apprise import Apprise
from bs4 import BeautifulSoup

# set global variables
global apple_url, db_file, log_file, localtime, bot_token, chat_ids

# SQL queries
sql_check_empty_table = """ SELECT COUNT(*) FROM main; """
sql_last_hash: str = """ SELECT file_hash FROM main ORDER BY main_id DESC LIMIT 1; """
sql_last_publish_date: str = """ SELECT publish_date FROM main ORDER BY main_id DESC LIMIT 1; """
sql_main_table: str = """ INSERT INTO main (publish_date, file_hash, log_message) VALUES (?, ?, ?); """
sql_updates_table: str = """ INSERT INTO updates (update_date, update_product, update_target, update_link, file_hash) 
VALUES (?, ?, ?, ?, ?); """
sql_get_updates: str = """SELECT update_date, update_product, update_target, update_link FROM updates ORDER BY 
update_id DESC;"""
sql_get_update_dates: str = """ SELECT DISTINCT update_date FROM updates ORDER BY update_id DESC LIMIT 5; """
sql_get_date_updates: str = """SELECT update_date, update_product, update_target, update_link FROM updates WHERE 
update_date = ? ORDER BY update_id DESC;"""

def get_config(local_path):
    global apple_url, db_file, log_file, localtime, bot_token, chat_ids
    config = open(f'{local_path}/config.json', 'r')
    data = json.loads(config.read())
    apple_url = data['apple_url']
    db_file = data['db_file']
    log_file = data['log_file']
    timezone = data['timezone']
    localtime = pytz.timezone(timezone)
    bot_token = data['bot_token']
    chat_ids = data['chat_ids']

def create_connection(file):
    if not os.path.isfile(file):
        logging.info(f'\'{file}\' database created.')
    conn = TypeVar('conn', Connection, None)
    try:
        conn: Connection = sqlite3.connect(file)
    except Error as error:
        logging.error(str(error))
    return conn

def page_scrape(url, conn):
    response = requests.get(url)
    content = response.content
    soup = BeautifulSoup(content, 'html.parser')
    publish_date = soup.find('div', {'class': 'mod-date'}).time['datetime']
    file_hash = hashlib.sha256(content).hexdigest()
    check_content(content, publish_date, file_hash, conn)

def check_content(content, publish_date, file_hash, conn):
    cursor = conn.cursor()
    count = cursor.execute(sql_check_empty_table).fetchone()[0]
    if count == 0:
        update_databases(conn, content, publish_date, file_hash, full_update=True)
    else:
        query_hash = cursor.execute(sql_last_hash).fetchone()[0]
        query_date = cursor.execute(sql_last_publish_date).fetchone()[0]
        if query_hash == file_hash and query_date == publish_date:
            logging.info('No updates available.')
            exit()
        elif query_hash != file_hash and query_date == publish_date:
            logging.info('No updates available but, there are differences in file hash. Check url for eventual changes.')
            exit()
        else:
            update_databases(conn, content, publish_date, file_hash, full_update=False)

def update_databases(conn, content, publish_date, file_hash, full_update):
    main_database_update(conn, publish_date, file_hash, full_update)
    updates_database_update(conn, content, file_hash, full_update)
    conn.close()

def main_database_update(conn, publish_date, file_hash, full_update):
    cursor = conn.cursor()
    if full_update:
        log_message = f'\'main\' table first update - SHA256: {file_hash}.'
    else:
        log_message = f'\'main\' table updated - SHA256: {file_hash}.'
    cursor.execute(sql_main_table, (publish_date, file_hash, log_message))
    logging.info(log_message)
    conn.commit()

def updates_database_update(conn, content, file_hash, full_update):
    cursor = conn.cursor()
    soup = BeautifulSoup(content, 'html.parser')
    content_updates = soup.find('div', id="tableWraper").find_all('tr')
    updates = updates_scrape(content_updates)
    new_updates = check_updates(cursor, updates)
    if new_updates != 'None' or full_update:
        if full_update:
            log_message = f'\'updates\' table first update - SHA256: {file_hash}.'
            new_updates = updates
        else:
            log_message = f'\'updates\' table updated - SHA256: {file_hash}.'
        for element in reversed(new_updates):
            cursor.execute(sql_updates_table, (element[0], element[1], element[2], element[3], file_hash))
        conn.commit()
        logging.info(log_message)
        apprise_notification(conn, new_updates, full_update)
        conn.commit()

def check_updates(cursor, latest_updates):
    existing_updates = cursor.execute(sql_get_updates).fetchall()
    new_updates = []
    for update in latest_updates:
        if tuple(update) not in existing_updates:
            new_updates.append(update)
    return new_updates

def updates_scrape(content_updates):
    updates = []
    for row in content_updates[1:]:
        columns = row.find_all('td')
        update_link = columns[0].find('a')['href'] if columns[0].find('a') else None
        product_name = columns[0].get_text().strip().replace('Esta actualización no tiene entradas de CVE publicadas.',
                                                             '').replace('\xa0', ' ').replace('\n', '')
        update_target = columns[1].get_text().strip().replace('\xa0', ' ').replace('\n', '')
        date_str = columns[2].get_text().strip().replace('\xa0', ' ').replace('\n', '')
        if date_str == 'Preinstalado':
            update_date = date_str
        else:
            update_date = check_date(date_str)
        updates_row = (update_date, product_name, update_target, update_link)
        updates.append(updates_row)
    return updates

def check_date(date_str):
    pattern = r'(\d{1,2}) de (\w+) de (\d{4})'
    match = re.match(pattern, date_str)
    if not match:
        raise ValueError(f"Invalid date format: {date_str}")
    day, month, year = match.groups()
    month_list = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
                  'noviembre', 'diciembre']
    try:
        month_num = month_list.index(month.lower()) + 1
    except ValueError:
        raise ValueError(f"Invalid month name: {month}")
    new_date = f'{year}-{str(month_num).zfill(2)}-{str(day).zfill(2)}'
    return new_date

def apprise_notification(conn, updates, full_update):
    apprise_object = Apprise()
    apprise_message = build_message(conn, updates, full_update)
    apprise_syntax = f'tgram://{bot_token}/'
    for chat_id in chat_ids:
        apprise_syntax += f'{chat_id}/'
    apprise_syntax += '?format=markdown'
    apprise_object.add(apprise_syntax, tag='telegram')
    apprise_object.notify(apprise_message, tag="telegram")

def build_message(conn, updates, full_update):
    cursor = conn.cursor()
    last_updates = []
    if full_update:
        update_dates = cursor.execute(sql_get_update_dates).fetchall()
        for date in update_dates:
            query = cursor.execute(sql_get_date_updates, date).fetchall()
            last_updates += query
        apprise_message = '*Últimas actualizaciones de Apple*\n\n'
    else:
        apprise_message = '*Nuevas actualizaciones de Apple*\n\n'
        last_updates = updates
    for element in last_updates:
        date_time = encode_telegram_markdown(element[0])
        update_product = encode_telegram_markdown(element[1])
        update_target = encode_telegram_markdown(element[2])
        update_link = encode_telegram_markdown(element[3])
        apprise_message += f'_{date_time}_'
        if update_link is not None:
            apprise_message += f' \- [{update_product}]({update_link})'
        else:
            apprise_message += f' \- _{update_product}_'
        apprise_message += f' \- {update_target}\n\n'
    return apprise_message

def encode_telegram_markdown(text):
    if text is None:
        return None
    reserved_chars = ['%', '&', '#', '?', ' ', '/', '@', '+', ',', ':', '-', '.', '(', ')']
    replace_chars = ['\%', '\&', '\#', '\?', '\ ', '\/', '\@', '\+', '\,', '\:', '\-', '\.', '\(', '\)']
    encoded_text = text
    for char, replace_char in zip(reserved_chars, replace_chars):
        if encoded_text is not None and char in encoded_text:
            encoded_text = encoded_text.replace(char, replace_char)
    return encoded_text

def main():
    local_file = __file__
    local_path = os.path.dirname(local_file)
    get_config(local_path)

    log_format = '%(asctime)s -- %(message)s'
    logging.basicConfig(filename=log_file, encoding='utf-8', format=log_format, level=logging.INFO)

    conn: Connection = create_connection(db_file)

    page_scrape(apple_url, conn)

if __name__ == '__main__':
    main()
