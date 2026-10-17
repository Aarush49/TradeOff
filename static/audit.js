// Render untrusted audit content as text, never HTML.
const $ = id => document.getElementById(id);
let auditData;
const amount = n => Number(n).toLocaleString(undefined,{style:'currency',currency:'USD',maximumFractionDigits:2});
const when = value => new Date(value).toLocaleString();
const pct = value => (value*100).toFixed(1)+'%';
function node(tag,text,className) {const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(className)element.className=className;return element;}
function grid(rows,columns) {
  const table=node('table'),head=node('tr'),body=node('tbody');
  for(const [,label] of columns)head.append(node('th',label));
  const thead=node('thead');thead.append(head);table.append(thead,body);
  for(const row of rows){const tr=node('tr');for(const [key] of columns)tr.append(node('td',row[key]??'—'));body.append(tr);}
  if(!rows.length){const tr=node('tr'),td=node('td','No records in this snapshot.');td.colSpan=columns.length;tr.append(td);body.append(tr);}
  return table;
}
function planTable(plan) {
  const box=node('div',undefined,'scroll');
  box.append(grid(plan.decisions||[],[['factory','Factory'],['requested','Requested'],['allocated','Allocated'],['unmet','Planned unmet']]));
  box.append(grid(plan.shipments||[],[['factory','Factory'],['supplier','Supply pool'],['quantity','Chips'],['arrival','Assumed arrival day']]));
  return box;
}
function render() {
  const data=auditData,run=$('run').value,current=data.current_run,summary=$('summary');
  summary.replaceChildren();
  if(run===current.run_id){
    const outcome=current.network.outcome,section=node('section');
    section.append(node('h2',outcome?'Revealed outcome':'Current approved plan'),node('p',`Approved revision ${current.approved_revision} · ${current.approved_by} · ${when(current.approved_at)}`,'muted'));
    const result=outcome?.result||current.approved_plan,metrics=node('div',undefined,'metrics');
    for(const [label,value] of [['Total simulated cost',amount(result.objective)],['Procurement',amount(result.procurement)],['Shortage penalty',amount(result.shortage_penalty)],['Hard minimum breaches',outcome?result.minimum_breaches:'Not revealed']]){const card=node('div',label,'card');card.append(node('strong',value));metrics.append(card);}
    section.append(metrics);
    if(outcome){section.append(node('p',`Primary shipment arrived on day ${outcome.actual_arrival_day}. ${result.unmet} chips unmet; ${result.minimum_breaches} hard minimum breaches.`,'notice'),grid(result.decisions,[['factory','Factory'],['allocated','Delivered by deadline'],['unmet','Unmet'],['minimum','Hard minimum']]));}
    section.append(node('h3','Approved shipment commitments'),planTable(current.approved_plan));
    section.append(node('p',outcome?outcome.accounting:'Outcome not yet revealed. Planned allocations are not proof of delivery.','muted'));summary.append(section);
  }else summary.append(node('p','Archived run: the timeline and proposals below come from retained audit records. This export includes a complete state and outcome summary only for the current run.','notice'));
  const actions=data.actions.filter(a=>a.run_id===run).sort((a,b)=>a.seq-b.seq);
  $('timeline').replaceChildren();
  const names={approved:'Allocation approved',rejected:'Proposal rejected',new_simulation_run:'Simulation started',event_accepted:'Event accepted',event_ignored_out_of_order:'Older event ignored',replay_pause:'Replay paused',replay_resume:'Replay resumed'};
  for(const action of actions){const item=node('li'),d=action.details;item.append(node('strong',names[action.action]||action.action.replaceAll('_',' ')),node('p',`${when(action.created_at)} · ${action.actor}`,'muted'));
    const parts=[];if(d.revision!=null)parts.push(`Revision ${d.revision}`);if(d.type)parts.push(d.type.replaceAll('_',' '));if(d.entity)parts.push(d.entity);if(d.scenario)parts.push(`Scenario: ${d.scenario}`);if(d.model_id)parts.push(`Model: ${d.model_id}`);if(d.note)parts.push(`Decision note: ${d.note}`);item.append(node('p',parts.join(' · ')));$('timeline').append(item);}
  if(!actions.length)$('timeline').append(node('li','No actions retained in this snapshot.'));
  $('proposals').replaceChildren();
  for(const proposal of data.proposals.filter(p=>p.run_id===run).sort((a,b)=>a.revision-b.revision)){
    const a=proposal.data.analysis,details=node('details');details.append(node('summary',`Revision ${proposal.revision} · ${a.action} · ${proposal.status}`));
    details.append(node('p',`${when(proposal.created_at)} · Model: ${a.model_id}`,'muted'));
    const forecast=node('div',undefined,'scroll');forecast.append(grid(a.forecast.map(f=>({...f,risk:pct(f.miss_probability)})),[['factory','Factory'],['deadline','Deadline day'],['risk','Modeled primary-shipment miss risk']]));details.append(forecast);
    if(a.recommended){const r=a.recommended;details.append(node('p',`Recommended reserve: ${r.reserve_quantity} chips. Expected cost: ${amount(r.expected_cost)}. Modeled hard minimum breach probability: ${pct(r.minimum_breach_probability)}.`),planTable(r.plan));}
    else details.append(node('p','No eligible recovery allocation recommended.'));
    details.append(node('p',a.policy.description,'muted'));$('proposals').append(details);
  }
  if(!$('proposals').children.length)$('proposals').append(node('p','No proposals retained in this snapshot.'));
  $('events').replaceChildren(grid(data.events.filter(e=>e.run_id===run).sort((a,b)=>a.seq-b.seq).map(e=>({time:when(e.received_at),type:e.payload.type.replaceAll('_',' '),entity:e.payload.entity,status:e.status,revision:e.revision,changes:Object.entries(e.payload.changes||{}).map(([k,v])=>`${k.replaceAll('_',' ')}: ${v}`).join('; '),latency:e.latency_ms.toFixed(2)+' ms'})),[['time','Received'],['type','Event'],['entity','Entity'],['revision','Revision'],['status','Status'],['changes','Reported changes'],['latency','Server processing']]));
  $('report').hidden=false;
}
async function load() {
  $('error').textContent='';$('refresh').disabled=true;
  try{
    const response=await fetch('/api/live/audit');if(response.status===401){window.location.replace('/login');return;}const data=await response.json();if(!response.ok)throw new Error(data.error||'Unable to load audit.');
    auditData=data;const previous=$('run').value,ids=[...new Set([data.current_run.run_id,...data.actions.map(a=>a.run_id),...data.events.map(e=>e.run_id),...data.proposals.map(p=>p.run_id)])];
    $('run').replaceChildren();for(const id of ids){const option=node('option',`${id===data.current_run.run_id?'Current':'Archived'} run · ${id.slice(0,8)}`);option.value=id;$('run').append(option);}if(ids.includes(previous))$('run').value=previous;
    $('snapshot').textContent=`Snapshot generated ${when(data.generated_at)}. Up to ${data.limit_per_collection} recent records per collection across all runs. Refresh to include new events. Server processing excludes browser, network, and human review time.`;
    for(const id of ['run','print','downloadJson'])$(id).disabled=false;render();
  }catch(error){$('error').textContent=error.message;}finally{$('refresh').disabled=false;}
}
$('run').addEventListener('change',render);$('refresh').addEventListener('click',load);
$('print').addEventListener('click',()=>{const details=[...document.querySelectorAll('details')],previous=details.map(d=>d.open);details.forEach(d=>d.open=true);window.print();details.forEach((d,i)=>d.open=previous[i]);});
$('downloadJson').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(auditData,null,2)],{type:'application/json'}));const a=node('a');a.href=url;a.download='tradeoff-events-and-decisions.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
load();
