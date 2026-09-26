import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from app.db import connection
from app.models import ItemUpdate
from app.services.inventory_service import check_inventory, find_alternatives

log=logging.getLogger('bolorder')
IST=timezone(timedelta(hours=5,minutes=30))
FINAL={'CONFIRMED','INVENTORY_RESERVED','COMPLETED','CANCELLED'}

def now():
    return datetime.now(IST)

def event(db,order_id,action,detail):
    db.execute('INSERT INTO events(order_id,action,detail) VALUES(?,?,?)',(order_id,action,detail))
    log.info('%s order=%s %s',action,order_id,detail)

def create_draft_order(customer_id,mode='live',request_id=None):
    order_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'bolorder:'+request_id)) if request_id else str(uuid.uuid4())
    with connection(True) as db:
        old=db.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
        if old:
            if old['customer_id']!=customer_id or old['mode']!=mode:
                raise ValueError('This request identifier belongs to a different order.')
        else:
            if not db.execute('SELECT 1 FROM customers WHERE id=?',(customer_id,)).fetchone():
                raise ValueError('Retailer not found. Choose a retailer to start.')
            db.execute('INSERT INTO orders(id,customer_id,state,created_at,delivery_date,mode) VALUES(?,?,?,?,?,?)',
                       (order_id,customer_id,'DRAFT',now().isoformat(),(now()+timedelta(days=1)).date().isoformat(),mode))
            event(db,order_id,'Customer identified','Retailer selected; draft opened')
    return get_order(order_id)

def get_order(order_id):
    with connection() as db:
        row=db.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
        if not row:
            raise ValueError('Order not found. Start a new order.')
        order=dict(row)
        order['customer']=dict(db.execute('SELECT * FROM customers WHERE id=?',(order['customer_id'],)).fetchone())
        stock_column='demo_stock' if order['mode']=='demo' else 'stock'
        order['items']=[dict(r) for r in db.execute(f'''SELECT i.*,p.name,p.brand,p.pack_size,p.carton_units,
            p.{stock_column} AS available,p.category FROM items i JOIN products p ON p.id=i.product_id WHERE order_id=? ORDER BY i.rowid''',(order_id,))]
        order['events']=[dict(r) for r in db.execute('SELECT action,detail,created_at FROM events WHERE order_id=? ORDER BY id',(order_id,))]
    total=0
    shortages=[]
    for item in order['items']:
        item['subtotal']=item['quantity']*item['carton_price']
        total+=item['subtotal']
        if order['state'] not in FINAL and item['quantity']>item['available']:
            missing=item['quantity']-item['available']
            shortages.append({**item,'shortage':missing,'alternatives':find_alternatives(item['product_id'],missing,mode=order['mode'])})
    order['total']=total
    order['cartons']=sum(i['quantity'] for i in order['items'])
    order['shortages']=shortages
    order['invoice_url']=f'/api/orders/{order_id}/invoice' if order['sales_number'] else None
    return order

def update_order_items(order_id,items,delivery_date=None,expected_revision=None):
    update=ItemUpdate(items=items,delivery_date=delivery_date)
    if len({i.product_id for i in update.items})!=len(update.items):
        raise ValueError('A product was repeated in the same update. Please state each quantity once.')
    if delivery_date:
        try:
            d=datetime.strptime(delivery_date,'%Y-%m-%d').date()
            if d<now().date() or d>(now()+timedelta(days=90)).date():
                raise ValueError()
        except ValueError:
            raise ValueError('Choose a delivery date between today and the next 90 days.')
    with connection(True) as db:
        order=db.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
        if not order:
            raise ValueError('Order not found.')
        if order['state'] in FINAL:
            raise ValueError('This order is closed. Start a new order to make changes.')
        if expected_revision is not None and order['revision']!=expected_revision:
            raise ValueError('The cart changed. Review the latest order before continuing.')
        for item in update.items:
            p=db.execute('SELECT * FROM products WHERE id=?',(item.product_id,)).fetchone()
            if not p:
                raise ValueError('Unknown product. Please clarify the brand and pack size.')
            if item.quantity==0:
                db.execute('DELETE FROM items WHERE order_id=? AND product_id=?',(order_id,item.product_id))
            else:
                db.execute('''INSERT INTO items VALUES(?,?,?,?) ON CONFLICT(order_id,product_id)
                    DO UPDATE SET quantity=excluded.quantity,carton_price=excluded.carton_price''',
                    (order_id,item.product_id,item.quantity,p['unit_price']*p['carton_units']))
        stock_column='demo_stock' if order['mode']=='demo' else 'stock'
        count=db.execute('SELECT COUNT(*) FROM items WHERE order_id=?',(order_id,)).fetchone()[0]
        short=db.execute(f'SELECT COUNT(*) FROM items i JOIN products p ON p.id=i.product_id WHERE order_id=? AND i.quantity>p.{stock_column}',(order_id,)).fetchone()[0]
        state='WAITING_FOR_CLARIFICATION' if short else ('READY_FOR_CONFIRMATION' if count else 'DRAFT')
        db.execute('UPDATE orders SET state=?,revision=revision+1,delivery_date=COALESCE(?,delivery_date) WHERE id=?',(state,delivery_date,order_id))
        event(db,order_id,'Cart updated',f'{len(update.items)} product quantities validated')
        event(db,order_id,'Inventory checked','Stock shortage detected' if short else 'All requested cartons available')
        if short:
            event(db,order_id,'Alternatives found','Same category, similar pack size and price; approval required')
    for item in update.items:
        check_inventory(item.product_id,item.quantity,order['mode'])
    return get_order(order_id)

def add_item_to_order(order_id,product_id,quantity):
    """Set absolute quantity (idempotent), not an unguarded increment."""
    return update_order_items(order_id,[{'product_id':product_id,'quantity':quantity}])

update_order_item=add_item_to_order

def calculate_order_total(order_id):
    order=get_order(order_id)
    return {'total':order['total'],'currency':'INR','unit':'paise','cartons':order['cartons']}

def reserve_inventory(order_id,db=None):
    """Only callable inside confirm_order's transaction; never exposed to an LLM."""
    if db is None:
        raise ValueError('Inventory can only be reserved during explicit order confirmation.')
    order=db.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
    if order['state']!='CONFIRMED':
        raise ValueError('Order must be confirmed before inventory is reserved.')
    column='demo_stock' if order['mode']=='demo' else 'stock'
    for item in db.execute('SELECT * FROM items WHERE order_id=?',(order_id,)).fetchall():
        result=db.execute(f'UPDATE products SET {column}={column}-? WHERE id=? AND {column}>=?',(item['quantity'],item['product_id'],item['quantity']))
        if result.rowcount!=1:
            raise ValueError('Stock changed while confirming. Review availability and try again.')
    db.execute("UPDATE orders SET state='INVENTORY_RESERVED' WHERE id=?",(order_id,))
    event(db,order_id,'INVENTORY_RESERVED','Inventory reserved in a single transaction')

def generate_order_confirmation(order_id):
    order=get_order(order_id)
    if not order['sales_number']:
        raise ValueError('Confirm the order before generating its document.')
    return {'url':order['invoice_url'],'title':'Order Confirmation'}

generate_proforma_invoice=generate_order_confirmation

def send_order_confirmation(order_id,db=None):
    """Local simulator: persist a message; never sends SMS, email or WhatsApp."""
    if db is None:
        order=get_order(order_id)
        if not order['notification']:
            raise ValueError('Confirmation has not completed yet.')
        return {'simulated':True,'message':order['notification']}
    row=db.execute('SELECT o.*,c.name FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.id=?',(order_id,)).fetchone()
    total=db.execute('SELECT SUM(quantity*carton_price) FROM items WHERE order_id=?',(order_id,)).fetchone()[0]
    message=f"{row['name']} — Order {row['sales_number']} confirmed. Delivery: {row['delivery_date']}. Amount: ₹{total/100:,.2f}."
    db.execute('UPDATE orders SET notification=? WHERE id=?',(message,order_id))
    event(db,order_id,'Notification simulated',message)
    return {'simulated':True,'message':message}

def confirm_order(order_id,expected_revision,confirmation_text,explicit=False):
    if not explicit:
        raise ValueError('Explicit retailer confirmation is required.')
    with connection(True) as db:
        order=db.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
        if not order:
            raise ValueError('Order not found.')
        if order['state']=='COMPLETED':
            pass  # An idempotent retry returns the original number and reservation.
        else:
            if order['state']!='READY_FOR_CONFIRMATION' or order['revision']!=expected_revision:
                raise ValueError('Review the latest cart and resolve shortages before confirming.')
            db.execute('UPDATE sequence SET value=value+1 WHERE id=1')
            number='SO-'+str(db.execute('SELECT value FROM sequence WHERE id=1').fetchone()[0])
            db.execute("UPDATE orders SET state='CONFIRMED',sales_number=?,confirmation_text=?,confirmation_revision=? WHERE id=?",
                       (number,confirmation_text,expected_revision,order_id))
            event(db,order_id,'CONFIRMED','Explicit retailer confirmation recorded; '+number+' created')
            reserve_inventory(order_id,db)
            event(db,order_id,'Document generated','Order confirmation and proforma view available')
            send_order_confirmation(order_id,db)
            db.execute("UPDATE orders SET state='COMPLETED' WHERE id=?",(order_id,))
            event(db,order_id,'COMPLETED','Order ready for fulfilment')
    return get_order(order_id)

def cancel_order(order_id):
    with connection(True) as db:
        row=db.execute('SELECT state FROM orders WHERE id=?',(order_id,)).fetchone()
        if not row or row['state'] in FINAL:
            raise ValueError('Only an open draft can be cancelled.')
        db.execute("UPDATE orders SET state='CANCELLED',revision=revision+1 WHERE id=?",(order_id,))
        event(db,order_id,'CANCELLED','Draft cancelled; no stock reserved')
    return get_order(order_id)

def reset_demo_stock():
    from app.data.seed import PRODUCTS
    with connection(True) as db:
        db.execute("UPDATE orders SET state='CANCELLED',revision=revision+1 WHERE mode='demo' AND state NOT IN ('COMPLETED','CANCELLED')")
        for p in PRODUCTS:
            db.execute('UPDATE products SET demo_stock=? WHERE id=?',(p[9],p[0]))
