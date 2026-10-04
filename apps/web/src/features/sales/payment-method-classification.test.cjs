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
  useCallback(fn,deps) { const h=current,i=h.index++; if(!h.values[i]||deps.some((v,j)=>!Object.is(v,h.values[i].deps[j])))h.values[i]={deps,fn}; return h.values[i].fn; }, useMemo(fn) { return fn(); },
  useEffect(fn,deps) { const h=current,i=h.index++; if(!h.values[i]||deps.some((v,j)=>!Object.is(v,h.values[i].deps[j]))){h.values[i]?.cleanup?.();h.values[i]={deps};h.pending.push(()=>{h.values[i].cleanup=fn();});} },
};
const load=Module._load;
Module._load=function(name,...args){
  if(name==='react')return hooks;
  if(name==='next/link')return ()=>null;
  if(name==='@/features/auth/current-user-context')return {useCurrentUser:()=>({isLoading:current.authLoading??false})};
  return load.call(this,name,...args);
};
const {PaymentMethodsScreen,PAYMENT_TYPES,labelPaymentType}=require('./components/payment-methods-screen.tsx');
Module._load=load;
const {setAuthTokenProvider}=require('../../lib/api.ts');
function nodes(tree){if(Array.isArray(tree))return tree.flatMap(nodes);if(!tree||typeof tree!=='object')return [];return [tree,...nodes(tree.props?.children)];}
function content(tree){if(Array.isArray(tree))return tree.map(content).join('');if(tree&&typeof tree==='object')return content(tree.props?.children);return typeof tree==='string'||typeof tree==='number'?String(tree):'';}
const flush=async()=>{for(let i=0;i<100;i++)await Promise.resolve();};
const method={id:'method-1',label:'QR Lida',type:'digital_wallet',is_active:true,sort_order:0,has_payments:false};
function setup(t,{methods=[method],respond,authLoading=false}={}){
 const oldFetch=global.fetch;const h={values:[],pending:[],requests:[],methods:structuredClone(methods),authLoading};
 setAuthTokenProvider(async()=>'test-token');
 global.fetch=async(url,init)=>{
  const request={url:new URL(url),init};h.requests.push(request);
  if(respond)return respond(request,h);
  if(init.method==='PATCH')h.methods=h.methods.map(m=>m.id==='method-1'?{...m,...JSON.parse(init.body)}:m);
  if(init.method==='POST')h.methods.push({id:'new-method',...JSON.parse(init.body)});
  return new Response(JSON.stringify({data:init.method==='GET'?h.methods:{},meta:{total:h.methods.length}}));
 };
 h.render=()=>{current=h;h.index=0;h.tree=PaymentMethodsScreen();if(typeof h.tree.type==='function')h.tree=h.tree.type();h.pending.splice(0).forEach(fn=>fn());return h.tree;};
 h.ready=async()=>{h.render();await flush();h.render();};
 h.button=label=>{const b=nodes(h.tree).find(n=>n.type==='button'&&(n.props['aria-label']===label||content(n).trim()===label));assert.ok(b,label);return b;};
 h.click=label=>{h.button(label).props.onClick();h.render();};
 h.input=(id,value)=>{nodes(h.tree).find(n=>n.props.id===id).props.onChange({target:{value}});h.render();};
 h.submit=()=>{nodes(h.tree).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});h.render();};
 t.after(()=>{h.values.forEach(v=>v?.cleanup?.());global.fetch=oldFetch;setAuthTokenProvider(null);});return h;
}

test('displays structured classification in Spanish independently of label',async t=>{const h=setup(t,{methods:[{...method,label:'EFECTIVO'}]});await h.ready();assert.match(content(h.tree),/Otro medio electrónico/);assert.doesNotMatch(content(h.tree),/digital_wallet/);});
test('unexpected null/unknown classification displays Sin clasificar defensively',async t=>{assert.equal(labelPaymentType(null),'Sin clasificar');assert.equal(labelPaymentType(undefined),'Sin clasificar');assert.equal(labelPaymentType('unexpected'),'Sin clasificar');const h=setup(t,{methods:[{...method,type:null}]});await h.ready();assert.match(content(h.tree),/Sin clasificar/);h.click('Editar QR Lida');assert.equal(nodes(h.tree).find(n=>n.props.id==='payment-method-type').props.value,'');});
test('selector keeps all six canonical categories without internal codes as labels',async t=>{const h=setup(t);await h.ready();h.click('Nueva forma de pago');const select=nodes(h.tree).find(n=>n.props.id==='payment-method-type');assert.equal(select.props.required,true);assert.equal(select.props.value,'');assert.equal(nodes(select).filter(n=>n.type==='option').length,7);for(const [kind,label] of PAYMENT_TYPES){assert.ok(nodes(select).some(n=>n.type==='option'&&n.props.value===kind&&content(n)===label));assert.notEqual(kind,label);}});
test('create needs explicit classification and does not infer cash from label',async t=>{const h=setup(t);await h.ready();h.click('Nueva forma de pago');h.input('payment-method-name','EFECTIVO');h.submit();await flush();h.render();assert.equal(h.requests.filter(r=>r.init.method==='POST').length,0);assert.match(content(h.tree),/Selecciona un tipo/);h.input('payment-method-type','other');h.submit();await flush();h.render();assert.equal(JSON.parse(h.requests.find(r=>r.init.method==='POST').init.body).type,'other');});
test('saves edited classification without a second payment_kind field',async t=>{const h=setup(t);await h.ready();h.click('Editar QR Lida');h.input('payment-method-type','bank_transfer');h.submit();await flush();h.render();const body=JSON.parse(h.requests.find(r=>r.init.method==='PATCH').init.body);assert.equal(body.type,'bank_transfer');assert.equal('payment_kind' in body,false);assert.match(content(h.tree),/Transferencia bancaria/);});
test('error preserves selected classification and allows retry',async t=>{let fail=true;const h=setup(t,{respond:(r,h)=>new Response(JSON.stringify(r.init.method==='GET'?{data:h.methods,meta:{total:1}}:fail?{error:{code:'validation_error',message:'Error de guardado'}}:{data:{}}),{status:r.init.method==='GET'||!fail?200:422})});await h.ready();h.click('Editar QR Lida');h.input('payment-method-type','credit_card');h.submit();await flush();h.render();assert.match(content(h.tree),/Error de guardado/);assert.equal(nodes(h.tree).find(n=>n.props.id==='payment-method-type').props.value,'credit_card');assert.equal(h.button('Guardar').props.disabled,false);fail=false;h.submit();await flush();h.render();assert.equal(h.requests.filter(r=>r.init.method==='PATCH').length,2);});
test('loading does not announce an empty catalog',async t=>{let finish;const h=setup(t,{respond:()=>new Promise(resolve=>{finish=resolve;})});h.render();await flush();assert.match(content(h.tree),/Cargando formas de pago/);assert.doesNotMatch(content(h.tree),/No hay formas/);finish(new Response(JSON.stringify({data:[],meta:{total:0}})));await flush();h.render();assert.match(content(h.tree),/No hay formas de pago configuradas/);});
test('auth loading keeps existing permission gate',async t=>{const h=setup(t,{authLoading:true});await h.ready();assert.match(content(h.tree),/Cargando permisos/);assert.equal(h.requests.length,0);});
test('inactive method retains visible classification and can reactivate',async t=>{const h=setup(t,{methods:[{...method,is_active:false}]});await h.ready();assert.match(content(h.tree),/Inactiva/);assert.match(content(h.tree),/Otro medio electrónico/);h.click('Activar QR Lida');await flush();h.render();assert.deepEqual(JSON.parse(h.requests.find(r=>r.init.method==='PATCH').init.body),{is_active:true});});
test('historical method type stays locked while rename stays available',async t=>{const h=setup(t,{methods:[{...method,has_payments:true}]});await h.ready();h.click('Editar QR Lida');assert.equal(nodes(h.tree).find(n=>n.props.id==='payment-method-type').props.disabled,true);assert.match(content(h.tree),/bloqueado porque ya existen cobros históricos/);h.input('payment-method-name','QR Mercado Pago Lida');h.submit();await flush();h.render();assert.equal(JSON.parse(h.requests.find(r=>r.init.method==='PATCH').init.body).type,'digital_wallet');});
test('mobile cards include classification state and descriptive edit actions',async t=>{const h=setup(t);await h.ready();const mobile=nodes(h.tree).find(n=>n.props['aria-label']==='Formas de pago móvil');assert.match(content(mobile),/QR Lida/);assert.match(content(mobile),/Otro medio electrónico/);assert.ok(nodes(mobile).some(n=>n.props['aria-label']==='Editar QR Lida'));const css=fs.readFileSync(path.join(root,'styles/globals.css'),'utf8');assert.match(css,/\.payment-methods-desktop \{ display: none/);assert.match(css,/\.payment-methods-mobile article[^}]*overflow-wrap: anywhere/);});
test('form associates labels and type help and announces errors',async t=>{const h=setup(t);await h.ready();h.click('Nueva forma de pago');for(const id of ['payment-method-name','payment-method-type','payment-method-order'])assert.ok(nodes(h.tree).some(n=>n.type==='label'&&n.props.htmlFor===id));assert.equal(nodes(h.tree).find(n=>n.props.id==='payment-method-type').props['aria-describedby'],'payment-method-type-help');h.input('payment-method-name','QR');h.submit();h.render();assert.ok(nodes(h.tree).some(n=>n.props.role==='alert'));});
test('synchronous duplicate save is blocked and fields disable while saving',async t=>{let finish;const h=setup(t,{respond:(r,h)=>r.init.method==='GET'?new Response(JSON.stringify({data:h.methods,meta:{total:1}})):new Promise(resolve=>{finish=resolve;})});await h.ready();h.click('Editar QR Lida');h.submit();h.submit();await flush();h.render();assert.equal(h.requests.filter(r=>r.init.method==='PATCH').length,1);assert.equal(nodes(h.tree).find(n=>n.type==='fieldset').props.disabled,true);assert.match(content(h.tree),/Guardando/);finish(new Response(JSON.stringify({data:{}})));await flush();h.render();});
test('catalog includes later pages and inactive methods without active-only filter',async t=>{const h=setup(t,{respond:r=>new Response(JSON.stringify({data:[{...method,id:r.url.searchParams.get('page'),is_active:r.url.searchParams.get('page')==='1'}],meta:{total:2}}))});await h.ready();assert.equal(h.requests.length,2);assert.ok(h.requests.every(r=>!r.url.searchParams.has('active')));assert.match(content(h.tree),/Inactiva/);});
test('load error offers retry instead of misleading empty state',async t=>{let fail=true;const h=setup(t,{respond:(r,h)=>new Response(JSON.stringify(fail?{error:{message:'No se pudo cargar',code:'validation_error'}}:{data:h.methods,meta:{total:1}}),{status:fail?422:200})});await h.ready();assert.match(content(h.tree),/No se pudo cargar/);assert.doesNotMatch(content(h.tree),/No hay formas/);fail=false;h.click('Reintentar');await flush();h.render();assert.match(content(h.tree),/QR Lida/);});
