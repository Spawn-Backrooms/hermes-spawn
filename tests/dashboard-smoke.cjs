const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const manifest = JSON.parse(fs.readFileSync('dashboard/manifest.json'));
assert.equal(typeof manifest.entry, 'string', 'web dashboard must declare a loadable script');
assert(fs.existsSync('dashboard/' + manifest.entry));
const source = fs.readFileSync('dashboard/' + manifest.entry, 'utf8');
async function render(response, reject=false) {
  let Page, values=[], index=0, cleanup, updates=0;
  const reads=[];
  const React={createElement:(tag,props,...children)=>({tag,props,children}),
    useState:initial=>{const i=index++; if(!(i in values))values[i]=initial; return [values[i],v=>{values[i]=v;updates++;}];},
    useEffect:fn=>{cleanup=fn();}};
  const window={__HERMES_PLUGIN_SDK__:{React,fetchJSON:async(...args)=>{reads.push(args);if(reject)throw Error('secret detail');return response;}},__HERMES_PLUGINS__:{register:(id,component)=>{assert.equal(id,manifest.name);Page=component;}}};
  vm.runInNewContext(source,{window});
  let tree=Page();
  await new Promise(r=>setImmediate(r)); index=0; React.useEffect=()=>{}; tree=Page();
  assert.equal(reads.length,1); assert.deepEqual(reads[0],['/api/plugins/spawn-backrooms/status']);
  return {tree:JSON.stringify(tree),cleanup,updates};
}
(async()=>{
 assert.equal(manifest.api,'plugin_api.py');
 const out=await render({ok:false,error:'not_signed_in'}); assert.match(out.tree,/hermes auth add spawn-backrooms:spawn/);assert.doesNotMatch(out.tree,/Connected to SPAWN/);
 const good=await render({ok:true,jobs:{jobs:[{job_id:'j1'}]},rooms:{rooms:[]},errors:[]});assert.match(good.tree,/Connected to SPAWN/);assert.match(good.tree,/1 assigned jobs/);
 const partial=await render({ok:true,errors:[{section:'jobs',message:'oops'}]});assert.match(partial.tree,/Some sections could not be read/);
 const error=await render(null,true);assert.match(error.tree,/Unable to read SPAWN/);assert.doesNotMatch(error.tree,/secret detail/);
 console.log('Dashboard manifest + 4 read-only rendering cases pass');
})().catch(error=>{console.error(error);process.exit(1)});
