#!/usr/bin/env python3
import argparse
import csv
import io
import sqlite3
from datetime import datetime, timedelta

import requests
import requests_ftp

requests_ftp.monkeypatch_session()

DB_FILE = './stockdata.sqlite'


class FTPScrape:
    def __init__(self, url):
        self.url = url
        self.session = requests.Session()
        self.file_list = []

    def get_file_list(self):
        res = self.session.nlst(self.url)
        self.file_list = res.text.split()
        return self.file_list

    def get_file(self, filename) -> bytes:
        res = self.session.get(f'{self.url}/{filename}')
        return res.text


def get_nasdaq_dict(url, filename):
    ftp_session = FTPScrape(url)
    data = ftp_session.get_file(filename)
    bd = io.StringIO(data)
    reader = csv.DictReader(bd, delimiter='|')
    return list(reader)


def create_sql_tbl(c):
    try:
        create_tbl = '''CREATE TABLE stocks (source text, date text, symbol text, short_vol int, short_exempt_vol int, total_vol int, market text, PRIMARY KEY(source, date,symbol,short_vol,market));'''
        c.execute(create_tbl)
    except sqlite3.OperationalError as e:
        pass


def date_to_iso(input):
    year = input[:4]
    month = input[4:6]
    day = input[6:]
    iso8601_date = f'{year}-{month}-{day}'
    return iso8601_date


def nasdaq_write_to_db(stock_data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    create_sql_tbl(c)

    for e in stock_data:
        iso8601_date = date_to_iso(e['DATE'])
        sql = f"INSERT OR REPLACE INTO stocks VALUES ('NASDAQ','{iso8601_date}', '{e['SYMBOL']}', '{e['SHORT VOLUME']}', '', '{e['TOTAL VOLUME']}','{e['MARKET']}')"
        c.execute(sql)
    conn.commit()
    conn.close()


def finra_write_to_db(stock_data):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    create_sql_tbl(c)

    for e in stock_data:
        iso8601_date = date_to_iso(e['Date'])
        sql = f"INSERT OR REPLACE INTO stocks VALUES ('FINRA', '{iso8601_date}', '{e['Symbol']}', '{e['ShortVolume']}', '{e['ShortExemptVolume']}', '{e['TotalVolume']}','{e['Market']}')"
        c.execute(sql)
    conn.commit()
    conn.close()


def get_finra_dict(year, month, day):
    url = f'http://regsho.finra.org/CNMSshvol{year:}{month:02d}{day:02d}.txt'
    req = requests.get(url)
    if req.status_code == 200:
        bd = io.StringIO(req.text)
        reader = csv.DictReader(bd, delimiter='|')
        return list(reader)
    return []


if __name__ == '__main__':
    nasdaq_psx_url = 'ftp://ftp.nasdaqtrader.com/files/shortsaledata/daily/psx'
    nasdaq_bx_url = 'ftp://ftp.nasdaqtrader.com/files/shortsaledata/daily/bx'

    parser = argparse.ArgumentParser(description='Put together some charts!!!')
    parser.add_argument('-d', '--days', default=2, type=int, help='get data from the last x number of days')
    args = parser.parse_args()

    last_x_days = args.days

    for single_date in (datetime.today() - timedelta(days=n) for n in range(last_x_days)):
        # If this date is a weekend, then don't bother
        if single_date.weekday() > 4:
            continue

        print(single_date)
        year = single_date.year
        month = single_date.month
        day = single_date.day

        print(f'Processing: {year:}{month:02d}{day:02d}')
        file_name = f'NPSXshvol{year:}{month:02d}{day:02d}.txt'
        data = get_nasdaq_dict(nasdaq_psx_url, file_name)
        print(f'PSX, {len(data)}')
        nasdaq_write_to_db(data)

        file_name = f'NQBXshvol{year}{month:02d}{day:02d}.txt'
        data = get_nasdaq_dict(nasdaq_bx_url, file_name)
        print(f'BX, {len(data)}')
        nasdaq_write_to_db(data)

        data = get_finra_dict(year, month, day)
        print(f'FINRA, {len(data)}')
        finra_write_to_db(data)
