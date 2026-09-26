import asyncio
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Header
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app import config
from app.db import initialize,connection
from app.models import StartOrder,Turn,Confirm,Speech,PhoneTurn,ItemUpdate
from app.services import order_service as orders, inventory_service as inventory, sarvam_service as sarvam
from app.services import access_service as access

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(name)s %(levelname)s %(message)s')
logging.getLogger('httpx').setLevel(logging.WARNING)
locks={}

@asynccontextmanager
async def lifespan(app):
    if config.PUBLIC_DEPLOYMENT and len(config.APP_ACCESS_PASSWORD) < 16:
        raise RuntimeError('Public deployment requires APP_ACCESS_PASSWORD of at least 16 characters.')
    initialize()
    yield

app=FastAPI(title='BolOrder',version='1.0.0',lifespan=lifespan)
app.mount('/static',StaticFiles(directory=config.ROOT/'app/static'),name='static')
templates=Jinja2Templates(directory=config.ROOT/'app/templates')

@app.exception_handler(ValueError)
async def invalid_input(request,exc):
    return JSONResponse({'detail':str(exc)},status_code=409)

@app.exception_handler(sarvam.ProviderUnavailable)
async def provider_unavailable(request,exc):
    return JSONResponse({'detail':str(exc)},status_code=503)

@app.middleware('http')
async def local_safety(request,call_next):
    path=request.url.path
    identity=request.client.host if request.client else 'unknown'
    if config.PUBLIC_DEPLOYMENT and path!='/healthz':
        # Phone adapter has its own bearer gate; browser endpoints use a shared demo login.
        if path!='/api/voice-agent/turn' and not access.authorized(request.headers.get('authorization','')):
            if not access.allow_request(identity,'login',20):
                return JSONResponse({'detail':'Too many sign-in attempts. Try again in a minute.'},status_code=429,headers={'Retry-After':'60'})
            return JSONResponse({'detail':'Sign in with the shared BolOrder access password.'},status_code=401,headers={'WWW-Authenticate':'Basic realm="BolOrder", charset="UTF-8"','Cache-Control':'no-store'})
        if request.method=='POST':
            if not access.allow_request(identity,'write',60):
                return JSONResponse({'detail':'Too many requests. Please wait a minute.'},status_code=429,headers={'Retry-After':'60'})
            ai_path=path in ('/api/stt','/api/tts','/api/voice-agent/turn') or path.endswith('/turn')
            if ai_path and not access.allow_ai_call(identity):
                return JSONResponse({'detail':'Voice service is busy. Please retry in a minute.'},status_code=429,headers={'Retry-After':'60'})
    try:
        if int(request.headers.get('content-length','0')) > 9*1024*1024:
            return JSONResponse({'detail':'Recording is too large. Keep each turn under 25 seconds.'},status_code=413)
    except ValueError:
        return JSONResponse({'detail':'Invalid content length.'},status_code=400)
    origin=request.headers.get('origin')
    allowed_origin=config.PUBLIC_ORIGIN or str(request.base_url).rstrip('/')
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin.rstrip('/')!=allowed_origin:
        return JSONResponse({'detail':'Cross-origin requests are not allowed.'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Permissions-Policy']='microphone=(self), camera=(), geolocation=()'
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api/') else 'no-cache'
    return response

@app.get('/healthz')
def health():
    with connection() as db:
        db.execute('SELECT 1 FROM products LIMIT 1').fetchone()
    return {'status':'ok'}

@app.get('/',response_class=HTMLResponse)
def index(request:Request):
    return templates.TemplateResponse(request=request,name='index.html')

@app.get('/api/bootstrap')
def bootstrap():
    with connection() as db:
        customers=[dict(r) for r in db.execute('SELECT * FROM customers')]
    return {'customers':customers,'demo_mode':config.DEMO_MODE,'sarvam_configured':bool(os.getenv('SARVAM_API_KEY')),'voice_adapter_configured':bool(os.getenv('VOICE_TOOL_TOKEN')),'date':orders.now().strftime('%A, %d %B %Y')}

@app.get('/api/inventory')
def get_inventory(mode:str='live'):
    return inventory.catalog('demo' if mode=='demo' else 'live')

@app.get('/api/overview')
def overview(mode:str='live'):
    mode='demo' if mode=='demo' else 'live'
    with connection() as db:
        rows=[dict(r) for r in db.execute('''SELECT o.*,c.name AS customer_name,
            COALESCE((SELECT SUM(quantity*carton_price) FROM items WHERE order_id=o.id),0) AS total
            FROM orders o JOIN customers c ON c.id=o.customer_id WHERE mode=? ORDER BY created_at DESC''',(mode,))]
    today=orders.now().date().isoformat()
    completed=[r for r in rows if r['state']=='COMPLETED' and r['created_at'].startswith(today)]
    return {'orders':rows,'metrics':{'orders':len(completed),'value':sum(r['total'] for r in completed),'pending':sum(r['state'] not in orders.FINAL for r in rows),'low_stock':sum(p['stock']<=5 for p in inventory.catalog(mode))}}

@app.post('/api/orders')
def start_order(body:StartOrder):
    return orders.create_draft_order(body.customer_id,'demo' if config.DEMO_MODE else body.mode,body.request_id)

@app.get('/api/orders/{order_id}')
def get_order(order_id:str):
    return orders.get_order(order_id)

@app.post('/api/orders/{order_id}/turn')
async def turn(order_id:str,body:Turn):
    async with locks.setdefault(order_id,asyncio.Lock()):
        with connection() as db:
            cached=db.execute('SELECT response FROM turns WHERE order_id=? AND request_id=?',(order_id,body.request_id)).fetchone()
        if cached:
            return json.loads(cached[0])
        order=orders.get_order(order_id)
        if order['revision']!=body.revision:
            raise ValueError('The cart changed. Review the latest order and try again.')
        updated,message=await sarvam.handle_turn(order,body.text)
        result={'order':updated,'reply':message or sarvam.reply_for(updated),'transcript':body.text,'language':updated['customer']['language']}
        with connection(True) as db:
            db.execute('INSERT INTO turns VALUES(?,?,?)',(order_id,body.request_id,json.dumps(result,ensure_ascii=False)))
        return result

@app.post('/api/orders/{order_id}/confirm')
async def confirm_order(order_id:str,body:Confirm):
    async with locks.setdefault(order_id,asyncio.Lock()):
        order=orders.confirm_order(order_id,body.revision,'Confirm order button',explicit=body.explicit_confirmation)
    return {'order':order,'reply':sarvam.reply_for(order),'language':order['customer']['language']}

@app.post('/api/orders/{order_id}/items')
async def change_items(order_id:str,body:ItemUpdate,revision:int):
    async with locks.setdefault(order_id,asyncio.Lock()):
        order=orders.update_order_items(order_id,[i.model_dump() for i in body.items],body.delivery_date,revision)
    return {'order':order,'reply':sarvam.reply_for(order),'language':order['customer']['language']}

@app.post('/api/orders/{order_id}/cancel')
async def cancel_order(order_id:str):
    async with locks.setdefault(order_id,asyncio.Lock()):
        return orders.cancel_order(order_id)

@app.post('/api/stt')
async def stt(file:UploadFile=File(...)):
    data=await file.read(8*1024*1024+1)
    if len(data)>8*1024*1024:
        raise HTTPException(413,'Recording is too large. Keep each turn under 25 seconds.')
    if len(data)<100:
        raise HTTPException(400,'Recording is empty. Try the microphone again.')
    return await sarvam.transcribe(data,(file.filename or 'recording.webm')[:100],file.content_type or 'audio/webm')

@app.post('/api/tts')
async def tts(body:Speech):
    return Response(await sarvam.speak(body.text,body.language),media_type='audio/wav')

@app.post('/api/demo/reset')
def reset_demo():
    orders.reset_demo_stock()
    return {'ok':True}

@app.get('/api/orders/{order_id}/invoice',response_class=HTMLResponse)
def invoice(order_id:str,request:Request):
    order=orders.get_order(order_id)
    if not order['sales_number']:
        raise HTTPException(409,'Confirm the order to generate an order confirmation.')
    return templates.TemplateResponse(request=request,name='invoice.html',context={'order':order})

@app.post('/api/voice-agent/turn')
async def phone_turn(body:PhoneTurn,authorization:str|None=Header(default=None)):
    token=os.getenv('VOICE_TOOL_TOKEN','')
    if not token or not hmac.compare_digest(authorization or '',f'Bearer {token}'):
        raise HTTPException(401,'Voice Agent adapter is not configured or authentication failed.')
    customer=inventory.identify_customer(phone_number=body.phone_number)
    order=orders.create_draft_order(customer['id'],'live','phone:'+body.interaction_id)
    return await turn(order['id'],Turn(text=body.text,revision=body.revision,request_id=body.request_id))
