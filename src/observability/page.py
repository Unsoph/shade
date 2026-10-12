"""Single static HTML page; polls /status and /decisions. No external assets."""

PAGE = """<!doctype html><meta charset="utf-8"><title>SHADE</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:light dark;font-family:system-ui,sans-serif}
body{margin:1rem auto;max-width:56rem;padding:0 1rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));gap:.6rem}
.card{border:1px solid #8884;border-radius:8px;padding:.6rem}
.card b{display:block;font-size:1.4rem}
table{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:1rem}
td,th{padding:.25rem .4rem;border-bottom:1px solid #8883;text-align:left}
#state{font-weight:700}
</style>
<h1>SHADE <small id=state></small></h1>
<div class=grid id=cards></div>
<h2>Decisions and events</h2>
<table><thead><tr><th>time<th>kind<th>state<th>rung<th>why</thead>
<tbody id=rows></tbody></table>
<script>
const fmt=t=>new Date(t*1000).toLocaleTimeString();
const text=(s)=>document.createTextNode(s);
async function tick(){
 try{
  const s=await (await fetch('status')).json();
  document.getElementById('state').textContent=s.state+' / '+s.rung_name;
  const cards=[['FPS',s.fps.toFixed(1)],['CPU C',s.cpu_temp.toFixed(1)],
   ['RAM %',s.memory_percent.toFixed(0)],['Rung',s.rung],
   ['Detections',s.detections],['Input',s.input_fault||'ok']];
  const box=document.getElementById('cards');box.replaceChildren();
  for(const [k,v] of cards){const d=document.createElement('div');d.className='card';
   d.append(text(k));const b=document.createElement('b');b.textContent=v;d.append(b);box.append(d);}
  const ev=await (await fetch('decisions')).json();
  const body=document.getElementById('rows');body.replaceChildren();
  for(const e of ev){const r=body.insertRow();
   const why=e.reasons.length?e.reasons.join(', '):JSON.stringify(e.detail);
   for(const v of [fmt(e.ts),e.kind,(e.from_state||'')+(e.to_state?' -> '+e.to_state:''),
    e.to_rung==null?'':e.from_rung+' -> '+e.to_rung,why])r.insertCell().textContent=v;}
 }catch(err){document.getElementById('state').textContent='offline';}
}
tick();setInterval(tick,1000);
</script>"""
