import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {runInNewContext} from 'node:vm';
const source=await readFile(new URL('./viewer.js',import.meta.url),'utf8');
const start=source.indexOf('function bindParameterError(');
const end=source.indexOf('function parameters(',start);
assert.ok(start>=0&&end>start);
function field(){
 const attrs=new Map([['aria-invalid','false']]),events={};
 const input={validity:{valid:false},validationMessage:'Please enter a value.',
 addEventListener:(type,fn)=>events[type]=fn,
 setAttribute:(k,v)=>attrs.set(k,v),getAttribute:k=>attrs.get(k),removeAttribute:k=>attrs.delete(k)};
 const error={id:'parameter-0-error',hidden:true,textContent:''};
 runInNewContext(source.slice(start,end)+'\nbindParameterError(input,error);',{input,error});
 return {input,error,events,attrs};
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
