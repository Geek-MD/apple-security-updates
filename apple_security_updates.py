#!/usr/bin/env python

# Apple Updates v0.1.0
# Python script that checks for Apple software updates, and notifies via a Telegram Bot.

import contextlib
import datetime
import hashlib
import pytz
import sqlite3
import logging
import requests
import urllib.request
import re
import os.path
import numpy
from datetime import datetime
from sqlite3 import Error, Connection
from typing import TypeVar
from bs4 import BeautifulSoup
from numpy import ndarray

# global variables
timezone = pytz.timezone('America/Santiago')
time = datetime.now(tz=timezone)
search_url = 'https://www.apple.com/us/search/apple-security-updates?src=globalnav'
language = 'es-cl'
db_file = r'apple_security_updates.db'
log_file = r'apple_security_updates.log'

# logging
log_format = '%(asctime)s -- %(message)s'
logging.basicConfig(filename=log_file, encoding='utf-8', format=log_format, level=logging.INFO)

# SQL queries
sql_create_main_table: str = """CREATE TABLE main ( main_id integer PRIMARY KEY AUTOINCREMENT, log_date text NOT 
NULL, file_hash text NOT NULL, log_message text NOT NULL ); """
sql_create_updates_table: str = """CREATE TABLE updates ( table_id integer PRIMARY KEY AUTOINCREMENT, update_date 
text NOT NULL, update_product text NOT NULL, update_target text NOT NULL, update_link text, main_id integer NOT NULL, 
FOREIGN KEY (main_id) REFERENCES main (main_id) ); """
sql_main_table: str = """ INSERT INTO main (log_date, file_hash, log_message) VALUES (?, ?, ?); """
sql_updates_table: str = """INSERT INTO updates (update_date, update_product, update_target, update_link, main_id) 
VALUES (?, ?, ?, ?, ?); """

def get_apple_updates_url(search_url, language):
    response = requests.get(search_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    update_link = soup.select_one('a[href*="support.apple.com/en-us/HT"]')['href']
    filename = os.path.basename(update_link)
    return f'http://support.apple.com/{language}/{filename}'

def create_connection(file):
    if not os.path.isfile(file):
        logging.info(f'\'{file}\' database created.')
    conn = TypeVar('conn', Connection, None)
    try:
        conn: Connection = sqlite3.connect(file)
    except Error as error:
        logging.error(str(error))
    return conn

def create_table(conn, sql_create_table, table_name):
    with contextlib.suppress(Error):
        try:
            conn.cursor().execute(sql_create_table)
            logging.info(f'\'{table_name}\' table created.')
        except Error as error:
            logging.error(str(error))

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

def first_population(conn, url):
    cursor = conn.cursor()
    log_date = datetime.now(tz=timezone)
    log_message = 'First database population.'
    recent_updates = check_updates(url)
    file_hash = check_hash(url)
    cursor.execute(sql_main_table, (log_date, file_hash, log_message))
    logging.info(log_message)
    cursor.execute("SELECT main_id FROM main ORDER BY main_id DESC LIMIT 1")
    main_id = cursor.fetchone()[0]
    for i, row in enumerate(recent_updates):
        if i == 0:
            continue
        columns = row.find_all('td')
        date_str = columns[2].get_text().strip().replace('\xa0', ' ')
        update_date = check_date(date_str)
        update_product = columns[0].get_text()
        update_target = columns[1].get_text()
        try:
            update_link = columns[0].find('a')['href']
        except Exception:
            update_link = None
        cursor.execute(sql_updates_table, (update_date, update_product, update_target, update_link, main_id))

def table_update(conn, url):
    cursor = conn.cursor()
    file_hash = check_hash(url)
    cursor.execute(f"SELECT COUNT(*) FROM main WHERE file_hash = '{file_hash}'")
    query = cursor.fetchone()[0]
    if query != 0:
        logging.info('No updates available.')
    else:
        table_population(conn, url, file_hash)
        telegram_bot_notification(conn, file_hash)

def table_population(conn, url, file_hash):
    cursor = conn.cursor()
    log_date = datetime.now(tz=timezone)
    log_message = f'\'{file_hash}\' update.'
    recent_updates = check_updates(url)
    updates_diff = check_updates_diff(conn, recent_updates)
    cursor.execute(sql_main_table, (log_date, file_hash, log_message))
    logging.info(log_message)
    cursor.execute("SELECT main_id FROM main ORDER BY main_id DESC LIMIT 1")
    main_id = cursor.fetchone()[0]
    for array_element in updates_diff:
        update_date = array_element[0]
        update_product = array_element[1]
        update_target = array_element[2]
        update_link = array_element[3]
        cursor.execute(sql_updates_table, (update_date, update_product, update_target, update_link, main_id))

# noinspection PyTypeChecker
def check_updates_diff(conn, recent_updates):
    cursor = conn.cursor()
    cursor.execute("SELECT update_date, update_product, update_target, update_link FROM updates")
    query: object = cursor.fetchall()
    db_array: ndarray = numpy.array(list(query))
    updates_array = []
    for i, row in enumerate(recent_updates):
        if i == 0:
            continue
        columns = row.find_all('td')
        date_str = columns[2].get_text().strip().replace('\xa0', ' ')
        update_date = check_date(date_str)
        update_product = columns[0].get_text()
        update_target = columns[1].get_text()
        try:
            update_link = columns[0].find('a')['href']
        except Exception:
            update_link = None
        array_element = numpy.array([update_date, update_product, update_target, update_link])
        updates_array = numpy.append(updates_array, array_element)
    return updates_array - db_array

def check_hash(url):
    response = urllib.request.urlopen(url)
    content = response.read()
    return hashlib.sha256(content).hexdigest()

def make_soup(url):
    response = requests.get(url)
    return BeautifulSoup(response.content, 'html.parser')

def check_updates(url):
    soup = make_soup(url)
    updates_table = soup.find('div', id="tableWraper")
    return updates_table.find_all('tr')

def telegram_bot_notification(conn, file_hash):
    pass

def main():
    global apple_updates_url
    apple_updates_url = get_apple_updates_url(search_url, language)

    # create a database connection
    conn: Connection = create_connection(db_file)
    cursor = conn.cursor()

    table_check = cursor.execute("SELECT COUNT(name) FROM sqlite_master WHERE type='table' AND name='main'")

    if table_check.fetchone()[0] == 1:
        table_update(conn, apple_updates_url)
    else:
        # create database tables and populate them
        create_table(conn, sql_create_main_table, 'main')
        create_table(conn, sql_create_updates_table, 'updates')
        first_population(conn, apple_updates_url)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    main()
