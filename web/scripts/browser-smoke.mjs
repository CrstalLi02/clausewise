import { spawn } from "node:child_process";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const base = "http://localhost:8080";
const roles = [
  { key: "student", username: "student", password: "student123", expected: "Policy Q&A Workspace" },
  { key: "department", username: "jwc_admin", password: "admin123", expected: "Department Governance Workspace" },
  { key: "super", username: "admin", password: "admin123", expected: "Super Admin Workspace" },
];

const delay = (ms) => new Promise(r => setTimeout(r, ms));
async function connect(url) {
  const ws = new WebSocket(url); await new Promise((ok, fail) => { ws.onopen = ok; ws.onerror = fail; });
  let seq = 0; const pending = new Map();
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { const {ok,fail}=pending.get(m.id); pending.delete(m.id); m.error?fail(new Error(m.error.message)):ok(m.result); } };
  const call = (method, params={}) => new Promise((ok,fail)=>{const id=++seq;pending.set(id,{ok,fail});ws.send(JSON.stringify({id,method,params}))});
  return { ws, call };
}
async function waitFor(call, expression, timeout=15000) {
  const start=Date.now();
  while(Date.now()-start<timeout){const r=await call("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true});if(r.result.value)return r.result.value;await delay(250)}
  throw new Error(`timeout: ${expression}`);
}
async function run(role, port) {
  const profile=await mkdtemp(join(tmpdir(),`clausewise-${role.key}-`));
  const proc=spawn(chrome,["--headless=new","--disable-gpu","--hide-scrollbars","--no-first-run","--no-default-browser-check",`--remote-debugging-port=${port}`,`--user-data-dir=${profile}`,"--window-size=1440,1000",base],{stdio:"ignore"});
  try {
    let pages; for(let i=0;i<40;i++){try{pages=await fetch(`http://127.0.0.1:${port}/json`).then(r=>r.json());if(pages.length)break}catch{}await delay(250)}
    const page=pages.find(p=>p.type==="page"); const {ws,call}=await connect(page.webSocketDebuggerUrl);
    await call("Page.enable"); await call("Runtime.enable");
    await waitFor(call,`document.querySelector('input[placeholder=\"Enter your username\"]') !== null`);
    await call("Runtime.evaluate",{expression:`(()=>{const set=(el,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}))};const a=document.querySelector('input[placeholder=\"Enter your username\"]');const p=document.querySelector('input[type=password]');set(a,${JSON.stringify(role.username)});set(p,${JSON.stringify(role.password)});document.querySelector('form').requestSubmit();})()`});
    await waitFor(call,`document.body.innerText.includes(${JSON.stringify(role.expected)})`,20000);
    const errors=await call("Runtime.evaluate",{expression:`({title:document.title,text:document.body.innerText.slice(0,5000),w:document.documentElement.scrollWidth,vw:document.documentElement.clientWidth})`,returnByValue:true});
    if(errors.result.value.w>errors.result.value.vw+2) throw new Error(`horizontal overflow ${errors.result.value.w}/${errors.result.value.vw}`);
    const checked=[];
    if(role.key!=="student"){
      const nav=[
        ["Overview","Loop Progressive Exit"],["Knowledge Assets","Department and Policy Fact Governance"],
        ["Trusted Review","Review Center"],["Evolution Loop","How feedback changes the next round"],
        ["Memory & Experiments","Policy fact plane"],["Agent Network","Department Sub-Agent Visualization"],
      ];
      for(const [label,expected] of nav){
        await call("Runtime.evaluate",{expression:`[...document.querySelectorAll('button')].find(b=>b.innerText.includes(${JSON.stringify(label)}))?.click()`});
        await waitFor(call,`document.body.innerText.includes(${JSON.stringify(expected)})`);checked.push(label);
        if(role.key==="super"){const tabShot=await call("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});await writeFile(`/tmp/clausewise-super-${label.replace(/\s/g,'-')}.png`,Buffer.from(tabShot.data,"base64"));}
      }
      const text=(await call("Runtime.evaluate",{expression:`document.body.innerText`,returnByValue:true})).result.value;
      await call("Runtime.evaluate",{expression:`[...document.querySelectorAll('button')].find(b=>b.innerText.includes('Knowledge Assets'))?.click()`});await delay(300);
      const assetText=(await call("Runtime.evaluate",{expression:`document.body.innerText`,returnByValue:true})).result.value;
      await call("Runtime.evaluate",{expression:`[...document.querySelectorAll('button')].find(b=>b.innerText.includes('Evolution Loop'))?.click()`});await delay(300);
      const loopText=(await call("Runtime.evaluate",{expression:`document.body.innerText`,returnByValue:true})).result.value;
      if(role.key==="department" && (assetText.includes("New Department") || loopText.includes("Trigger a new Loop"))) throw new Error("department admin sees global mutations");
      if(role.key==="super" && (!assetText.includes("New Department") || !loopText.includes("Trigger a new Loop"))) throw new Error("super admin missing global mutations");
      await call("Runtime.evaluate",{expression:`[...document.querySelectorAll('button')].find(b=>b.innerText.includes('Memory & Experiments'))?.click()`}); await delay(1000);
      await waitFor(call,`document.body.innerText.includes('Policy fact plane')`);
    } else {
      const welcomeShot=await call("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});
      await writeFile("/tmp/clausewise-student-welcome.png",Buffer.from(welcomeShot.data,"base64"));
      await call("Runtime.evaluate",{expression:`[...document.querySelectorAll('button')].find(b=>b.innerText.includes('My long-term memory'))?.click()`}); await delay(500);
      await waitFor(call,`document.body.innerText.includes('My long-term memory')`);
      await call("Runtime.evaluate",{expression:`[...document.querySelectorAll('section button')].find(b=>b.innerText==='×')?.click()`});
      const clicked=(await call("Runtime.evaluate",{expression:`(()=>{const x=document.querySelector('div[class*=sessionItem]');if(x){x.click();return true}return false})()`,returnByValue:true})).result.value;
      if(clicked){await waitFor(call,`document.body.innerText.includes('View ') && document.body.innerText.includes('policy sources')`,15000);checked.push("Session history and citations");}
    }
    const shot=await call("Page.captureScreenshot",{format:"png",captureBeyondViewport:false});await writeFile(`/tmp/clausewise-${role.key}.png`,Buffer.from(shot.data,"base64"));
    ws.close(); return {role:role.key, title:errors.result.value.title, overflow:false, checked, screenshot:`/tmp/clausewise-${role.key}.png`};
  } finally { proc.kill("SIGTERM"); await delay(300); await rm(profile,{recursive:true,force:true}); }
}
const results=[];for(let i=0;i<roles.length;i++)results.push(await run(roles[i],9333+i));console.log(JSON.stringify(results,null,2));
