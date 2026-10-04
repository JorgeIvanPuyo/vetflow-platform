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
  if(name==='@/features/auth/current-user-context')return {useCurrentUser:()=>({role:current.role})};
  if(name==='@/features/clinic/clinic-context')return {useClinic:()=>({refreshProfile(){},refreshPreferences(){current.refreshes++;}})};
  return load.call(this,name,...args);
};
const {ReceivablesSettingsSection}=require('./components/receivables-settings-section.tsx');
const {SettingsScreen}=require('./components/settings-screen.tsx');
Module._load=load;
const {clinicCalendarDate,startDateError}=require('./components/receivables-settings-helpers.ts');
const {setAuthTokenProvider}=require('../../lib/api.ts');
const NativeDate=Date;
const todayInstant='2026-10-05T02:00:00Z';
function nodes(tree){if(Array.isArray(tree))return tree.flatMap(nodes);if(!tree||typeof tree!=='object')return [];return [tree,...nodes(tree.props?.children)];}
function content(tree){if(Array.isArray(tree))return tree.map(content).join('');if(tree&&typeof tree==='object')return content(tree.props?.children);return typeof tree==='string'?tree:'';}
const flush=async()=>{for(let i=0;i<100;i++)await Promise.resolve();};
function setup(t,{cutoff=null,timezone='America/Panama',role='clinic_admin',respond,settings=false}={}){
 const old={fetch:global.fetch,document:global.document,HTMLElement:global.HTMLElement,Date:global.Date};
 global.Date=class extends NativeDate{constructor(...args){super(...(args.length?args:[todayInstant]));}static now(){return new NativeDate(todayInstant).getTime();}};
 global.HTMLElement=class {};global.document={activeElement:null};
 const preferences={id:'prefs',tenant_id:'tenant',currency_code:'USD',locale:'es-PA',default_appointment_duration_minutes:30,appointment_duration_options:[30],default_purchase_tax_rate:'0',default_sale_tax_rate:'0',default_profit_margin:'0',money_rounding_increment:'1',receivables_tracking_started_at:cutoff};
 const h={values:[],pending:[],requests:[],saves:[],role,refreshes:0,preferences};
 setAuthTokenProvider(async()=>'test-token');
 global.fetch=async(url,init)=>{
  h.requests.push({url:new URL(url),init});
  if(init.method==='PATCH'){
   if(respond)return respond(init,h);
   const day=JSON.parse(init.body).receivables_tracking_start_date;
   return new Response(JSON.stringify({data:{...h.preferences,receivables_tracking_started_at:`${day}T05:00:00Z`},meta:{}}),{status:200});
  }
  const pathname=new URL(url).pathname;
  const data=pathname.endsWith('/profile')?{id:'tenant',display_name:'Clínica',timezone}:pathname.endsWith('/configuration')?{preferences:h.preferences,services:[]}:[];
  return new Response(JSON.stringify({data,meta:{}}),{status:200});
 };
 h.render=()=>{current=h;h.index=0;h.tree=settings?SettingsScreen():ReceivablesSettingsSection({preferences:h.preferences,timezone,onSaved:updated=>{h.preferences=updated;h.saves.push(updated);}});h.pending.splice(0).forEach(fn=>fn());return h.tree;};
 h.ready=async()=>{h.render();await flush();return h.render();};
 h.select=value=>{nodes(h.tree).find(n=>n.props.id==='receivables-start-date').props.onChange({target:{value}});h.render();};
 h.button=label=>{const result=nodes(h.tree).find(n=>n.type==='button'&&content(n).trim()===label);assert.ok(result,label);return result;};
 h.submit=()=>nodes(h.tree).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});
 t.after(()=>{h.values.forEach(v=>v?.cleanup?.());Object.assign(global,old);setAuthTokenProvider(null);});return h;
}

test('NULL shows unconfigured, blank date and never auto-activates',async t=>{const h=setup(t);await h.ready();assert.match(content(h.tree),/No configurado/);assert.equal(nodes(h.tree).find(n=>n.props.id==='receivables-start-date').props.value,'');assert.equal(h.requests.length,0);});
test('active cutoff displays the clinic date instead of browser or UTC date',async t=>{const h=setup(t,{cutoff:'2026-10-02T02:00:00Z'});await h.ready();assert.match(content(h.tree),/Activo desde 01\/10\/2026/);assert.equal(nodes(h.tree).find(n=>n.props.id==='receivables-start-date').props.value,'2026-10-01');});
test('today fills the clinic calendar date without a request',async t=>{const h=setup(t);await h.ready();h.button('Empezar desde hoy').props.onClick();h.render();assert.equal(nodes(h.tree).find(n=>n.props.id==='receivables-start-date').props.value,'2026-10-04');assert.equal(h.requests.length,0);});
test('today differs correctly across clinic timezones',()=>{assert.equal(clinicCalendarDate(todayInstant,'America/Panama'),'2026-10-04');assert.equal(clinicCalendarDate(todayInstant,'Asia/Tokyo'),'2026-10-05');});
test('initial save sends only a date, blocks synchronous duplicate submit and updates UI',async t=>{
 let finish;const h=setup(t,{respond:()=>new Promise(resolve=>{finish=resolve;})});await h.ready();h.select('2026-10-01');h.submit();h.submit();h.render();
 assert.match(content(h.tree),/Guardando…/);assert.equal(nodes(h.tree).find(n=>n.type==='fieldset').props.disabled,true);await flush();assert.equal(h.requests.length,1);assert.deepEqual(JSON.parse(h.requests[0].init.body),{receivables_tracking_start_date:'2026-10-01'});
 finish(new Response(JSON.stringify({data:{...h.preferences,receivables_tracking_started_at:'2026-10-01T05:00:00Z'}}),{status:200}));await flush();h.render();assert.match(content(h.tree),/Configuración guardada/);assert.match(content(h.tree),/Activo desde 01\/10\/2026/);assert.equal(h.saves.length,1);
});
test('save error retains date, enables retry and does not report success',async t=>{
 let fail=true;const h=setup(t,{respond:()=>new Response(JSON.stringify(fail?{error:{message:'No se pudo guardar.',code:'validation_error'}}:{data:{...h.preferences,receivables_tracking_started_at:'2026-10-01T05:00:00Z'}}),{status:fail?422:200})});await h.ready();h.select('2026-10-01');h.submit();await flush();h.render();assert.equal(nodes(h.tree).find(n=>n.props.id==='receivables-start-date').props.value,'2026-10-01');assert.equal(nodes(h.tree).find(n=>n.type==='fieldset').props.disabled,false);assert.match(content(h.tree),/No se pudo guardar/);assert.equal(h.saves.length,0);fail=false;h.submit();await flush();h.render();assert.equal(h.saves.length,1);
});
test('future date is visibly invalid and cannot submit even programmatically',async t=>{const h=setup(t);await h.ready();h.select('2026-10-05');assert.match(content(h.tree),/no puede estar en el futuro/);assert.equal(h.button('Guardar configuración').props.disabled,true);h.submit();await flush();assert.equal(h.requests.length,0);assert.equal(nodes(h.tree).find(n=>n.props.id==='receivables-start-date').props.max,'2026-10-04');});
for(const [day,phrase] of [['2026-10-01','incorporar ventas anteriores'],['2026-10-03','excluir ventas']])test(`change to ${day} warns and needs explicit confirmation`,async t=>{
 const h=setup(t,{cutoff:'2026-10-02T05:00:00Z'});await h.ready();h.select(day);assert.match(content(h.tree),new RegExp(phrase));h.submit();h.render();assert.equal(h.requests.length,0);const dialog=nodes(h.tree).find(n=>n.type==='dialog');assert.equal(dialog.props['aria-labelledby'],'receivables-confirm-title');assert.match(content(dialog),/Cambiar esta fecha puede modificar/);h.button('Confirmar cambio').props.onClick();await flush();h.render();assert.equal(h.requests.length,1);assert.equal(nodes(h.tree).some(n=>n.type==='dialog'),false);assert.match(content(h.tree),/Configuración guardada/);
});
test('cancel and Escape close confirmation without saving',async t=>{const h=setup(t,{cutoff:'2026-10-02T05:00:00Z'});await h.ready();h.select('2026-10-01');h.submit();h.render();h.button('Cancelar').props.onClick();h.render();assert.equal(h.requests.length,0);h.submit();h.render();nodes(h.tree).find(n=>n.type==='dialog').props.onCancel({preventDefault(){}});h.render();assert.equal(h.requests.length,0);assert.equal(nodes(h.tree).some(n=>n.type==='dialog'),false);});
for(const role of ['superadmin',null])test(`read-only ${role} cannot change date or save`,async t=>{const h=setup(t,{role});await h.ready();assert.equal(nodes(h.tree).find(n=>n.type==='fieldset').props.disabled,true);h.select('2026-10-01');h.submit();await flush();assert.equal(h.requests.length,0);assert.match(content(h.tree),/no tiene permiso/);});
test('blank active date does not offer disabling tracking',async t=>{const h=setup(t,{cutoff:'2026-10-02T05:00:00Z'});await h.ready();h.select('');assert.equal(h.button('Guardar cambios').props.disabled,true);h.submit();await flush();assert.equal(h.requests.length,0);assert.doesNotMatch(content(h.tree),/Desactivar/);});
test('labels and live feedback provide basic accessibility',async t=>{const h=setup(t);await h.ready();const field=nodes(h.tree).find(n=>n.type==='label');assert.equal(field.props.htmlFor,'receivables-start-date');assert.ok(nodes(h.tree).some(n=>n.props.role==='status'));assert.equal(h.button('Guardar configuración').props['aria-live'],'polite');h.select('2026-10-05');assert.equal(nodes(h.tree).find(n=>n.props.id==='receivables-start-date').props['aria-invalid'],true);});
test('invalid clinic timezone cannot silently choose another timezone',async t=>{const h=setup(t,{timezone:'Invalid/Zone'});await h.ready();assert.match(content(h.tree),/zona horaria/);assert.equal(nodes(h.tree).find(n=>n.type==='fieldset').props.disabled,true);h.submit();await flush();assert.equal(h.requests.length,0);});
test('invalid calendar dates are rejected',()=>{for(const value of ['','2026-02-30','0000-01-01','bad'])assert.ok(startDateError(value,'2026-10-04'));assert.equal(startDateError('2024-02-29','2026-10-04'),null);});
test('settings contains the section under Sales and updates preferences without reload',async t=>{const h=setup(t,{settings:true});await h.ready();h.button('Ventas y cobrosFormas de pago, cuentas por cobrar y comprobantes manuales.').props.onClick();h.render();const section=nodes(h.tree).find(n=>n.type===ReceivablesSettingsSection);assert.ok(section);assert.equal(section.props.timezone,'America/Panama');section.props.onSaved({...h.preferences,receivables_tracking_started_at:'2026-10-01T05:00:00Z'});h.render();assert.equal(nodes(h.tree).find(n=>n.type===ReceivablesSettingsSection).props.preferences.receivables_tracking_started_at,'2026-10-01T05:00:00Z');assert.equal(h.refreshes,1);});

test('confirmation cycles keyboard focus in both directions',async t=>{
 const h=setup(t,{cutoff:'2026-10-02T05:00:00Z'});await h.ready();h.select('2026-10-01');h.submit();h.render();
 const modal=nodes(h.tree).find(n=>n.type==='dialog');let focused='',prevented=0;
 const first={focus(){focused='first';}},last={focus(){focused='last';}};
 const event={key:'Tab',shiftKey:false,currentTarget:{querySelectorAll:()=>[first,last]},preventDefault(){prevented++;}};
 document.activeElement=last;modal.props.onKeyDown(event);assert.equal(focused,'first');
 document.activeElement=first;modal.props.onKeyDown({...event,shiftKey:true});assert.equal(focused,'last');assert.equal(prevented,2);
});
