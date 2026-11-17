import {createServer} from 'vite';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const reportPlugin={name:'ui-lab-local-report',configureServer(server){server.middlewares.use('/__ui-report',async(req,res)=>{if(req.method!=='POST'||req.headers.origin&&req.headers.origin!=='http://127.0.0.1:5190'){res.statusCode=403;res.end();return;}let body='';for await(const chunk of req){body+=chunk;if(body.length>2000000){res.statusCode=413;res.end();return;}}try{const data=JSON.parse(body);await mkdir(resolve('..','.local-tools'),{recursive:true});await writeFile(resolve('..','.local-tools','ui-measurements.json'),JSON.stringify(data,null,2));res.end('saved');}catch{res.statusCode=400;res.end('invalid');}});}};
const server=await createServer({configFile:false,plugins:[reportPlugin],root:process.cwd(),server:{host:'127.0.0.1',port:5190,strictPort:true,watch:{usePolling:true},proxy:undefined}});
await server.listen();server.printUrls();
