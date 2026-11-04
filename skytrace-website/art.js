// Procedural iridescent artwork: flowing bands, luminous rims, dark folds.
// Rendered by one small WebGL fragment shader per canvas, driven by a single shared rAF loop.
// The CPU functions F below are only the static fallback (no WebGL / context lost / reduced motion without GL).
(()=>{
const clamp=(x,a,b)=>x<a?a:x>b?b:x,sm=(a,b,x)=>{x=clamp((x-a)/(b-a),0,1);return x*x*(3-2*x)};
const mx=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t];
const K={gold:[.98,.85,.52],blue:[.1,.36,1],cyan:[.25,.82,.95],pink:[.95,.5,.82],pur:[.52,.28,.9],brn:[.4,.31,.18],navy:[.01,.02,.08]};
const B=[0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5].map(x=>x/16);
const F={
 hero(u,v,t){
  const wu=u+.05*Math.sin(3*v+t)+.03*Math.sin(7*u-t*1.3),wv=v+.06*Math.sin(2.4*u-t*.8);
  const s=wu*.7+wv*1.0,band=.5+.5*Math.sin(s*9+2.2*Math.sin(wu*3.2+t*.6)+1.5*Math.cos(wv*4-t*.5));
  let c=mx(K.brn,K.gold,sm(.5,1.02,wv));
  c=mx(c,mx(K.cyan,K.blue,sm(.1,.6,wv)),Math.exp(-Math.pow((wu-.04)/.2,2))*sm(.08,.5,wv)*(1-sm(.62,.82,wv)));
  c=mx(c,K.pur,Math.exp(-Math.pow((wu-.1)/.17,2))*sm(.4,.6,wv)*(1-sm(.68,.85,wv))*.9);
  c=mx(c,mx(K.blue,K.pink,sm(.2,.8,wu)),Math.exp(-(Math.pow((wu-.96)/.16,2)+Math.pow((wv-1)/.2,2))));
  const dark=.08+.9*sm(.15,.9,band);
  const rim=Math.exp(-Math.pow((band-.8)*8,2))*.28;
  const top=1-sm(.0,.4,wv)*0; // top fade is applied by CSS mask
  return [c[0]*dark+rim*.35,c[1]*dark+rim*.6,c[2]*dark+rim*.8];
 },
 cta(u,v,t){
  const wu=u+.05*Math.sin(2.2*v+t*.8),wv=v+.06*Math.sin(2*u-t*.6);
  const side=sm(.1,.42,Math.abs(wu-.5)),e=wu<.5?wu:1-wu,s=e*2.4+wv*(wu<.5?1.5:-1.1);
  const band=.5+.5*Math.sin(s*5.2+1.4*Math.sin(wv*3.1+t*.5)+(wu<.5?0:2.4));
  let c=mx(K.blue,K.gold,sm(.2,.8,.5+.5*Math.sin(s*2.4+t*.4)));
  c=mx(c,K.pink,sm(.78,1,band)*.45);c=mx(c,K.navy,sm(.7,.1,band)*.7);
  const dark=(.06+.95*sm(.2,.85,band))*side,rim=Math.exp(-Math.pow((band-.82)*8,2))*.22*side;
  return [c[0]*dark+rim*.6,c[1]*dark+rim*.8,c[2]*dark+rim];
 },
 stage(u,v,t,h){
  const wu=u+.07*Math.sin(3.4*v+t)+.04*Math.sin(8*u-t),wv=v+.08*Math.sin(2.6*u+t*.7);
  const s=wu*1.05+wv*.8,ph=h/360;
  const c=[.5+.26*Math.cos(6.283*(s*.8+ph)),.48+.24*Math.cos(6.283*(s*.8+ph+.33)),.52+.28*Math.cos(6.283*(s*.8+ph+.67))];
  const band=.5+.5*Math.sin(s*7+2*Math.sin(wv*3.4));
  const d=(.3+.85*sm(.1,.8,band))*(1-.45*sm(.3,1,wv)*sm(.2,1,wu));
  return [Math.pow(c[0],1.3)*d*.85,Math.pow(c[1],1.3)*d*.85,Math.pow(c[2],1.3)*d*.85];
 }};

const FS=`precision highp float;
uniform vec2 R;uniform float T,H;uniform int K;
float sm(float a,float b,float x){x=clamp((x-a)/(b-a),0.,1.);return x*x*(3.-2.*x);}
float sq(float x){return x*x;}
const vec3 gold=vec3(.98,.85,.52),blue=vec3(.1,.36,1.),cyan=vec3(.25,.82,.95),pink=vec3(.95,.5,.82),pur=vec3(.52,.28,.9),brn=vec3(.4,.31,.18),navy=vec3(.01,.02,.08);
vec3 hero(float u,float v,float t){
 float wu=u+.05*sin(3.*v+t)+.03*sin(7.*u-t*1.3),wv=v+.06*sin(2.4*u-t*.8);
 float s=wu*.7+wv,band=.5+.5*sin(s*9.+2.2*sin(wu*3.2+t*.6)+1.5*cos(wv*4.-t*.5));
 vec3 c=mix(brn,gold,sm(.5,1.02,wv));
 c=mix(c,mix(cyan,blue,sm(.1,.6,wv)),exp(-sq((wu-.04)/.2))*sm(.08,.5,wv)*(1.-sm(.62,.82,wv)));
 c=mix(c,pur,exp(-sq((wu-.1)/.17))*sm(.4,.6,wv)*(1.-sm(.68,.85,wv))*.9);
 c=mix(c,mix(blue,pink,sm(.2,.8,wu)),exp(-(sq((wu-.96)/.16)+sq((wv-1.)/.2))));
 float dark=.08+.9*sm(.15,.9,band),rim=exp(-sq((band-.8)*8.))*.28;
 return vec3(c.r*dark+rim*.35,c.g*dark+rim*.6,c.b*dark+rim*.8);}
vec3 cta(float u,float v,float t){
 float wu=u+.05*sin(2.2*v+t*.8),wv=v+.06*sin(2.*u-t*.6);
 float side=sm(.1,.42,abs(wu-.5)),e=wu<.5?wu:1.-wu,s=e*2.4+wv*(wu<.5?1.5:-1.1);
 float band=.5+.5*sin(s*5.2+1.4*sin(wv*3.1+t*.5)+(wu<.5?0.:2.4));
 vec3 c=mix(blue,gold,sm(.2,.8,.5+.5*sin(s*2.4+t*.4)));
 c=mix(c,pink,sm(.78,1.,band)*.45);c=mix(c,navy,sm(.7,.1,band)*.7);
 float dark=(.06+.95*sm(.2,.85,band))*side,rim=exp(-sq((band-.82)*8.))*.22*side;
 return vec3(c.r*dark+rim*.6,c.g*dark+rim*.8,c.b*dark+rim);}
vec3 stage(float u,float v,float t,float h){
 float wu=u+.07*sin(3.4*v+t)+.04*sin(8.*u-t),wv=v+.08*sin(2.6*u+t*.7);
 float s=wu*1.05+wv*.8,ph=h/360.;
 vec3 c=vec3(.5+.26*cos(6.283*(s*.8+ph)),.48+.24*cos(6.283*(s*.8+ph+.33)),.52+.28*cos(6.283*(s*.8+ph+.67)));
 float band=.5+.5*sin(s*7.+2.*sin(wv*3.4)),d=(.3+.85*sm(.1,.8,band))*(1.-.45*sm(.3,1.,wv)*sm(.2,1.,wu));
 return pow(max(c,0.),vec3(1.3))*d*.85;}
float b2(vec2 a){a=floor(a);return fract(a.x/2.+a.y*a.y*.75);}
float bayer(vec2 a){return b2(.5*a)*.25+b2(a);}
void main(){
 float u=gl_FragCoord.x/R.x,v=1.-gl_FragCoord.y/R.y;vec3 c;
 if(K==0)c=hero(u,v,T);else if(K==1)c=cta(u,v,T);
 else{c=stage(u,v,T,H);float q=(bayer(gl_FragCoord.xy)-.5)/7.;c=floor((c+q)*7.+.5)/7.;}
 gl_FragColor=vec4(clamp(c,0.,1.),1.);}`;
const VS='attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
const KIND={hero:0,cta:1,stage:2},RES={hero:2,cta:2,stage:4}; // css px per rendered pixel
const MAXPX=700000; // upper bound on rendered pixels per canvas
const rmq=matchMedia('(prefers-reduced-motion:reduce)');
const arts=[];let clock=0,last=0,raf=0,anyVisible=false;
function cpuStatic(c,t){ // fallback: one frame on a 2D canvas
 const k=c.dataset.art,sc=RES[k]*1.5,w=Math.max(8,Math.ceil(c.clientWidth/sc)),h=Math.max(8,Math.ceil(c.clientHeight/sc));
 c.width=w;c.height=h;const x=c.getContext('2d'),im=x.createImageData(w,h),d=im.data,hue=+c.dataset.hue||0,fn=F[k];
 for(let j=0;j<h;j++)for(let i=0;i<w;i++){let [r,g,b]=fn(i/w,j/h,t,hue),o=(j*w+i)*4;
  if(k==='stage'){const q=(B[(j&3)*4+(i&3)]-.5)/7;r=Math.floor((r+q)*7+.5)/7;g=Math.floor((g+q)*7+.5)/7;b=Math.floor((b+q)*7+.5)/7}
  d[o]=clamp(r,0,1)*255;d[o+1]=clamp(g,0,1)*255;d[o+2]=clamp(b,0,1)*255;d[o+3]=255}
 x.putImageData(im,0,0)}
function setup(c){
 const a={c,k:c.dataset.art,hue:+c.dataset.hue||0,vis:false,dirty:true,w:0,h:0,gl:null};
 const gl=c.getContext('webgl',{antialias:false,alpha:false,depth:false,stencil:false,powerPreference:'high-performance'});
 if(!gl){a.fail=true;return a}
 const sh=(t,s)=>{const o=gl.createShader(t);gl.shaderSource(o,s);gl.compileShader(o);return gl.getShaderParameter(o,gl.COMPILE_STATUS)?o:null};
 const vs=sh(gl.VERTEX_SHADER,VS),fs=sh(gl.FRAGMENT_SHADER,FS),pr=gl.createProgram();
 if(!vs||!fs){a.fail=true;return a}
 gl.attachShader(pr,vs);gl.attachShader(pr,fs);gl.linkProgram(pr);
 if(!gl.getProgramParameter(pr,gl.LINK_STATUS)){a.fail=true;return a}
 gl.useProgram(pr);const buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);
 gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),gl.STATIC_DRAW);
 const loc=gl.getAttribLocation(pr,'p');gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
 a.gl=gl;a.uR=gl.getUniformLocation(pr,'R');a.uT=gl.getUniformLocation(pr,'T');a.uH=gl.getUniformLocation(pr,'H');a.uK=gl.getUniformLocation(pr,'K');
 gl.uniform1i(a.uK,KIND[a.k]);gl.uniform1f(a.uH,a.hue);
 c.addEventListener('webglcontextlost',e=>{e.preventDefault();a.lost=true;toFallback(a)});
 return a}
function toFallback(a){ // GL unavailable: swap in a fresh canvas and paint one static CPU frame
 const n=a.c.cloneNode(false);a.c.replaceWith(n);ro.unobserve(a.c);io.unobserve(a.c);a.c=n;a.gl=null;a.fail=true;
 cpuStatic(n,clock);}
function size(a){ // only called when the observed size changed
 const rs=RES[a.k];let w=Math.max(8,Math.ceil(a.cw/rs)),h=Math.max(8,Math.ceil(a.ch/rs));
 const f=Math.sqrt(Math.min(1,MAXPX/(w*h)));w=Math.ceil(w*f);h=Math.ceil(h*f);
 if(a.c.width!==w||a.c.height!==h){a.c.width=w;a.c.height=h}
 a.gl.viewport(0,0,w,h);a.gl.uniform2f(a.uR,w,h);a.dirty=true}
function paint(a,t){a.gl.uniform1f(a.uT,t);a.gl.drawArrays(a.gl.TRIANGLES,0,3)}
// observers: size via ResizeObserver (coalesced into the next frame), visibility via IntersectionObserver
const byEl=new Map();
const ro=new ResizeObserver(es=>{es.forEach(e=>{const a=byEl.get(e.target);if(a){a.cw=e.contentRect.width;a.ch=e.contentRect.height;a.resize=true}});kick()});
const io=new IntersectionObserver(es=>{es.forEach(e=>{const a=byEl.get(e.target);if(a)a.vis=e.isIntersecting});anyVisible=arts.some(a=>a.vis);kick()},{rootMargin:'100px'});
document.querySelectorAll('canvas[data-art]').forEach(c=>{const a=setup(c);arts.push(a);byEl.set(c,a);ro.observe(c);io.observe(c)});
arts.forEach(a=>{if(a.fail){a.cw=a.c.clientWidth;a.ch=a.c.clientHeight;cpuStatic(a.c,0)}});
function animating(){return !rmq.matches&&!document.hidden&&anyVisible}
function frame(ts){
 raf=0;
 const dt=last?Math.min(ts-last,50):0;last=ts;clock+=dt/1000*.5; // clamped dt: no jump after a pause
 for(const a of arts){if(a.fail||a.lost)continue;
  if(a.resize){a.resize=false;size(a)}
  if(a.vis&&(a.dirty||animating())){paint(a,clock);a.dirty=false}}
 if(animating())raf=requestAnimationFrame(frame);else last=0}
function kick(){if(!raf)raf=requestAnimationFrame(frame)}
document.addEventListener('visibilitychange',()=>{last=0;kick()});
rmq.addEventListener('change',()=>{last=0;arts.forEach(a=>a.dirty=true);kick()}); // reduced motion toggled: static frame / resume
})();
