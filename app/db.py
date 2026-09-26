import json
import sqlite3
from contextlib import contextmanager
from app import config
from app.data.seed import PRODUCTS, CUSTOMERS

@contextmanager
def connection(write=False):
    db = sqlite3.connect(config.DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        if write:
            db.execute('BEGIN IMMEDIATE')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def initialize():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS products(
          id TEXT PRIMARY KEY, brand TEXT, name TEXT, category TEXT, pack_size TEXT,
          pack_amount INTEGER, mrp INTEGER, unit_price INTEGER, carton_units INTEGER,
          stock INTEGER CHECK(stock>=0), aliases TEXT, demo_stock INTEGER CHECK(demo_stock>=0));
        CREATE TABLE IF NOT EXISTS customers(
          id TEXT PRIMARY KEY,name TEXT,city TEXT,phone TEXT UNIQUE,language TEXT,language_label TEXT,initials TEXT);
        CREATE TABLE IF NOT EXISTS orders(
          id TEXT PRIMARY KEY, customer_id TEXT REFERENCES customers(id),state TEXT,
          created_at TEXT,delivery_date TEXT,revision INTEGER DEFAULT 0,
          sales_number TEXT UNIQUE, notification TEXT,mode TEXT,
          confirmation_text TEXT,confirmation_revision INTEGER);
        CREATE TABLE IF NOT EXISTS items(
          order_id TEXT REFERENCES orders(id),product_id TEXT REFERENCES products(id),
          quantity INTEGER CHECK(quantity>0),carton_price INTEGER,
          PRIMARY KEY(order_id,product_id));
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,order_id TEXT REFERENCES orders(id),
          action TEXT,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS turns(
          order_id TEXT,request_id TEXT,response TEXT,PRIMARY KEY(order_id,request_id));
        CREATE TABLE IF NOT EXISTS sequence(id INTEGER PRIMARY KEY CHECK(id=1),value INTEGER);
        INSERT OR IGNORE INTO sequence VALUES(1,1027);
        ''')
        for p in PRODUCTS:
            row = list(p)
            row[6] = round(row[6]*100)
            row[7] = round(row[7]*100)
            row[-1] = json.dumps(row[-1],ensure_ascii=False)
            row.append(row[9])
            db.execute('INSERT OR IGNORE INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',row)
        db.executemany('INSERT OR IGNORE INTO customers VALUES(?,?,?,?,?,?,?)',CUSTOMERS)
