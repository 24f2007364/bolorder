import assets from './.sites-runtime/assets.mjs';
import {handle} from './server.mjs';
export default {fetch(request,env,ctx){return handle(request,env,assets);}};
