const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), Module = require('node:module');
const { test } = require('node:test');
const React = require('react'), ts = require('typescript');
const root = path.resolve(__dirname, '../..');
const resolve = Module._resolveFilename;
Module._resolveFilename = function(name, ...args) { return resolve.call(this, name.startsWith('@/') ? path.join(root, name.slice(2)) : name, ...args); };
for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (module, filename) => {
  assert.ok(filename.startsWith(root + path.sep));
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { fileName: filename, compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
};
let current;
const hooks = { ...React,
  useState(initial) { const h=current,i=h.index++; if (!(i in h.values)) h.values[i]=typeof initial==='function'?initial():initial; return [h.values[i],value=>{h.values[i]=typeof value==='function'?value(h.values[i]):value;}]; },
  useRef(initial) { const h=current,i=h.index++; return h.values[i]??={current:initial}; },
  useCallback(fn) { return fn; }, useMemo(fn) { return fn(); },
  useEffect(fn,deps) { const h=current,i=h.index++; if(!h.values[i]||deps.some((v,j)=>!Object.is(v,h.values[i].deps[j]))){h.values[i]?.cleanup?.();h.values[i]={deps};h.pending.push(()=>{h.values[i].cleanup=fn();});} },
};
const load=Module._load;
Module._load=function(name,...args){
  if(name==='react')return hooks;
  if(name==='next/link')return ()=>null;
  return load.call(this,name,...args);
};
const {PaymentReportScreen}=require('./reports/payment-report-screen.tsx');
Module._load=load;
const {setAuthTokenProvider}=require('../../lib/api.ts');
function nodes(tree){if(Array.isArray(tree))return tree.flatMap(nodes);if(!tree||typeof tree!=='object')return [];return [tree,...nodes(tree.props?.children)];}
function content(tree){if(Array.isArray(tree))return tree.map(content).join('');if(tree&&typeof tree==='object')return content(tree.props?.children);return typeof tree==='string'||typeof tree==='number'?String(tree):'';}
const flush=async()=>{for(let i=0;i<100;i++)await Promise.resolve();};
const base={
 data:{date_from:'2026-10-02',date_to:'2026-10-02',timezone:'America/Panama',currency_code:'USD',locale:'es-PA',
 methods:[{payment_method_id:'cash',label:'Efectivo actual',is_active:true},{payment_method_id:'qr',label:'QR cerrado',is_active:false}],
 summary:{total_amount_ars:'100000000000000.01',payment_count:26,by_method:[{payment_method_id:'cash',label:'Efectivo histórico',is_active:true,amount_ars:'80000.00',payment_count:12},{payment_method_id:'qr',label:'QR histórico',is_active:false,amount_ars:'99999999920000.01',payment_count:14}]},
 payments:[{payment_id:'pay-1',received_at:'2026-10-03T02:30:00Z',payment_method_id:'cash',payment_method_label:'Efectivo histórico',amount_ars:'10.01',sale_id:'abcdef12-3456',owner_id:'owner',owner_name:'Ana',patient_id:'patient',patient_name:'Firulais',reference:'REF 123',created_by_user_id:'user',created_by_user_name:'Operadora'}]},
 meta:{page:1,page_size:20,total:26,total_pages:2},
};
function setup(t,{payload=base,respond}={}){
 const oldFetch=global.fetch;const h={values:[],pending:[],requests:[],payload:structuredClone(payload)};
 setAuthTokenProvider(async()=>'test-token');
 global.fetch=async(url,init)=>{const request={url:new URL(url),init};h.requests.push(request);return respond?respond(request,h):new Response(JSON.stringify(h.payload),{status:200});};
 h.render=()=>{current=h;h.index=0;h.tree=PaymentReportScreen();h.pending.splice(0).forEach(fn=>fn());return h.tree;};
 h.ready=async()=>{h.render();await flush();h.render();};
 h.input=(id,value)=>{nodes(h.tree).find(n=>n.props.id===id).props.onChange({target:{value}});h.render();};
 h.button=label=>{const button=nodes(h.tree).find(n=>n.type==='button'&&content(n)===label);assert.ok(button,label);return button;};
 h.submit=()=>{nodes(h.tree).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});h.render();};
 t.after(()=>{h.values.forEach(v=>v?.cleanup?.());global.fetch=oldFetch;setAuthTokenProvider(null);});return h;
}

test('summary exact money and count represent the full filter',async t=>{const h=setup(t);await h.ready();assert.match(content(h.tree),/100,000,000,000,000\.01/);assert.match(content(h.tree),/26 cobros/);assert.match(content(h.tree),/80,000\.00/);});
test('groups keyed by identity preserve historical names and inactivity',async t=>{const h=setup(t);await h.ready();const summary=nodes(h.tree).find(n=>n.props['aria-label']==='Resumen de cobros');const groups=nodes(summary).filter(n=>n.type==='article');assert.equal(groups.length,3);assert.match(content(summary),/Efectivo histórico/);assert.match(content(summary),/QR histórico/);assert.match(content(summary),/Inactiva/);});
test('today defaults come from clinic API and initial read has no browser dates',async t=>{const h=setup(t);await h.ready();assert.equal(h.requests[0].url.search,'');assert.equal(nodes(h.tree).find(n=>n.props.id==='report-from').props.value,'2026-10-02');assert.equal(nodes(h.tree).find(n=>n.props.id==='report-to').props.value,'2026-10-02');});
test('date filters apply together and reset pagination',async t=>{const h=setup(t);await h.ready();h.input('report-from','2026-10-01');h.input('report-to','2026-10-05');assert.equal(h.requests.length,1);h.submit();await flush();h.render();const query=h.requests.at(-1).url.searchParams;assert.equal(query.get('date_from'),'2026-10-01');assert.equal(query.get('date_to'),'2026-10-05');assert.equal(query.get('page'),'1');});
test('method filter includes historical inactive methods and supports All',async t=>{const h=setup(t);await h.ready();const select=nodes(h.tree).find(n=>n.props.id==='report-method');assert.match(content(select),/Todas/);assert.match(content(select),/QR cerrado \(inactiva\)/);h.input('report-method','qr');h.submit();await flush();h.render();assert.equal(h.requests.at(-1).url.searchParams.get('payment_method_id'),'qr');h.input('report-method','');h.submit();await flush();h.render();assert.equal(h.requests.at(-1).url.searchParams.has('payment_method_id'),false);});
test('details display date method amount parties reference and actor',async t=>{const h=setup(t);await h.ready();const detail=nodes(h.tree).find(n=>n.props['aria-label']==='Detalle de cobros');for(const text of ['Efectivo histórico','10.01','Ana','Firulais','REF 123','Operadora'])assert.ok(content(detail).includes(text),text);});
test('every detail has navigation to its sale and report returns to sales',async t=>{const h=setup(t);await h.ready();assert.ok(nodes(h.tree).some(n=>n.props.href==='/sales/abcdef12-3456'));assert.ok(nodes(h.tree).some(n=>n.props.href==='/sales'));const sales=fs.readFileSync(path.join(root,'features/sales/components/sales-screen.tsx'),'utf8');assert.match(sales,/href="\/sales\/reports\/payments"/);});
test('loading hides results and announces progress',async t=>{let finish;const h=setup(t,{respond:()=>new Promise(resolve=>{finish=resolve;})});h.render();await flush();assert.match(content(h.tree),/Cargando cobros/);assert.equal(nodes(h.tree).some(n=>n.props['aria-label']==='Resumen de cobros'),false);finish(new Response(JSON.stringify(base)));await flush();h.render();assert.equal(nodes(h.tree).some(n=>n.props['aria-label']==='Resumen de cobros'),true);});
test('error hides totals and allows retry',async t=>{let fail=true;const h=setup(t,{respond:()=>new Response(JSON.stringify(fail?{error:{message:'Fecha inválida',code:'validation_error'}}:base),{status:fail?422:200})});await h.ready();assert.match(content(h.tree),/Fecha inválida/);assert.equal(nodes(h.tree).some(n=>n.props['aria-label']==='Resumen de cobros'),false);fail=false;h.button('Reintentar').props.onClick();h.render();await flush();h.render();assert.equal(h.requests.length,2);assert.match(content(h.tree),/Total cobrado/);});
test('empty uses cobros wording and zero summary',async t=>{const payload=structuredClone(base);payload.data.summary={total_amount_ars:'0.00',payment_count:0,by_method:[]};payload.data.payments=[];payload.meta.total=0;const h=setup(t,{payload});await h.ready();assert.match(content(h.tree),/No hay cobros registrados para este período\./);assert.equal(nodes(h.tree).some(n=>n.type==='table'),false);});
test('pagination preserves applied filters while draft remains unsubmitted',async t=>{const h=setup(t,{respond:(request,h)=>{const result=structuredClone(h.payload);result.meta.page=Number(request.url.searchParams.get('page')||1);return new Response(JSON.stringify(result));}});await h.ready();h.input('report-from','2026-09-01');h.button('Siguiente').props.onClick();h.render();await flush();h.render();const query=h.requests.at(-1).url.searchParams;assert.equal(query.get('page'),'2');assert.equal(query.get('date_from'),'2026-10-02');assert.equal(h.button('Anterior').props.disabled,false);assert.equal(h.button('Siguiente').props.disabled,true);});
test('timestamps explicitly use clinic timezone instead of browser date',async t=>{const h=setup(t);await h.ready();assert.match(content(h.tree),/02\/10\/2026/);assert.match(content(h.tree),/21:30/);assert.match(content(h.tree),/America\/Panama/);});
test('mobile cards expose date method amount reference actor and sale link',async t=>{const h=setup(t);await h.ready();const mobile=nodes(h.tree).find(n=>n.props['aria-label']==='Detalle de cobros móvil');assert.ok(nodes(mobile).some(n=>n.type==='time'&&n.props.dateTime==='2026-10-03T02:30:00Z'));assert.match(content(mobile),/Efectivo histórico/);assert.ok(nodes(mobile).some(n=>n.props.href==='/sales/abcdef12-3456'));const css=fs.readFileSync(path.join(root,'styles/globals.css'),'utf8');assert.match(css,/@media \(max-width: 900px\)[\s\S]*\.payment-report-desktop \{ display: none/);assert.match(css,/\.payment-report-mobile article \{ min-width: 0; overflow-wrap: anywhere/);});
test('invalid or reversed range does not issue a request',async t=>{const h=setup(t);await h.ready();h.input('report-from','2026-10-03');h.submit();await flush();assert.equal(h.requests.length,1);assert.match(content(h.tree),/rango de fechas válido/);});
test('late response cannot replace a newer applied report',async t=>{let finish;const h=setup(t,{respond:request=>request.url.searchParams.get('date_from')==='2026-09-01'?new Promise(resolve=>{finish=resolve;}):new Response(JSON.stringify(base))});await h.ready();h.input('report-from','2026-09-01');h.submit();await flush();h.input('report-from','2026-10-01');h.submit();await flush();h.render();const stale=structuredClone(base);stale.data.summary.total_amount_ars='777.77';finish(new Response(JSON.stringify(stale)));await flush();h.render();assert.doesNotMatch(content(h.tree),/777\.77/);});
test('null optional fields remain readable',async t=>{const payload=structuredClone(base);for(const field of ['owner_name','patient_name','reference','created_by_user_name'])payload.data.payments[0][field]=null;const h=setup(t,{payload});await h.ready();for(const text of ['Sin propietario','Sin paciente','Sin referencia','Sin usuario registrado'])assert.match(content(h.tree),new RegExp(text));});
