import json
import logging
import re
from app.db import connection

log = logging.getLogger('bolorder')

def catalog(mode='live'):
    with connection() as db:
        result = [dict(r) for r in db.execute('SELECT * FROM products ORDER BY rowid')]
    for p in result:
        if mode=='demo':
            p['stock']=p['demo_stock']
        p.pop('demo_stock',None)
        p['aliases'] = json.loads(p['aliases'])
        p['carton_price'] = p['unit_price'] * p['carton_units']
        p['sku'] = p['id']
    return result

def identify_customer(phone_number=None,customer_name=None):
    with connection() as db:
        rows = [dict(r) for r in db.execute('SELECT * FROM customers')]
    for c in rows:
        if (phone_number and c['phone']==phone_number) or (customer_name and c['name'].casefold()==customer_name.casefold()):
            return c
    raise ValueError('Retailer not found. Select a retailer from the customer list.')

def get_product(product_id,mode='live'):
    product = next((p for p in catalog(mode) if p['id']==product_id),None)
    if not product:
        raise ValueError('That product is not in the catalog. Please clarify the brand and pack size.')
    return product

def search_products(query,mode='live'):
    query = re.sub(r'[^\w\s]',' ',query.casefold()).strip()
    ranked=[]
    for p in catalog(mode):
        terms=[p['name'],p['brand'],p['pack_size'],*p['aliases']]
        scores=[]
        for term in terms:
            term = re.sub(r'[^\w\s]',' ',term.casefold()).strip()
            scores.append(1.0 if query==term else len(set(query.split()) & set(term.split())) / max(len(set(query.split())),len(set(term.split())),1))
        score=max(scores)
        if score>=0.3:
            ranked.append({**p,'confidence':round(score,2)})
    return sorted(ranked,key=lambda p:-p['confidence'])[:5]

def check_inventory(product_id,requested_quantity,mode='live'):
    p=get_product(product_id,mode)
    log.info('inventory lookup sku=%s requested=%s available=%s',product_id,requested_quantity,p['stock'])
    return {'product_id':product_id,'requested':requested_quantity,'available':p['stock'],'shortage':max(0,requested_quantity-p['stock'])}

def find_alternatives(product_id,requested_quantity,category=None,approximate_price_range=None,pack_size=None,mode='live'):
    p=get_product(product_id,mode)
    candidates=[x for x in catalog(mode) if x['id']!=product_id and x['category']==p['category'] and x['stock']>=requested_quantity]
    for x in candidates:
        x['rank_score']=round(abs(x['pack_amount']-p['pack_amount'])/p['pack_amount']*2+abs(x['unit_price']-p['unit_price'])/p['unit_price'],3)
    log.info('alternative search sku=%s quantity=%s',product_id,requested_quantity)
    return sorted(candidates,key=lambda x:x['rank_score'])[:3]
