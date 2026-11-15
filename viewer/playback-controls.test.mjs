import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';

// Exercise the viewer's actual refresh function with a minimal DOM/renderer.
// This checks its accessible value without requiring a WebGL browser context.
const source=await readFile(new URL('./viewer.js',import.meta.url),'utf8');
const start=source.indexOf('function refresh() {');
const end=source.indexOf('function stop()',start);
assert.ok(start>=0&&end>start,'Viewer should expose a refresh function to test');
const refreshSource=source.slice(start,end);

for(const [time,duration,position,spoken] of [
  [0,4,0,'0.00 seconds of 4.00 seconds'],
  [1.25,4,313,'1.25 seconds of 4.00 seconds'],
  [4,4,1000,'4.00 seconds of 4.00 seconds'],
  [2.5,10,250,'2.50 seconds of 10.00 seconds'],
]) {
  test(`playback value exposes elapsed seconds at ${time}/${duration}`,()=>{
    const elements=new Map();
    const el=id=>{
      if(!elements.has(id))elements.set(id,{
        attributes:{},setAttribute(name,value){this.attributes[name]=value;},
      });
      return elements.get(id);
    };
    const atlas={time,draw(){},frame:{phase:'hold',muscles:{primary:[],secondary:[]},diagnostics:[]}};
    runInNewContext(refreshSource+'\nrefresh();',{
      atlas,clip:{duration},recipe:undefined,el,titleCase:value=>value,
    });
    assert.equal(el('scrub').value,position);
    assert.equal(el('scrub').attributes['aria-valuetext'],spoken);
    assert.equal(el('clock').textContent,time.toFixed(2)+' s');
  });
}
