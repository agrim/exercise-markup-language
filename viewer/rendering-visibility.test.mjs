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
const helperEnd=controller.indexOf('// Listen directly:',helperStart);
const helper=controller.slice(helperStart,helperEnd);
test('desktop breakpoint clears the gate and ignores late mobile skip events',()=>{
 const mobileCanvas={matches:true};let draws=0;const atlas={draw(){draws++;}};
 const context={mobileCanvas,atlas,canvasRenderingSkipped:false};
 runInNewContext(helper+'\nsetCanvasRenderingSkipped(true);',context);
 assert.equal(atlas.renderingSkipped,true);assert.equal(draws,0);
 mobileCanvas.matches=false;
 runInNewContext(helper+'\nsetCanvasRenderingSkipped(false);setCanvasRenderingSkipped(true);',context);
 assert.equal(atlas.renderingSkipped,false);assert.equal(draws,2);
});
test('visibility state can arrive before the atlas initializes',()=>{
 const context={mobileCanvas:{matches:true},atlas:undefined,canvasRenderingSkipped:false};
 runInNewContext(helper+'\nsetCanvasRenderingSkipped(true);',context);
 assert.equal(context.canvasRenderingSkipped,true);
});
