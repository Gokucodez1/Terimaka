import random
import string
import sqlite3
import requests
from bitcoinlib.wallets import Wallet
from datetime import datetime

# Database setup
conn = sqlite3.connect('deals.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS deals
                 (channel_id INT PRIMARY KEY,
                  deal_code TEXT,
                  sender_id INT,
                  receiver_id INT,
                  amount_ltc REAL,
                  amount_usd REAL,
                  start_time TEXT,
                  status TEXT)''')
conn.commit()

def generate_deal_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

def validate_amount(input_str):
    try:
        amount = float(input_str.replace('$', '').strip())
        return amount if amount >= 0.1 else None
    except ValueError:
        return None

def get_live_rate():
    response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd")
    return response.json()["litecoin"]["usd"]

def get_ltc_address():
    with open('ltcaddy.txt') as f:
        return f.read().strip()

def get_wif_key():
    with open('wifkey.txt') as f:
        return f.read().strip()

def validate_ltc_address(address):
    return address.startswith(('L', 'M', 'ltc1')) and 26 <= len(address) <= 48

def save_deal(channel_id, deal_data):
    cursor.execute('''INSERT OR REPLACE INTO deals VALUES 
                     (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (channel_id, *deal_data))
    conn.commit()

def load_deal(channel_id):
    cursor.execute("SELECT * FROM deals WHERE channel_id=?", (channel_id,))
    return cursor.fetchone()

def send_ltc(receiver, amount):
    wallet = Wallet.import_key("escrow_bot", get_wif_key(), network='litecoin')
    tx = wallet.send_to(receiver, amount, fee=0.0001)
    return tx.txid
