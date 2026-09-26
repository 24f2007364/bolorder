import uuid
import pytest
from fastapi.testclient import TestClient
from app import config
from app.main import app
from app.services import order_service as orders,inventory_service as inv
from app.services.sarvam_service import consent

@pytest.fixture
def api(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'DB_PATH',tmp_path/'test.sqlite3')
    with TestClient(app) as client:
        yield client

def start(api):
    return api.post('/api/orders',json={'customer_id':'raja','mode':'demo','request_id':str(uuid.uuid4())}).json()

def turn(api,o,text,request_id=None):
    return api.post(f"/api/orders/{o['id']}/turn",json={'text':text,'request_id':request_id or str(uuid.uuid4()),'revision':o['revision']})

def test_happy_path_and_idempotency(api):
    o=start(api)
    o=turn(api,o,'10 atta 5 Maggi 4 Parle-G').json()['order']
    assert o['state']=='WAITING_FOR_CLARIFICATION'
    assert o['shortages'][0]['available']==3
    assert o['shortages'][0]['alternatives'][0]['id']=='NDL-YP-70'
    assert inv.get_product('NDL-MG-70','demo')['stock']==3
    assert api.post(f"/api/orders/{o['id']}/confirm",json={'revision':o['revision'],'explicit_confirmation':True}).status_code==409
    o=turn(api,o,'Haan 3 Maggi aur 2 Yippee kar do').json()['order']
    assert o['state']=='READY_FOR_CONFIRMATION' and o['total']==2462400
    key=str(uuid.uuid4())
    response=turn(api,o,'Haan confirm',key)
    assert response.status_code==200
    done=response.json()['order']
    assert done['state']=='COMPLETED' and done['sales_number']=='SO-1028'
    assert inv.get_product('NDL-MG-70','demo')['stock']==0
    assert inv.get_product('NDL-MG-70','live')['stock']==3
    assert turn(api,o,'Haan confirm',key).json()['order']['sales_number']==done['sales_number']
    assert api.post(f"/api/orders/{o['id']}/confirm",json={'revision':o['revision'],'explicit_confirmation':True}).json()['order']['sales_number']==done['sales_number']
    assert api.get(done['invoice_url']).status_code==200
    assert 'Notification simulated' in [e['action'] for e in done['events']]

def test_transaction_rolls_back_when_stock_changes(api):
    a=start(api); b=start(api)
    a=orders.add_item_to_order(a['id'],'ATT-AA-5',10)
    b=orders.add_item_to_order(b['id'],'ATT-AA-5',10)
    orders.confirm_order(a['id'],a['revision'],'yes confirm',True)
    with pytest.raises(ValueError):orders.confirm_order(b['id'],b['revision'],'yes confirm',True)
    assert orders.get_order(b['id'])['sales_number'] is None
    assert inv.get_product('ATT-AA-5','demo')['stock']==0

def test_validation_and_confirmation_safety(api):
    o=start(api)
    assert api.post(f"/api/orders/{o['id']}/items?revision=0",json={'items':[{'product_id':'invented','quantity':1}]}).status_code==409
    assert api.post(f"/api/orders/{o['id']}/items?revision=0",json={'items':[{'product_id':'NDL-MG-70','quantity':-1}]}).status_code==422
    o=orders.add_item_to_order(o['id'],'NDL-MG-70',2)
    assert api.post(f"/api/orders/{o['id']}/confirm",json={'revision':0,'explicit_confirmation':True}).status_code==409
    assert api.post(f"/api/orders/{o['id']}/confirm",json={'revision':o['revision'],'explicit_confirmation':False}).status_code==422
    for text in ['do not confirm','haan confirm mat karo','not confirmed','confirm 5 more maggi','हाँ कन्फर्म मत करो']:
        assert not consent(text)
    assert consent('Haan confirm.')
    assert consent('हाँ कन्फर्म')

def test_ambiguous_product_and_unknown_customer(api):
    result=inv.search_products('red packet wala biscuit')
    assert len([p for p in result if p['confidence']==1])==2
    assert api.post('/api/orders',json={'customer_id':'missing','mode':'demo','request_id':str(uuid.uuid4())}).status_code==409
    assert api.post('/api/voice-agent/turn',json={'text':'hello','request_id':str(uuid.uuid4()),'revision':0,'interaction_id':'call1','phone_number':'+919000000001'}).status_code==401

def test_demo_reset_leaves_live_stock_untouched(api):
    o=start(api)
    o=orders.add_item_to_order(o['id'],'NDL-MG-70',3)
    orders.confirm_order(o['id'],o['revision'],'yes confirm',True)
    api.post('/api/demo/reset')
    assert inv.get_product('NDL-MG-70','demo')['stock']==3
    assert inv.get_product('NDL-MG-70','live')['stock']==3
