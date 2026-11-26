'use strict';
const $ = id => document.getElementById(id);
const chat = $('chat'), input = $('question'), send = $('send'), clear = $('clear');
const welcome = chat.firstElementChild.cloneNode(true);
let busy = false;
function el(tag, text, cls) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (cls) node.className = cls; return node; }
function scroll() { chat.scrollTop = chat.scrollHeight; }
function update() { $('count').textContent = `${input.value.length} / 4000`; }
function cell(v) { return v === null || v === undefined ? 'NULL' : typeof v === 'object' ? JSON.stringify(v) : String(v); }
function render(data) {
  const card = el('article', undefined, 'message' + (data.status !== 'ok' ? ' error' : ''));
  card.append(el('strong', 'Database agent'), el('p', data.answer || 'No answer returned.', 'answer'));
  const meta = [data.status, Number.isFinite(data.latency_ms) ? `${data.latency_ms} ms` : '', data.request_id ? `ID: ${data.request_id}` : ''].filter(Boolean).join(' · ');
  card.append(el('div', meta, 'meta'));
  if (data.sql) {
    const details = el('details'); details.append(el('summary','Generated SQL'), el('pre',data.sql)); card.append(details);
  }
  const rows = Array.isArray(data.rows) ? data.rows : [];
  const columns = Array.isArray(data.columns) && data.columns.length ? data.columns : Object.keys(rows[0] || {});
  if (columns.length) {
    const details = el('details'); details.open = true; details.append(el('summary',`Returned rows (${rows.length})`));
    const wrap = el('div',undefined,'tablewrap'), table = el('table'), head = el('thead'), tr = el('tr');
    columns.forEach(c => {const th = el('th',c); th.scope='col'; tr.append(th);}); head.append(tr); table.append(head);
    const body = el('tbody'); rows.forEach(r => { const row = el('tr'); columns.forEach(c => row.append(el('td',cell(r[c])))); body.append(row); }); table.append(body); wrap.append(table); details.append(wrap); card.append(details);
  }
  chat.append(card); scroll();
}
input.addEventListener('input',update);
input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();if(!busy)$('form').requestSubmit();}});
$('examples').addEventListener('click',e=>{if(e.target.tagName==='BUTTON'&&!busy){input.value=e.target.textContent;update();input.focus();}});
clear.addEventListener('click',()=>{if(!busy){chat.replaceChildren(welcome.cloneNode(true));input.value='';update();input.focus();}});
$('form').addEventListener('submit',async e=>{
  e.preventDefault(); const question=input.value.trim(); if(busy||question.length<2||question.length>4000)return;
  busy=true; send.disabled=true; clear.disabled=true; input.disabled=true; $('examples').querySelectorAll('button').forEach(b=>b.disabled=true);
  chat.querySelector('.welcome')?.remove(); const user=el('article',undefined,'message user');user.append(el('strong','You'),el('div',question,'answer'));chat.append(user);
  input.value='';update(); const pending=el('div',undefined,'message pending');pending.append(el('span',undefined,'spinner'),el('span','Processing your question…'));chat.append(pending);scroll();
  try {
    const res=await fetch('/v1/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});
    const data=await res.json(); if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:`Request failed (HTTP ${res.status})`);
    render(data);
  }catch(err){render({status:'error',answer:err.message||'Could not reach the API.'});}
  finally{pending.remove();busy=false;send.disabled=false;clear.disabled=false;input.disabled=false;$('examples').querySelectorAll('button').forEach(b=>b.disabled=false);input.focus();scroll();}
});
fetch('/health').then(r=>{if(!r.ok)throw Error();return r.json();}).then(d=>{$('health').textContent=d.status==='ok'?'● API online':'API status unknown';}).catch(()=>{$('health').textContent='○ API unavailable';});
