// Regression check for the simulator STOP defect. Needs puppeteer-core (NODE_PATH) and Chrome:
//   node check-simulator.js http://localhost:4173/simulator.html
const p=require('puppeteer-core'),sleep=ms=>new Promise(r=>setTimeout(r,ms));
const URL=process.argv[2]||'http://localhost:4173/simulator.html';
(async()=>{const b=await p.launch({executablePath:process.env.CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:'new'});
let fail=0;const ok=(n,c)=>{console.log((c?'PASS ':'FAIL ')+n);if(!c)fail++};
const status=pg=>pg.$eval('#s1',e=>e.textContent);
const start=async pg=>{await pg.type('#q','red jacket');await pg.keyboard.press('Enter')};
for(const stage of ['plan','scan','target','follow']){
 const pg=await b.newPage();await pg.goto(URL);
 await pg.evaluate(()=>{window.__h=[]});
 await start(pg);await sleep(800);                       // plan gate visible
 await pg.evaluate(()=>{window.__h.push(...document.querySelectorAll('#chat button'))});
 if(stage!=='plan'){await pg.click('#chat button');await pg.evaluate(()=>{window.__h.push(...document.querySelectorAll('#chat button'))});}
 if(stage==='target'||stage==='follow'){await sleep(1300);await pg.evaluate(()=>{window.__h.push(...document.querySelectorAll('#chat button'))});}
 if(stage==='follow'){await pg.click('#chat button');await sleep(200);}
 await pg.click('#stop');
 // stale clicks on every captured button + wait past every timer
 await pg.evaluate(()=>window.__h.forEach(b=>{b.disabled=false;b.onclick&&b.onclick();b.click()}));
 await sleep(2500);
 ok(`STOP at ${stage}: stays STOPPED after stale clicks`,await status(pg)==='STOPPED');
 ok(`STOP at ${stage}: no pending confirm buttons`,(await pg.$$('#chat button')).length===0);
 ok(`STOP at ${stage}: no completion logged`,!(await pg.$eval('#log',e=>e.textContent)).includes('landed'));
 if(stage==='follow'){
  await start(pg);await sleep(800);await pg.click('#chat button');await sleep(1200);await pg.click('#chat button');await sleep(2000);
  ok('fresh mission after STOP completes',await status(pg)==='LANDED');
 }
 await pg.close();}
await b.close();process.exit(fail?1:0)})();
