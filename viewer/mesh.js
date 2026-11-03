// Atlas and apparatus share the solver's right-handed world coordinates.
const add = (a,b) => a.map((v,i) => v+b[i]);
const sub = (a,b) => a.map((v,i) => v-b[i]);
const mul = (a,n) => a.map(v => v*n);
const dot = (a,b) => a.reduce((s,v,i) => s+v*b[i],0);
const cross = (a,b) => [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const norm = a => mul(a,1/(Math.hypot(...a)||1));
const identity = [0,0,0,1];
function qmul(a,b) {
  return [...add(add(mul(a.slice(0,3),b[3]),mul(b.slice(0,3),a[3])),cross(a,b)), a[3]*b[3]-dot(a.slice(0,3),b)];
}
function rotate(q,v) {
  const t = mul(cross(q,v),2);
  return add(v,add(mul(t,q[3]),cross(q,t)));
}
function mix(a,b,t){return a.map((v,i)=>v+(b[i]-v)*t);}
function slerp(a,b,t){
  let d=dot(a,b);
  if(d<0){b=mul(b,-1);d=-d;}
  if(d>.9995)return norm(mix(a,b,t));
  const angle=Math.acos(Math.max(-1,Math.min(1,d)));
  return mul(add(mul(a,Math.sin((1-t)*angle)),mul(b,Math.sin(t*angle))),1/Math.sin(angle));
}
function transform(q,p,size=[1,1,1]) {
  return [...mul(rotate(q,[1,0,0]),size[0]),0,...mul(rotate(q,[0,1,0]),size[1]),0,
          ...mul(rotate(q,[0,0,1]),size[2]),0,...p,1];
}
const common = `uniform vec3 center, right, up, eye; uniform vec2 extent;
vec4 project(vec3 pos){vec3 p=pos-center;return vec4(dot(p,right)/extent.x,dot(p,up)/extent.y,-dot(p,eye)/8.,1.);}`;
const vertex = `#version 300 es
precision highp float;precision highp int;
layout(location=0) in vec3 pos;layout(location=1) in vec3 normal;
layout(location=2) in uvec4 joints;layout(location=3) in vec4 weights;
layout(location=4) in uint group;layout(location=5) in uint ao;
uniform mat4 skin[51];uniform vec4 palette[32];uniform vec2 sides;
out vec3 surface,n,world;out float visibility;
${common}
void main(){
  mat4 m=skin[joints.x]*weights.x+skin[joints.y]*weights.y+skin[joints.z]*weights.z+skin[joints.w]*weights.w;
  vec3 a=m[0].xyz,b=m[1].xyz,c=m[2].xyz;
  n=mat3(cross(b,c),cross(c,a),cross(a,b))*normal*sign(dot(a,cross(b,c)));
  vec4 mat=palette[group];surface=mat.rgb;
  if(mat.a<0.)surface=mix(vec3(.48,.55,.59),surface,mix(sides.y,sides.x,smoothstep(-.01,.01,pos.x)));
  uint light=ao&255u;visibility=light==0u?1.:float(light-1u)/254.;
  world=(m*vec4(pos,1.)).xyz;gl_Position=project(world);
}`;
const fragment = `#version 300 es
precision highp float;in vec3 surface,n,world;in float visibility;out vec4 color;uniform vec3 eye;
void main(){
 vec3 N=normalize(n),L=normalize(vec3(-.48,.79,.56)),V=normalize(eye);
 float key=max(dot(N,L),0.),fill=.5+.5*dot(N,normalize(vec3(.7,.25,-.44)));
 float ambient=(.40+.18*fill+.15*max(dot(N,V),0.))*mix(.48,1.,visibility);
 float spec=pow(max(dot(N,normalize(L+V)),0.),25.);
 color=vec4(surface*(ambient+.53*key)+.06*spec,1.);
}`;
const propVert = `#version 300 es
precision highp float;layout(location=0) in vec3 pos;layout(location=1) in vec3 normal;
uniform mat4 model; uniform vec3 tint;
out vec3 surface,n,world;out float visibility;
${common}
void main(){
 world=(model*vec4(pos,1.)).xyz;n=mat3(transpose(inverse(model)))*normal;
 surface=tint;visibility=1.;gl_Position=project(world);
}`;
const floorFrag = `#version 300 es
precision highp float;in vec3 world;out vec4 color;uniform vec3 center;
void main(){
 vec2 lines=abs(fract(world.xz*2.+.5)-.5)/max(fwidth(world.xz*2.),vec2(.0001));
 float grid=1.-min(min(lines.x,lines.y),1.);
 float dist=length(world.xz-center.xz);
 color=vec4(mix(vec3(.17,.21,.24),vec3(.28,.34,.37),grid*.48),
   .72*exp(-.24*dist*dist));
}`;
function shaderProgram(gl,vert,frag) {
  const program=gl.createProgram();
  for (const [type,source] of [[gl.VERTEX_SHADER,vert],[gl.FRAGMENT_SHADER,frag]]) {
    const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);
    if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader));
    gl.attachShader(program,shader);gl.deleteShader(shader);
  }
  gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));
  const u={};
  for(let i=0;i<gl.getProgramParameter(program,gl.ACTIVE_UNIFORMS);i++) {
    const name=gl.getActiveUniform(program,i).name;u[name.replace('[0]','')]=gl.getUniformLocation(program,name);
  }
  return {program,u};
}
function dataBuffer(gl,target,bytes) {
  const b=gl.createBuffer();gl.bindBuffer(target,b);gl.bufferData(target,bytes,gl.STATIC_DRAW);return b;
}
function mesh(gl,vertices) {
  const vao=gl.createVertexArray();gl.bindVertexArray(vao);dataBuffer(gl,gl.ARRAY_BUFFER,new Float32Array(vertices));
  for(const [slot,off] of [[0,0],[1,12]]){gl.enableVertexAttribArray(slot);gl.vertexAttribPointer(slot,3,gl.FLOAT,false,24,off);}
  return {vao,count:vertices.length/6};
}
function primitive(name) {
  const data=[];const point=(p,n)=>data.push(...p,...n);
  if(name==='plane') {
    for(const p of [[-.5,0,-.5],[.5,0,.5],[.5,0,-.5],[-.5,0,-.5],[-.5,0,.5],[.5,0,.5]])point(p,[0,1,0]);
  } else if(name==='box') {
    for(let axis=0;axis<3;axis++)for(const s of [-1,1])for(const [u,v] of [[-1,-1],[1,-1],[1,1],[-1,-1],[1,1],[-1,1]]) {
      const p=[0,0,0],n=[0,0,0];p[axis]=.5*s;p[(axis+1)%3]=.5*u;p[(axis+2)%3]=.5*v;n[axis]=s;point(p,n);
    }
  } else if(name==='rod') { // cylinders run along local X.
    for(let i=0;i<28;i++) {
      const a=i*Math.PI/14,b=(i+1)*Math.PI/14,n=t=>[0,Math.cos(t),Math.sin(t)];
      for(const [x,t] of [[-.5,a],[.5,b],[.5,a],[-.5,a],[-.5,b],[.5,b]])point([x,.5*Math.cos(t),.5*Math.sin(t)],n(t));
      for(const s of [-1,1]) {
        point([s/2,0,0],[s,0,0]);for(const t of [a,b])point([s/2,.5*Math.cos(t),.5*Math.sin(t)],[s,0,0]);
      }
    }
  } else {
    for(let y=0;y<14;y++)for(let x=0;x<24;x++)for(const [dx,dy] of [[0,0],[1,0],[1,1],[0,0],[1,1],[0,1]]) {
      const a=(x+dx)*Math.PI/12,b=(y+dy)*Math.PI/14-Math.PI/2;
      const n=[Math.cos(a)*Math.cos(b),Math.sin(b),Math.sin(a)*Math.cos(b)];point(mul(n,.5),n);
    }
  }
  return data;
}
function extent(clip,joints,kit) {
  // The camera stays fixed throughout the cycle. Include complete free weights;
  // remote stations may extend beyond the view so the moving anatomy remains legible.
  const points=[];
  for(const f of clip.frames){
    for(const joint of joints)points.push(f.positions[joint.name]);
    for(const item of clip.equipment){
      const spec=kit[item.kind],world=f.equipment[item.id];if(spec.category!=='free-weight')continue;
      const half=mul(spec.dimensions,.5);
      for(const a of [-1,1])for(const b of [-1,1])for(const c of [-1,1])
        points.push(add(world.position,rotate(world.rotation,[a*half[0],b*half[1],c*half[2]])));
    }
  }
  const lo=[Infinity,Infinity,Infinity],hi=lo.map(()=>-Infinity);
  for(const p of points)for(let i=0;i<3;i++){lo[i]=Math.min(lo[i],p[i]);hi[i]=Math.max(hi[i],p[i]);}
  const center=mul(add(lo,hi),.5);
  const corners=[];
  for(const x of [lo[0],hi[0]])for(const y of [lo[1],hi[1]])for(const z of [lo[2],hi[2]])corners.push(sub([x,y,z],center));
  return {center,corners};
}
export class Atlas {
  constructor(canvas,model,vertices,indices,kit) {
    const gl=canvas.getContext('webgl2',{antialias:true,alpha:true,preserveDrawingBuffer:true});
    if(!gl)throw new Error('A WebGL 2 capable browser is required for the atlas.');
    this.gl=gl;this.canvas=canvas;this.model=model;this.kit=kit;
    this.body=shaderProgram(gl,vertex,fragment);this.prop=shaderProgram(gl,propVert,fragment);this.floor=shaderProgram(gl,propVert,floorFrag);
    this.vao=gl.createVertexArray();gl.bindVertexArray(this.vao);dataBuffer(gl,gl.ARRAY_BUFFER,vertices);dataBuffer(gl,gl.ELEMENT_ARRAY_BUFFER,indices);
    for(const [slot,n,type,off,integer,normalized] of [[0,3,gl.FLOAT,0,false,false],[1,3,gl.FLOAT,12,false,false],
      [2,4,gl.UNSIGNED_BYTE,24,true,false],[3,4,gl.UNSIGNED_BYTE,28,false,true],[4,1,gl.UNSIGNED_INT,32,true,false],[5,1,gl.UNSIGNED_INT,36,true,false]]) {
      gl.enableVertexAttribArray(slot);if(integer)gl.vertexAttribIPointer(slot,n,type,40,off);else gl.vertexAttribPointer(slot,n,type,normalized,40,off);
    }
    this.parts=Object.fromEntries(['box','rod','sphere','plane'].map(name=>[name,mesh(gl,primitive(name))]));
    gl.enable(gl.DEPTH_TEST);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
    this.yaw=25;this.pitch=8;this.zoom=1;this.time=0;
    this.pointer=new Map();
    canvas.addEventListener('pointerdown',e=>{canvas.setPointerCapture(e.pointerId);this.pointer.set(e.pointerId,[e.clientX,e.clientY]);});
    canvas.addEventListener('pointermove',e=>{
      const old=this.pointer.get(e.pointerId);if(!old)return;
      const other=[...this.pointer].find(([id])=>id!==e.pointerId)?.[1];
      if(other){const a=Math.hypot(old[0]-other[0],old[1]-other[1]),b=Math.hypot(e.clientX-other[0],e.clientY-other[1]);if(a>1)this.scaleZoom(b/a);}
      else{this.yaw+=(e.clientX-old[0])*.5;this.pitch=Math.min(85,Math.max(-65,this.pitch+(e.clientY-old[1])*.35));}
      this.pointer.set(e.pointerId,[e.clientX,e.clientY]);this.draw();
    });
    for(const event of ['pointerup','pointercancel'])canvas.addEventListener(event,e=>this.pointer.delete(e.pointerId));
    canvas.addEventListener('wheel',e=>{e.preventDefault();this.scaleZoom(Math.exp(-e.deltaY*.001));this.draw();},{passive:false});
    new ResizeObserver(()=>this.draw()).observe(canvas);
  }
  scaleZoom(scale){this.zoom=Math.max(.45,Math.min(3.5,this.zoom*scale));}
  setClip(clip){this.clip=clip;this.bounds=extent(clip,this.model.joints,this.kit);this.time=0;this.camera('recipe');}
  camera(view){
    const [yaw,pitch]=({front:[0,8],side:[90,8],back:[180,8]})[view]||this.clip?.camera||[25,8];
    this.yaw=yaw;this.pitch=pitch;this.zoom=1;this.draw();
  }
  uniforms(program) {
    const gl=this.gl,u=program.u,rad=Math.PI/180,a=this.yaw*rad,b=this.pitch*rad;
    const right=[Math.cos(a),0,-Math.sin(a)],eye=[Math.sin(a)*Math.cos(b),Math.sin(b),Math.cos(a)*Math.cos(b)],up=cross(eye,right);
    const aspect=gl.canvas.width/gl.canvas.height,corners=this.bounds.corners;
    const halfWidth=Math.max(...corners.map(x=>Math.abs(dot(x,right))))+.11;
    const halfHeight=Math.max(...corners.map(x=>Math.abs(dot(x,up))))+.15;
    const radius=Math.max(.45,halfWidth/aspect,halfHeight)/this.zoom;
    gl.useProgram(program.program);gl.uniform3fv(u.center,this.bounds.center);gl.uniform3fv(u.right,right);gl.uniform3fv(u.up,up);gl.uniform3fv(u.eye,eye);
    gl.uniform2f(u.extent,radius*aspect,radius);
  }
  object(type,p,q,s,color) {
    const gl=this.gl,part=this.parts[type];gl.uniformMatrix4fv(this.prop.u.model,false,transform(q,p,s));gl.uniform3fv(this.prop.u.tint,color);
    gl.bindVertexArray(part.vao);gl.drawArrays(gl.TRIANGLES,0,part.count);
  }
  link(a,b,radius,color) {
    const d=sub(b,a),length=Math.hypot(...d);if(length<1e-5)return;
    const axis=mul(d,1/length),q=axis[0]<-.999999?[0,1,0,0]:norm([0,-axis[2],axis[1],1+axis[0]]);
    this.object('rod',mul(add(a,b),.5),q,[length,radius*2,radius*2],color);
  }
  drawProp(item,pose) {
    const spec=this.kit[item.kind];if(!spec)return;
    const metal=[.47,.55,.61],dark=[.23,.31,.36],pad=[.32,.40,.44];
    const parts=spec.visual||[{shape:spec.shape,dimensions:spec.dimensions}];
    for(const part of parts){
      const position=add(pose.position,rotate(pose.rotation,part.position||[0,0,0]));
      const angles=(part.rotation||[0,0,0]).map(a=>a*Math.PI/360),sin=Math.sin,cos=Math.cos;
      const rotation=qmul(pose.rotation,qmul([0,0,sin(angles[2]),cos(angles[2])],
        qmul([0,sin(angles[1]),0,cos(angles[1])],[sin(angles[0]),0,0,cos(angles[0])])));
      const [x,y,z]=part.dimensions,at=off=>add(position,rotate(rotation,off));
      const place=(name,off,size,col)=>this.object(name,at(off),rotation,size,col);
      if(part.shape==='barbell'||part.shape==='dumbbell'){
        const single=part.shape==='dumbbell';
        place('rod',[0,0,0],[x,.029,.029],metal);
        for(const sign of [-1,1]){
          const thickness=single?x*.24:Math.min(.12,x*.09);
          place('rod',[sign*(x/2-(single?.004:.055)-thickness/2),0,0],[thickness,y,z],dark);
        }
      }else if(part.shape==='kettlebell'){
        const r=z/2,w=x/2,cy=-(1.55*r+.02);
        place('sphere',[0,cy,0],[2*r,2*r,2*r],dark);
        this.link(at([-w*.74,0,0]),at([w*.74,0,0]),.0165,metal);
        for(const sign of [-1,1]){
          this.link(at([sign*w*.74,0,0]),at([sign*w,-.04,0]),.017,metal);
          this.link(at([sign*w,-.04,0]),at([sign*r*.55,cy+r*.65,0]),.017,metal);
        }
      }else if(part.shape==='rod')place('rod',[0,0,0],[x,y,z],metal);
      else if(part.shape==='ball')place('sphere',[0,0,0],[x,y,z],dark);
      else if(!spec.visual&&spec.category==='station'){
        // A legacy registry may lack components; retain visible sockets without a solid occluding block.
        for(const [key,e] of Object.entries(pose.sockets))if(key!=='center')this.object('sphere',e,identity,[.045,.045,.045],metal);
      }else place('box',[0,0,0],[x,y,z],part.material==='steel'?metal:pad);
    }
  }
  sample(time){
    const frames=this.clip.frames;
    let low=0,high=frames.length-1;
    while(low<high){const mid=(low+high)>>1;if(frames[mid].time<time)low=mid+1;else high=mid;}
    const b=frames[low];
    if(low===0||time===b.time)return b;
    const a=frames[low-1],t=(time-a.time)/(b.time-a.time);
    const rotations={},positions={},worlds=[];
    this.model.joints.forEach((joint,i)=>{
      const name=joint.name,parent=joint.parent,q=slerp(a.rotations[name],b.rotations[name],t);
      rotations[name]=q;
      worlds[i]=parent<0?q:qmul(worlds[parent],q);
      if(parent<0)positions[name]=mix(a.positions[name],b.positions[name],t);
      else{
        const bindParent=this.model.joints[parent];
        positions[name]=add(positions[bindParent.name],rotate(worlds[parent],sub(joint.position,bindParent.position)));
      }
    });
    const equipment={};
    for(const item of this.clip.equipment){
      const from=a.equipment[item.id],to=b.equipment[item.id],sockets={};
      for(const key of Object.keys(from.sockets))sockets[key]=mix(from.sockets[key],to.sockets[key],t);
      equipment[item.id]={position:mix(from.position,to.position,t),rotation:slerp(from.rotation,to.rotation,t),sockets};
    }
    return {...b,rotations,positions,equipment,diagnostics:(t<.5?a:b).diagnostics};
  }
  draw() {
    if(!this.clip)return;
    const gl=this.gl,dpr=Math.min(2,globalThis.devicePixelRatio||1);
    const w=Math.max(1,Math.round(this.canvas.clientWidth*dpr)),h=Math.max(1,Math.round(this.canvas.clientHeight*dpr));
    if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h;}
    gl.viewport(0,0,w,h);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    const frame=this.sample(this.time);
    this.frame=frame;
    this.uniforms(this.floor);gl.uniformMatrix4fv(this.floor.u.model,false,transform(identity,[this.bounds.center[0],-.018,this.bounds.center[2]],[12,1,12]));
    gl.bindVertexArray(this.parts.plane.vao);gl.depthMask(false);gl.drawArrays(gl.TRIANGLES,0,this.parts.plane.count);gl.depthMask(true);
    this.uniforms(this.body);
    const worlds=[],bones=[];
    this.model.joints.forEach((j,i)=>{
      const q=frame.rotations[j.name],world=j.parent<0?q:qmul(worlds[j.parent],q);worlds.push(world);
      bones.push(...transform(world,sub(frame.positions[j.name],rotate(world,j.position))));
    });
    const roles=frame.muscles||this.clip.muscles,restricted=this.clip.sideFocus?.groups||frame.sideGroups||[];
    const palette=this.model.groups.flatMap(group=>{
      if(roles.primary.includes(group))return [1,.36,.25,restricted.includes(group)?-1:1];
      if(roles.secondary.includes(group))return [1,.72,.31,restricted.includes(group)?-1:1];
      return group==='bone'?[.78,.76,.7,1]:group==='tendon'?[.72,.71,.67,1]:[.53,.60,.64,1];
    });
    gl.uniformMatrix4fv(this.body.u.skin,false,bones);gl.uniform4fv(this.body.u.palette,palette);
    gl.uniform2fv(this.body.u.sides,frame.sideWeights||[1,1]);gl.bindVertexArray(this.vao);gl.drawElements(gl.TRIANGLES,this.model.indexCount,gl.UNSIGNED_INT,0);
    this.uniforms(this.prop);
    for(const item of this.clip.equipment)this.drawProp(item,frame.equipment[item.id]);
    for(const edge of this.clip.connections||[]){
      const a=frame.equipment[edge.from.item].sockets[edge.from.socket],b=frame.equipment[edge.to.item].sockets[edge.to.socket];
      this.link(a,b,edge.kind==='rope'?.012:.006,edge.kind==='band'?[.79,.58,.28]:[.55,.64,.65]);
    }
  }
}
