const b=document.querySelector('.burger'),m=document.getElementById('mm'),bg=[document.querySelector('main'),document.querySelector('footer')];
const set=(o,restore)=>{m.classList.toggle('open',o);b.setAttribute('aria-expanded',o);b.setAttribute('aria-label',o?'Close menu':'Open menu');document.body.style.overflow=o?'hidden':'';
 bg.forEach(e=>o?e.setAttribute('inert',''):e.removeAttribute('inert'));if(!o&&restore)b.focus()};
b.onclick=()=>set(!m.classList.contains('open'),true);
m.querySelectorAll('a').forEach(a=>a.onclick=()=>set(false));
// keep Tab inside header + menu while the menu is open
addEventListener('keydown',e=>{if(!m.classList.contains('open'))return;
 if(e.key==='Escape'){set(false,true);return}
 if(e.key!=='Tab')return;
 const f=[...document.querySelectorAll('.hdr a,.hdr button,#mm a')].filter(x=>x.offsetParent!==null||x===b),i=f.indexOf(document.activeElement);
 if(e.shiftKey&&(i<=0)){e.preventDefault();f[f.length-1].focus()}else if(!e.shiftKey&&(i===f.length-1||i<0)){e.preventDefault();f[0].focus()}});
// leaving the mobile layout must never leave the page inert or scroll-locked
matchMedia('(min-width:901px)').addEventListener('change',e=>{if(e.matches)set(false)});
const s=document.getElementById('stmt');
s.innerHTML=s.textContent.split(' ').map(w=>`<span>${w}</span>`).join(' ');
const ws=[...s.children];
const upd=()=>{const r=s.getBoundingClientRect(),p=Math.min(1,Math.max(0,(innerHeight*.8-r.top)/(r.height+innerHeight*.25)));ws.forEach((w,i)=>w.classList.toggle('on',i/ws.length<p))};
addEventListener('scroll',upd,{passive:true});upd();
const car=document.getElementById('car'),rm=matchMedia('(prefers-reduced-motion:reduce)').matches;
let hold=false;car.onmouseenter=car.onfocusin=()=>hold=true;car.onmouseleave=car.onfocusout=()=>hold=false;
if(!rm)setInterval(()=>{if(hold||document.hidden)return;const w=car.firstElementChild.offsetWidth;
 if(car.scrollLeft+car.clientWidth>=car.scrollWidth-4)car.scrollTo({left:0,behavior:'smooth'});else car.scrollBy({left:w,behavior:'smooth'})},3500);
document.getElementById('nlf').onsubmit=e=>{e.preventDefault();const n=document.getElementById('nlm');n.textContent='Subscriptions are not available yet. Nothing was sent.'};
