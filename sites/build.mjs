import {build} from 'esbuild';
import {mkdir,readFile,writeFile,copyFile} from 'node:fs/promises';
const assets={};
for(const [url,path,type] of [['/','index.html','text/html; charset=utf-8'],['/static/app.js','static/app.js','text/javascript; charset=utf-8'],['/static/styles.css','static/styles.css','text/css; charset=utf-8'],...['shortage','ready','complete','retailer'].map(n=>['/static/demo/'+n+'.wav','static/demo/'+n+'.wav','audio/wav'])]){
  const bytes=await readFile('public/'+path);assets[url]={body:bytes.toString('base64'),type};
}
await mkdir('.sites-runtime',{recursive:true});
await writeFile('.sites-runtime/assets.mjs','export default '+JSON.stringify(assets)+';');
await mkdir('dist/server',{recursive:true});await mkdir('dist/.openai',{recursive:true});
await build({entryPoints:['worker.mjs'],outfile:'dist/server/index.js',bundle:true,format:'esm',platform:'browser',target:'es2022',minify:true});
await copyFile('.openai/hosting.json','dist/.openai/hosting.json');
console.log('Built BolOrder Worker, UI and prerecorded voice assets.');
