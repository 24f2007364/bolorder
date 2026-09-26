import {createServer} from 'node:http';
import {readFileSync} from 'node:fs';
import worker from './dist/server/index.js';
import {localDB} from './local-db.mjs';
const env={DB:localDB('.sites-runtime/preview.sqlite3'),APP_ACCESS_PASSWORD:'local-preview-access-only',SARVAM_API_KEY:process.env.SARVAM_API_KEY||''};
const server=createServer(async(req,res)=>{try{const parts=[];for await(const part of req)parts.push(part);const data=Buffer.concat(parts);const request=new Request('http://127.0.0.1:8001'+req.url,{method:req.method,headers:req.headers,...(!['GET','HEAD'].includes(req.method)?{body:data}:{} )});const response=await worker.fetch(request,env,{});res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));}catch{res.writeHead(500);res.end('Preview unavailable');}});server.listen(8001,'127.0.0.1',()=>console.log('Local: http://127.0.0.1:8001'));
