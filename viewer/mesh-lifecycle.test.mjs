import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';

const source=await readFile(new URL('./mesh.js',import.meta.url),'utf8');

function fixture(options={}) {
  const allocations=[],deleted=[],calls=[],observers=[],listeners=new Map(),captures=new Set(),released=[];
  let allocationCount=0,compileCount=0,linkCount=0,uploadCount=0,addCount=0;
  const gl=new Proxy({}, {get(_target,key){
    if(String(key)===String(key).toUpperCase())return key;
    if(key.startsWith('create'))return ()=>{
      allocationCount++;
      if(allocationCount===options.nullAllocationAt)return null;
      const value={type:key.slice(6),id:allocationCount};allocations.push(value);return value;
    };
    if(key.startsWith('delete'))return value=>{assert.ok(value);deleted.push(value);};
    if(key==='getShaderParameter')return ()=>++compileCount!==options.compileFailureAt;
    if(key==='getShaderInfoLog')return ()=>'shader compilation failed';
    if(key==='getProgramParameter')return (_program,param)=>param==='LINK_STATUS'?++linkCount!==options.linkFailureAt:0;
    if(key==='getProgramInfoLog')return ()=>'program linking failed';
    if(key==='bufferData')return ()=>{if(++uploadCount===options.uploadFailureAt)throw Error('buffer upload failed');};
    return (...args)=>calls.push([key,...args]);
  }});
  const canvas={
    getContext:()=>options.noWebGL?null:gl,
    addEventListener(type,handler,settings){
      if(++addCount===options.listenerFailureAt)throw Error('listener setup failed');
      assert.equal(listeners.has(type),false);listeners.set(type,{handler,settings});
    },
    removeEventListener(type,handler,settings){
      const item=listeners.get(type);
      if(item){assert.equal(handler,item.handler);assert.equal(settings,item.settings);listeners.delete(type);}
    },
    setPointerCapture:id=>captures.add(id),hasPointerCapture:id=>captures.has(id),
    releasePointerCapture:id=>{captures.delete(id);released.push(id);},
  };
  const Atlas=runInNewContext(source.replace('export class Atlas','class Atlas')+'\nAtlas',{
    ResizeObserver:class {
      constructor(callback){this.callback=callback;this.connected=false;this.disconnects=0;observers.push(this);}
      observe(target){assert.equal(target,canvas);this.connected=true;if(options.observerFailure)throw Error('observer setup failed');}
      disconnect(){this.connected=false;this.disconnects++;}
    },
  });
  const make=()=>new Atlas(canvas,options.model||{joints:[],groups:[]},new ArrayBuffer(40),new ArrayBuffer(4),{});
  const emit=(type,event)=>listeners.get(type)?.handler(event);
  const assertReleased=()=>{
    assert.deepEqual(new Set(deleted),new Set(allocations));
    assert.equal(deleted.length,allocations.length,'no resource deleted twice');
    assert.equal(listeners.size,0);assert.equal(captures.size,0);
    assert.ok(observers.every(observer=>!observer.connected));
  };
  return {make,emit,assertReleased,allocations,deleted,calls,observers,listeners,captures,released};
}

test('dispose releases every owned GPU object, listener, observer and active pointer exactly once',()=>{
  const f=fixture(),atlas=f.make();
  assert.equal(f.allocations.filter(x=>x.type==='Shader').length,6);
  assert.equal(f.deleted.length,6,'shader objects are detached/deleted immediately after linking');
  assert.equal(f.allocations.filter(x=>x.type==='Buffer').length,6);
  assert.equal(f.allocations.filter(x=>x.type==='VertexArray').length,5);
  assert.equal(f.allocations.filter(x=>x.type==='Program').length,3);
  assert.equal(f.listeners.size,6);assert.equal(f.observers[0].connected,true);
  f.emit('pointerdown',{pointerId:1,clientX:2,clientY:3});
  f.emit('pointerdown',{pointerId:2,clientX:4,clientY:5});
  atlas.dispose();f.assertReleased();assert.deepEqual(f.released,[1,2]);
  const callCount=f.calls.length;
  atlas.dispose();atlas.draw();atlas.camera('front');atlas.setClip({});atlas.scaleZoom(2);
  // An already-queued observer callback remains harmless after disconnect.
  f.observers[0].callback();
  assert.equal(f.calls.length,callCount);assert.equal(f.observers[0].disconnects,1);f.assertReleased();
});

test('pointer capture loss clears gesture state before a later pointer move',()=>{
  const f=fixture(),atlas=f.make();
  f.emit('pointerdown',{pointerId:7,clientX:2,clientY:3});
  f.captures.delete(7);f.emit('lostpointercapture',{pointerId:7});
  const yaw=atlas.yaw;f.emit('pointermove',{pointerId:7,clientX:100,clientY:100});
  assert.equal(atlas.yaw,yaw);assert.equal(atlas.pointer.size,0);
  atlas.dispose();f.assertReleased();
});

test('repeated construction and disposal on a reused canvas never accumulates resources or handlers',()=>{
  const f=fixture();
  for(let i=0;i<30;i++){
    const atlas=f.make();assert.equal(f.listeners.size,6);atlas.dispose();f.assertReleased();
  }
  assert.equal(f.observers.length,30);assert.ok(f.observers.every(x=>x.disconnects===1));
});

for(const [description,options,message] of [
  ['first shader compile',{compileFailureAt:1},/shader compilation/],
  ['later shader compile',{compileFailureAt:5},/shader compilation/],
  ['first program link',{linkFailureAt:1},/program linking/],
  ['later program link',{linkFailureAt:3},/program linking/],
  ['shader allocation',{nullAllocationAt:2},/allocate WebGL shader/],
  ['program allocation',{nullAllocationAt:1},/allocate WebGL Program/],
  ['body vertex buffer allocation',{nullAllocationAt:11},/allocate WebGL Buffer/],
  ['body vertex upload',{uploadFailureAt:1},/buffer upload/],
  ['primitive buffer upload',{uploadFailureAt:5},/buffer upload/],
  ['model wrist validation',{model:{wristPivots:['missing'],joints:[]}},/Invalid wrist/],
  ['partial listener registration',{listenerFailureAt:3},/listener setup/],
  ['resize observation',{observerFailure:true},/observer setup/],
])test(`constructor rolls back all resources after ${description} failure`,()=>{
  const f=fixture(options);assert.throws(f.make,message);f.assertReleased();
});

test('unavailable WebGL allocates nothing and leaves the existing host untouched',()=>{
  const f=fixture({noWebGL:true});assert.throws(f.make,/WebGL 2 capable/);f.assertReleased();
  assert.equal(f.allocations.length,0);assert.equal(f.observers.length,0);
});
