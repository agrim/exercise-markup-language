import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';
const source=await readFile(new URL('./viewer.js',import.meta.url),'utf8');
const start=source.indexOf('function bindParameterError(');
const end=source.indexOf('function parameters(',start);
assert.ok(start>=0&&end>start);
function field(){
 const announcements=[],clears=[];
 const attrs=new Map([['aria-invalid','false']]),events={};
 const input={validity:{valid:false},validationMessage:'Please enter a value.',
 addEventListener:(type,fn)=>events[type]=fn,
 setAttribute:(k,v)=>attrs.set(k,v),getAttribute:k=>attrs.get(k),removeAttribute:k=>attrs.delete(k)};
 const error={id:'parameter-0-error',hidden:true,textContent:''};
 runInNewContext(source.slice(start,end)+'\nbindParameterError(input,error,announce,clear);',{input,error,announce:()=>announcements.push(error.textContent),clear:(field)=>clears.push(field)});
 return {input,error,events,attrs,announcements,clears};
}
test('untouched or first-edited invalid fields do not announce premature errors',()=>{
 const {error,events,attrs}=field();events.input();
 assert.equal(error.hidden,true);assert.equal(attrs.get('aria-invalid'),'false');assert.equal(attrs.has('aria-describedby'),false);
});
test('failed native validation retains associated error without canceling browser focus',()=>{
 const {input,error,events,attrs}=field();events.invalid();
 assert.equal(error.hidden,false);assert.equal(error.textContent,input.validationMessage);
 assert.equal(attrs.get('aria-invalid'),'true');assert.equal(attrs.get('aria-describedby'),error.id);
});
test('correction removes error association and subsequent submit can show a new error',()=>{
 const {input,error,events,attrs}=field();events.invalid();input.validity.valid=true;events.input();
 assert.equal(error.hidden,true);assert.equal(error.textContent,'');assert.equal(attrs.get('aria-invalid'),'false');assert.equal(attrs.has('aria-describedby'),false);
 input.validity.valid=false;input.validationMessage='Value must be less than or equal to 4.';events.invalid();
 assert.equal(error.textContent,input.validationMessage);assert.equal(attrs.get('aria-describedby'),error.id);
});
test('range corrections keep current validation text and separate fields independent',()=>{
 const a=field(),b=field();a.events.invalid();a.input.validationMessage='Value must be greater than or equal to 1.';a.events.input();
 assert.equal(a.error.textContent,a.input.validationMessage);assert.equal(b.error.hidden,true);
});
test('dynamically generated labels explicitly identify their controls',()=>{
 assert.match(source,/input\.id=`parameter-\$\{host\.childElementCount\}`;label\.htmlFor=input\.id/);
 assert.match(source,/error\.id=input\.id\+'-error'/);
});

test('untouched blur is silent, edited blur exposes and announces error once',()=>{
 const f=field();f.events.blur();assert.equal(f.error.hidden,true);assert.equal(f.announcements.length,0);
 f.events.input();f.events.blur();assert.equal(f.error.hidden,false);assert.equal(f.announcements.length,1);
 f.events.blur();assert.equal(f.announcements.length,1);
});
test('correction clears announcement and a new invalid edit announces on blur',()=>{
 const f=field();f.events.input();f.events.blur();
 f.input.validity.valid=true;f.events.input();assert.equal(f.clears.at(-1),f.input);
 f.input.validity.valid=false;f.events.input();assert.equal(f.announcements.length,1);
 f.events.blur();assert.equal(f.announcements.length,2);
});
test('native failed submit clears pending announcement and relies on focus',()=>{
 const f=field();f.events.input();f.events.blur();f.events.invalid();
 assert.equal(f.clears.at(-1),undefined);f.events.blur();assert.equal(f.announcements.length,1);
});
test('delayed announcements coalesce, cancel on correction and ignore disconnected fields',()=>{
 const a=source.indexOf('let parameterAnnouncementTimer;');const b=source.indexOf('// Keep native validation',a);
 const timers=new Map();let id=0;const region={textContent:''};const context={el:()=>region,
  setTimeout:fn=>{timers.set(++id,fn);return id;},clearTimeout:id=>timers.delete(id)};
 runInNewContext(source.slice(a,b),context);
 const input={isConnected:true,labels:[{textContent:'Depth'}],getAttribute:()=> 'true'};
 context.announceParameterError(input,{textContent:'Too low'});assert.equal(region.textContent,'');
 context.announceParameterError(input,{textContent:'Too high'});assert.equal(timers.size,1);
 const callback=timers.values().next().value;timers.clear();callback();assert.equal(region.textContent,'Depth: Too high');
 context.clearParameterAnnouncement(input);assert.equal(region.textContent,'');
 context.announceParameterError(input,{textContent:'Removed'});input.isConnected=false;
 timers.values().next().value();assert.equal(region.textContent,'');
 context.clearParameterAnnouncement();assert.equal(timers.size,0);
});

test('returning focus cancels pending speech for that field',()=>{
 const f=field();f.events.input();f.events.blur();f.events.focus();
 assert.equal(f.clears.at(-1),f.input);assert.equal(f.error.hidden,false);
});
