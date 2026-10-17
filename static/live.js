// Shared event-driven demo. All text from the API is inserted with textContent.
const live = id => document.getElementById(id);
let liveState = null, liveSession = null, refreshSequence = 0, proposalForReview = null;
let liveBusy = false, formInitialized = false, reviewedProposalId = null, eventFormDirty = false;

async function liveAPI(path, payload) {
  const response = await fetch('/api/live/' + path, payload === undefined ? {} : {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
  });
  const data = await response.json();
  if (response.status === 401) window.location.replace('/login');
  if (!response.ok) throw new Error(data.error || 'Shared-state request failed.');
  return data;
}

function percentage(value) { return (value*100).toFixed(1)+'%'; }
function fixed(value) { return value == null ? '—' : value.toFixed(2)+' ms'; }

async function refreshLive() {
  const sequence = ++refreshSequence;
  try {
    const state = await liveAPI('state');
    if (sequence !== refreshSequence) return;
    if(liveState && liveState.run_id!==state.run_id) {eventFormDirty=false;live('eventClock').value=state.simulation_hour;}
    liveState = state;
    live('liveConnection').textContent = 'Connected · updates every 2 seconds';
    live('liveVersion').textContent = `Run ${state.run_id.slice(0,8)} · observed revision ${state.revision} · simulation hour ${state.simulation_hour} · ${state.signal_stale?'checkpoint stale':'checkpoint current'}`;
    const plan = state.approved_plan;
    live('planRevision').textContent = 'Revision '+state.approved_revision;
    live('approvedStatus').textContent = `Revision ${state.approved_revision} · Published by ${state.approved_by}. ${state.approved_revision < state.revision ? 'New signals have not changed this plan.' : ''}`;
    table('approvedDecisions',plan.decisions,[['factory','Factory'],['requested','Requested'],['allocated','Allocated'],['unmet','Planned unmet']]);
    table('approvedShipments',plan.shipments,[['factory','Factory'],['supplier','Supply pool'],['quantity','Quantity'],['arrival','Assumed arrival day'],['unit_cost','Unit cost ($)']]);
    if (!formInitialized) { initializeEventForm(); formInitialized = true; }
    else if(!eventFormDirty && !live('eventFields').contains(document.activeElement)) populateEventFields();
    for(const node of live('liveEventForm').querySelectorAll('input,select,button')) node.disabled=Boolean(state.replay.complete);
    if (document.activeElement !== live('eventClock') && Number(live('eventClock').value)<state.simulation_hour) live('eventClock').value = state.simulation_hour;
    if (liveSession.role === 'coordinator') {
      renderProposal(state);
      table('eventLedger',state.events.map(e=>({id:e.event_id.slice(-18),type:e.payload.type,entity:e.payload.entity,status:e.status,revision:e.revision,ms:fixed(e.latency_ms)})),[['id','Event'],['type','Type'],['entity','Entity'],['status','Status'],['revision','Revision'],['ms','Processing']]);
      const metrics = await liveAPI('metrics');
      if (sequence !== refreshSequence) return;
      live('liveLatency').textContent = fixed(metrics.event_to_proposal_ms.p95);
      live('liveMetrics').textContent = JSON.stringify(metrics,null,2);
      live('liveMetricsNote').textContent = metrics.measurement;
      live('liveOutcome').hidden = !metrics.outcome;
      if (metrics.outcome) {
        const realized = metrics.outcome.result;
        live('liveOutcome').textContent = `Outcome · Primary shipment arrived on day ${metrics.outcome.actual_arrival_day}. Total cost ${money(realized.objective)} · ${realized.unmet} chips unmet · ${realized.minimum_breaches} hard minimum breaches.`;
      }
    }
  } catch (error) {
    if (sequence !== refreshSequence) return;
    live('liveConnection').textContent = 'Connection problem · retrying';
    live('liveError').textContent = error.message;
  }
}

function renderProposal(state) {
  const replay=state.replay;
  live('replayStatus').textContent = replay.error || (replay.awaiting_outcome ? 'Replay paused before the delivery outcome. Review the proposal, approve or reject, then reveal the outcome.' : replay.complete ? 'Replay complete. Start another run to compare a different response.' : replay.running ? `Replaying ${replay.scenario}: ${replay.index}/4 checkpoints received.` : replay.scenario ? 'Replay paused.' : 'Manual event mode.');
  live('pauseReplay').textContent = replay.running ? 'Pause' : 'Resume';
  live('pauseReplay').disabled = !replay.scenario || replay.awaiting_outcome || replay.complete || liveBusy;
  live('stepReplay').textContent = replay.awaiting_outcome ? 'Reveal simulated outcome' : 'Next event';
  live('stepReplay').disabled = !replay.scenario || replay.complete || liveBusy;
  const proposal=state.proposals[0];
  proposalForReview=proposal || null;
  if (reviewedProposalId && reviewedProposalId !== proposal?.proposal_id) {
    reviewedProposalId=null;
    live('decisionNote').value='';
  }
  const analysis=proposal?.data.analysis;
  live('proposalTitle').textContent = proposal ? `${analysis.action} · revision ${proposal.revision}` : 'No proposal yet';
  live('liveAction').textContent = proposal ? proposal.status : 'Awaiting event';
  const primaryForecast=analysis?.forecast.find(f=>f.factory==='Factory A');
  live('liveRisk').textContent = state.network.outcome ? 'Outcome known' : primaryForecast ? percentage(primaryForecast.miss_probability) : '—';
  const recommended=analysis?.recommended;
  live('proposalSummary').textContent = analysis ? (recommended ? `Reserve ${recommended.reserve_quantity} backup chips. Expected total cost: ${money(recommended.expected_cost)}. Modeled risk of breaching a hard minimum: ${percentage(recommended.minimum_breach_probability)}.` : 'No recovery plan meets the current requirements. Review the inputs before continuing.') : 'Start a scenario to receive a recommendation.';
  live('nextStep').textContent = replay.complete ? 'Complete · Review the outcome below or open the decision audit.' : replay.running ? 'Receiving shipment updates · Recommendations will change as new signals arrive.' : state.network.outcome ? 'Outcome available · Review the result below.' : proposal?.status==='approved' ? 'Plan approved · Reveal the simulated outcome to see the result.' : proposal?.status==='rejected' ? 'Proposal rejected · The previous plan remains active. Reveal the outcome when ready.' : replay.awaiting_outcome ? (reviewedProposalId===proposal?.proposal_id ? 'Ready to decide · Approve this allocation or reject it to keep the current plan.' : 'Decision needed · Review the recommendation, then approve or reject it.') : proposal ? 'Recommendation available · Review it, or continue receiving updates.' : 'Start here · Choose a scenario and select Start scenario.';

  const canDecide=proposal && proposal.status==='pending' && proposal.revision===state.revision && !state.network.outcome;
  live('reviewProposal').disabled = !canDecide || liveBusy;
  const reviewed = proposal && reviewedProposalId===proposal.proposal_id;
  live('reviewNotice').textContent = reviewed ? `You are reviewing revision ${proposal.revision}. A newer event will require a new review.` : 'Review the allocation before approving it.';
  live('reviewPreview').hidden = !reviewed;
  if (reviewed && recommended) {
    table('proposedDecisions',recommended.plan.decisions,[['factory','Factory'],['requested','Requested'],['allocated','Allocated'],['unmet','Planned unmet']]);
    table('proposedShipments',recommended.plan.shipments,[['factory','Factory'],['supplier','Supply pool'],['quantity','Quantity'],['arrival','Assumed arrival day']]);
  }
  live('approveLive').disabled = !canDecide || !reviewed || state.signal_stale || liveBusy;
  live('rejectLive').disabled = !canDecide || liveBusy;
  if (analysis) {
    table('liveForecast',analysis.forecast.map(f=>({...f,probability:percentage(f.miss_probability)})),[['factory','Factory'],['deadline','Deadline day'],['probability','Modeled primary-shipment miss risk']]);
    table('arrivalScenarios',analysis.arrival_scenarios.map(s=>({...s,chance:percentage(s.probability)})),[['arrival_day','Primary arrival day'],['additional_delay_days','Additional days'],['chance','Probability']]);
    table('candidatePlans',analysis.candidates.map(c=>({source:c.source,cost:money(c.expected_cost),risk:percentage(c.minimum_breach_probability),reserve:c.reserve_quantity,eligible:c.eligible?'Yes':'No'})),[['source','Candidate'],['cost','Expected cost'],['risk','Minimum breach risk'],['reserve','Reserve qty'],['eligible','Meets policy']]);
    live('riskPolicy').textContent = analysis.policy.description + ' Expected costs reflect simulation assumptions, not guaranteed savings.';
  } else {
    for (const id of ['liveForecast','arrivalScenarios','candidatePlans']) live(id).replaceChildren();
    live('riskPolicy').textContent='';
  }
}

async function liveAction(callback, message) {
  if (liveBusy) return;
  liveBusy=true;
  live('liveError').textContent='';
  live('liveActionStatus').textContent='Processing…';
  if(liveState && liveSession.role==='coordinator') renderProposal(liveState);
  try {
    await callback();
    live('liveActionStatus').textContent=message;
    await refreshLive();
  } catch(error) {
    live('liveError').textContent=error.message;
    live('liveActionStatus').textContent='';
    await refreshLive();
  } finally {
    liveBusy=false;
    if(liveState && liveSession.role==='coordinator') renderProposal(liveState);
  }
}

function initializeEventForm() {
  const types = liveSession.role==='factory' ? [['demand_update','Factory demand update']] : liveSession.role==='supplier' && liveSession.participant==='Supplier T' ? [['inventory_update','Supply-pool update']] : [['shipment_update','Primary shipment checkpoint'],['inventory_update','Supply-pool update']];
  if(liveSession.role==='coordinator') types.push(['demand_update','Factory demand update']);
  for(const [value,text] of types) { const option=document.createElement('option'); option.value=value; option.textContent=text; live('liveEventType').append(option); }
  live('liveEventType').addEventListener('change',populateEntities);
  live('liveEventEntity').addEventListener('change',populateEventFields);
  populateEntities();
}

function populateEntities() {
  const kind=live('liveEventType').value;
  let entities=kind==='shipment_update'?['Supplier S']:kind==='demand_update'?['Factory A','Factory B']:['Supplier S','Supplier T','Supplier T reserve'];
  if(liveSession.role!=='coordinator') entities=entities.filter(name=>(name==='Supplier T reserve'?'Supplier T':name)===liveSession.participant);
  live('liveEventEntity').replaceChildren();
  for(const name of entities) { const option=document.createElement('option'); option.value=name; option.textContent=name; live('liveEventEntity').append(option); }
  populateEventFields();
}

function populateEventFields() {
  eventFormDirty=false;
  const kind=live('liveEventType').value,entity=live('liveEventEntity').value;
  let data;
  if(kind==='shipment_update') data=liveState.network?.primary_signal || liveState.signal;
  else if(kind==='inventory_update') data=(liveState.network?.offers || liveState.stock_pools || []).find(o=>o.name===entity);
  else data=liveState.network?.requests.find(r=>r.name===entity) || liveState.request || {quantity:600,deadline:2,minimum:400,penalty:100};
  const fields=kind==='shipment_update' ? [['reported_eta_day','Reported arrival day',0,1000],['checkpoint_age_hours','Hours since checkpoint',0,24000],['backlog_ratio','Backlog ratio (0–2)',0,2],['progress','Progress fraction (0–1)',0,1],['route_status','Route status']] : kind==='inventory_update' ? [['capacity','Available chips',0,5000],['arrival','Confirmed arrival day',0,10000],['unit_cost','Unit cost',0,10000]] : [['quantity','Requested chips',0,5000],['deadline','Deadline day',0,10000],['minimum','Hard minimum',0,5000],['penalty','Penalty per missing chip',0,10000]];
  live('eventFields').replaceChildren();
  for(const [key,title,min,max] of fields) {
    const label=document.createElement('label');label.textContent=title;
    const input=document.createElement(key==='route_status'?'select':'input');input.dataset.change=key;
    if(key==='route_status') for(const value of ['normal','congestion','outage']) { const option=document.createElement('option');option.value=value;option.textContent=value;input.append(option); }
    else {input.type='number';input.min=min;input.max=max;input.step=['capacity','arrival','quantity','deadline','minimum'].includes(key)?'1':'any';input.required=true;}
    input.value=data?.[key] ?? 0;label.append(input);live('eventFields').append(label);
  }
}

live('eventFields').addEventListener('input',()=>eventFormDirty=true);
live('eventFields').addEventListener('change',()=>eventFormDirty=true);
live('liveEventForm').addEventListener('submit',event=>{
  event.preventDefault();
  if(!liveState)return;
  const changes=Object.fromEntries([...live('eventFields').querySelectorAll('[data-change]')].map(node=>[node.dataset.change,node.tagName==='SELECT'?node.value:Number(node.value)]));
  const payload={event_id:crypto.randomUUID(),run_id:liveState.run_id,occurred_at:new Date().toISOString(),source:'manual_demo',simulation_hour:Number(live('eventClock').value),type:live('liveEventType').value,entity:live('liveEventEntity').value,changes};
  liveAction(async()=>{const result=await liveAPI('events',payload);if(result.status==='ignored_out_of_order')throw new Error('Out-of-order event recorded but not applied. Use the current simulation clock.');eventFormDirty=false;},'Event recorded; review the new proposal.');
});

live('startReplay').addEventListener('click',()=>liveAction(()=>liveAPI('replay',{action:'start',scenario:live('replayScenario').value,interval_seconds:5,run_id:liveState.run_id,revision:liveState.revision}),'New replay started. Previous run retained in the audit.'));
live('resetLive').addEventListener('click',()=>liveAction(()=>liveAPI('reset',{run_id:liveState.run_id,revision:liveState.revision}),'New blank run created. Previous run retained.'));
live('pauseReplay').addEventListener('click',()=>liveAction(()=>liveAPI('replay',{action:liveState.replay.running?'pause':'resume',run_id:liveState.run_id}),'Replay control updated.'));
live('stepReplay').addEventListener('click',()=>liveAction(()=>liveAPI('replay',{action:'step',run_id:liveState.run_id,index:liveState.replay.index}),'Replay event processed.'));
live('reviewProposal').addEventListener('click',()=>{if(proposalForReview){reviewedProposalId=proposalForReview.proposal_id;renderProposal(liveState);}});
for(const [id,decision] of [['approveLive','approve'],['rejectLive','reject']]) live(id).addEventListener('click',()=>{
  if(!proposalForReview || (decision==='approve' && reviewedProposalId!==proposalForReview.proposal_id))return;
  const payload={proposal_id:proposalForReview.proposal_id,revision:proposalForReview.revision,decision,note:live('decisionNote').value};
  liveAction(()=>liveAPI('decision',payload),decision==='approve'?'Approved plan published to participant workspaces.':'Proposal rejected; approved plan retained.');
});
live('exportLive').addEventListener('click',()=>window.open('/audit','_blank','noopener'));

function renderBenchmark(report) {
  live('benchmarkHost').textContent=`${report.episodes} independent synthetic episodes · ${report.host.system}/${report.host.architecture} · generated ${new Date(report.generated_at).toLocaleString()}. ${report.decision_time} ${report.network || ''}`;
  const names={eta_rule:'Reported ETA rule',facts_optimizer:'Reported-facts optimizer',always_reserve:'Always reserve backup',ai_scenarios:'AI scenario planning'};
  table('benchmarkResults',Object.entries(report.policies).map(([name,r])=>({policy:names[name]||name,cost:money(r.mean_cost),unmet:r.unmet,breaches:r.minimum_breaches,reserve:r.mean_reserve_quantity.toFixed(1)})),[['policy','Policy'],['cost','Mean simulated cost'],['unmet','Total unmet chips'],['breaches','Minimum breaches'],['reserve','Mean reserve qty']]);
  live('benchmarkLimit').textContent=`p95 inference + planning ${fixed(report.inference_and_planning_ms.p95)}. ${report.timing_scope} ${report.limitations.join(' ')}`;
}
live('benchmarkLive').addEventListener('click',()=>liveAction(async()=>renderBenchmark(await liveAPI('benchmark',{episodes:300})),'Simulation comparison completed on this server.'));

sessionReady.then(async session=>{
  liveSession=session;
  await refreshLive();
  if(session.role==='coordinator') {
    try {
      const model=await liveAPI('model');
      live('shipmentModelSummary').textContent=`${model.model_id} · ${model.algorithm}. ${model.evaluation.training_episodes} training episodes; ${model.evaluation.test.episodes} separate test episodes. Synthetic performance only.`;
      live('shipmentModelEvaluation').textContent=JSON.stringify(model.evaluation,null,2);
      renderBenchmark(await liveAPI('benchmark'));
    } catch(error) {live('liveError').textContent=error.message;}
  }
  setInterval(()=>{if(!liveBusy && !document.hidden)refreshLive();},2000);
}).catch(error=>{live('liveError').textContent=error.message;});
