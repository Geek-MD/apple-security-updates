#!/usr/bin/env python3

# Apple Security Updates Notifier v0.4.1
# Python script that checks for Apple software updates, and notifies via Telegram Bot.
# This is a first workaround attempt for a permanent bot in the near future.

import contextlib
import datetime
import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime
from sqlite3 import Error, Connection
from typing import TypeVar

import pytz
import requests
import schedule
from apprise import Apprise
from bs4 import BeautifulSoup

working_dir = os.getcwd()
os.chdir(working_dir)

# set global variables
global apple_url, db_file, log_file, localtime, bot_token, chat_ids

# SQL queries
sql_check_empty_database: str = """ SELECT COUNT(name) FROM sqlite_master WHERE type='table' AND name='main' """
sql_create_main_table: str = """ CREATE TABLE IF NOT EXISTS main ( main_id integer PRIMARY KEY AUTOINCREMENT, log_date text NOT 
NULL, file_hash text NOT NULL, log_message text NOT NULL ); """
sql_create_updates_table: str = """ CREATE TABLE IF NOT EXISTS updates ( update_id integer PRIMARY KEY AUTOINCREMENT, update_date 
text NOT NULL, update_product text NOT NULL, update_target text NOT NULL, update_link text, file_hash text NOT NULL ); """
sql_main_table_hash_check: str = """ SELECT COUNT(*) FROM main WHERE file_hash = ? """
sql_main_table: str = """ INSERT INTO main (log_date, file_hash, log_message) VALUES (?, ?, ?); """
sql_updates_table: str = """ INSERT INTO updates (update_date, update_product, update_target, update_link, file_hash) 
VALUES (?, ?, ?, ?, ?); """
sql_get_updates: str = """ SELECT update_date, update_product, update_target, update_link FROM updates ORDER BY update_id ASC; """
sql_get_updates_count: str = """ SELECT count(update_date) FROM updates WHERE update_date = ?; """
sql_get_last_updates: str = """ SELECT update_date, update_product, update_target, update_link FROM updates WHERE update_date = ?; """
sql_get_last_update_date: str = """ SELECT update_date FROM updates ORDER BY update_id DESC LIMIT 1; """
sql_get_update_dates: str = """ SELECT DISTINCT update_date FROM updates; """
sql_get_date_update: str = """ SELECT update_date, update_product, update_target, update_link FROM updates WHERE update_date = ?; """

def get_config():
    global apple_url, db_file, log_file, localtime, bot_token, chat_ids
    config = open('config.json', 'r')
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

def create_table(conn, sql_create_table, table_name, file):
    with contextlib.suppress(Error):
        try:
            conn.cursor().execute(sql_create_table)
            logging.info(f'\'{file}\' - \'{table_name}\' table created.')
        except Error as error:
            logging.error(str(error))

def get_updates(conn, full_update):
    cursor = conn.cursor()
    response = requests.get(apple_url)
    content = response.content
    file_hash = hashlib.sha256(content).hexdigest()
    available_updates = cursor.execute(sql_main_table_hash_check, [file_hash]).fetchone()[0] < 1
    if not available_updates:
        logging.info('No updates available.')
    else:
        update_databases(conn, content, file_hash, full_update)
    conn.commit()
    conn.close()

def update_databases(conn, content, file_hash, full_update):
    log_date = datetime.now(tz=localtime)
    update_main_database(conn, log_date, file_hash, full_update)
    update_updates_database(conn, file_hash, content, full_update)

def update_main_database(conn, log_date, file_hash, full_update):
    cursor = conn.cursor()
    if full_update:
        log_message = f'First \'main\' table population - SHA256: {file_hash}.'
    else:
        log_message = f'\'main\' table updated - SHA256: {file_hash}.'
    cursor.execute(sql_main_table, (log_date, file_hash, log_message))
    logging.info(log_message)
    conn.commit()

def update_updates_database(conn, file_hash, content, full_update):
    cursor = conn.cursor()
    soup = BeautifulSoup(content, 'html.parser')
    updates_table = soup.find('div', id="tableWraper").find_all('tr')
    recent_updates = formatted_content(updates_table)
    if full_update:
        log_message = f'First \'updates\' table population - SHA256: {file_hash}.'
    else:
        log_message = f'\'updates\' table updated - SHA256: {file_hash}.'
        old_updates = cursor.execute(sql_get_updates).fetchall()
        for element in old_updates:
            recent_updates.remove(element)
    recent_updates.reverse()
    for element in recent_updates:
        cursor.execute(sql_updates_table, (element[0], element[1], element[2], element[3], file_hash))
    logging.info(log_message)
    conn.commit()
    apprise_notification(conn, recent_updates, full_update)

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
        list_element = [update_date, update_product, update_target, update_link]
        content_list.append(list_element)
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

def apprise_notification(conn, updates, full_update):
    apprise_object = Apprise()
    apprise_message = build_message(conn, updates, full_update)
    apprise_syntax = f'tgram://{bot_token}/'
    for chat_id in chat_ids:
        apprise_syntax += f'{chat_id}/'
    apprise_syntax *= '?format=markdown'
    apprise_object.add(apprise_syntax, tag='telegram')
    apprise_object.notify(apprise_message, tag="telegram")

def build_message(conn, last_updates, full_update):
    max_updates = 5
    cursor = conn.cursor()
    if full_update:
        last_updates = []
        update_dates = cursor.execute(sql_get_update_dates).fetchall()
        for element in reversed(update_dates):
            if max_updates >= 0:
                query = cursor.execute(sql_get_date_update, element).fetchall()
                query_count = cursor.execute(sql_get_updates_count, element).fetchone()[0]
                last_updates += query
                max_updates -= query_count
        apprise_message = '*Últimas actualizaciones de Apple.*\n\n'
    else:
        apprise_message = '*Nuevas actualizaciones de Apple.*\n\n'
    for element in reversed(last_updates):
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
    get_config()

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

    # run first database update
    get_updates(conn, full_update=True)

    # Schedule the function to run every hour
    schedule.every().hour.do(get_updates, conn=conn, full_update=False)

    # Run the scheduler continuously
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()