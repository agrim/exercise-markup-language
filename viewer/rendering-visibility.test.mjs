import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';
const source=await readFile(new URL('./mesh.js',import.meta.url),'utf8');
const start=source.indexOf('  draw() {');assert.ok(start>=0);
const draw=runInNewContext('class TestAtlas {\n'+source.slice(start)+'\nTestAtlas.prototype.draw');
test('skipped rendering still samples current logical time without layout or GPU access',()=>{
 let samples=0;const frame={phase:'lower',diagnostics:['current']};
 const atlas={clip:{},time:1.5,renderingSkipped:true,sample(time){assert.equal(time,1.5);samples++;return frame;},
 get canvas(){throw Error('must not measure skipped canvas');},get gl(){throw Error('must not access skipped GPU');}};
 draw.call(atlas);assert.equal(samples,1);assert.equal(atlas.frame,frame);
 atlas.time=2;atlas.sample=time=>({phase:String(time)});draw.call(atlas);assert.equal(atlas.frame.phase,'2');
});
test('an atlas without a clip neither samples nor draws',()=>{
 draw.call({sample(){throw Error('no clip');},get gl(){throw Error('no clip');}});
});
test('resuming rendering draws the current frame rather than a stale skipped frame',()=>{
 const calls=[];const gl=new Proxy({canvas:{width:0,height:0}}, {get(target,key){if(key in target)return target[key];if(String(key)===String(key).toUpperCase())return 0;return (...args)=>calls.push([key,...args]);}});
 const frame={positions:{},rotations:{},muscles:{primary:[],secondary:[]}};
 const atlas={clip:{equipment:[]},time:2,renderingSkipped:true,sample:()=>frame,gl,canvas:{clientWidth:320,clientHeight:400},
 bounds:{center:[0,0,0]},floor:{u:{model:0}},body:{u:{}},prop:{},parts:{plane:{vao:0,count:6}},model:{joints:[],groups:[],indexCount:3},wristJoints:[],uniforms(){}};
 // draw references the production transform helpers; inject minimal equivalents
 // for this GL-dispatch regression, not a geometry correctness assertion.
 const withHelpers=runInNewContext('class TestAtlas {\n'+source.slice(start)+'\nTestAtlas.prototype.draw',{transform:()=>[],identity:[],sub:()=>[],rotate:()=>[],qmul:()=>[],norm:()=>[],mul:()=>[]});
 withHelpers.call(atlas);assert.equal(calls.length,0);
 atlas.renderingSkipped=false;withHelpers.call(atlas);assert.equal(atlas.frame,frame);assert.ok(calls.some(([name])=>name==='drawElements'));
});

const controller=await readFile(new URL('./viewer.js',import.meta.url),'utf8');
const helperStart=controller.indexOf('function setCanvasRenderingSkipped(');
const helperEnd=controller.indexOf('// Skip GPU work only',helperStart);
const helper=controller.slice(helperStart,helperEnd);
test('intersection gate pauses and resumes GPU drawing independently of breakpoints',()=>{
 let draws=0;const atlas={draw(){draws++;}};
 const context={atlas,canvasRenderingSkipped:false};
 runInNewContext(helper+'\nsetCanvasRenderingSkipped(true);',context);
 assert.equal(atlas.renderingSkipped,true);assert.equal(draws,0);
 runInNewContext(helper+'\nsetCanvasRenderingSkipped(false);',context);
 assert.equal(atlas.renderingSkipped,false);assert.equal(draws,1);
});
test('visibility state can arrive before the atlas initializes',()=>{
 const context={atlas:undefined,canvasRenderingSkipped:false};
 runInNewContext(helper+'\nsetCanvasRenderingSkipped(true);',context);
 assert.equal(context.canvasRenderingSkipped,true);
});
const observerCode=controller.slice(controller.indexOf("if('IntersectionObserver'"),controller.indexOf('function message('));
test('unsupported observers retain normal rendering',()=>{
 runInNewContext(observerCode,{el(){throw Error('no observation without support');}});
});
test('observer uses latest entry, prewarms nearby canvas and observes its panel',()=>{
 const panel={};let callback,options,observed;const states=[];
 runInNewContext(observerCode,{IntersectionObserver:class{
  constructor(cb,opts){callback=cb;options=opts;}
  observe(target){observed=target;}
 },el:()=>({parentElement:panel}),setCanvasRenderingSkipped:x=>states.push(x)});
 assert.equal(options.rootMargin,'200px');assert.equal(observed,panel);
 callback([{isIntersecting:true},{isIntersecting:false}]);callback([{isIntersecting:true}]);callback([]);
 assert.deepEqual(states,[true,false]);
});
