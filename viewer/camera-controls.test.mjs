import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {adjustCamera} from './camera-controls.js';
function camera() {
  return {yaw:25,pitch:8,zoom:1,draws:0,
    scaleZoom(scale){this.zoom=Math.max(.45,Math.min(3.5,this.zoom*scale));},
    draw(){this.draws++;}};
}
test('camera controls safely ignore unavailable model and unknown actions',()=>{
  adjustCamera(undefined,'left');const a=camera();adjustCamera(a,'unknown');assert.equal(a.draws,0);
});
test('rotation supports both axes and retains pointer pitch bounds',()=>{
  const a=camera();adjustCamera(a,'left');assert.equal(a.yaw,15);
  adjustCamera(a,'right');assert.equal(a.yaw,25);
  adjustCamera(a,'up');assert.equal(a.pitch,13);
  adjustCamera(a,'down');assert.equal(a.pitch,8);
  for(let i=0;i<40;i++)adjustCamera(a,'up');assert.equal(a.pitch,85);
  for(let i=0;i<40;i++)adjustCamera(a,'down');assert.equal(a.pitch,-65);
  assert.equal(a.draws,84);
});
test('zoom is reversible and retains existing renderer limits',()=>{
  const a=camera();adjustCamera(a,'in');assert.equal(a.zoom,1.15);
  adjustCamera(a,'out');assert.ok(Math.abs(a.zoom-1)<1e-12);
  for(let i=0;i<40;i++)adjustCamera(a,'in');assert.equal(a.zoom,3.5);
  for(let i=0;i<40;i++)adjustCamera(a,'out');assert.equal(a.zoom,.45);
});
test('native controls expose all camera actions and server serves their module',async()=>{
  const html=await readFile(new URL('./index.html',import.meta.url),'utf8');
  const actions=[...html.matchAll(/<button type="button" data-camera="([^"]+)">/g)].map(x=>x[1]);
  assert.deepEqual(actions,['left','right','up','down','in','out']);
  const server=await readFile(new URL('./__main__.py',import.meta.url),'utf8');
  assert.match(server,/"\/camera-controls\.js": "viewer\/camera-controls\.js"/);
});

test('rotation clamps recipe cameras that start outside the pointer range',()=>{
  for(const start of [-100,100])for(const action of ['up','down']) {
    const a=camera();a.pitch=start;adjustCamera(a,action);
    assert.equal(a.pitch,start<0?-65:85);assert.equal(a.draws,1);
  }
});
