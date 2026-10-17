// Local inference only. No external services or browser-side model dependencies.
const ai = id => document.getElementById(id);
let intelligenceVersion = 0;

async function getJSON(path, payload) {
  const response = await fetch(path, payload === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (response.status === 401) window.location.replace('/login');
  if (!response.ok) throw new Error(data.error || 'Request failed.');
  return data;
}

async function initializeIntelligence() {
  try {
    const model = await getJSON('/api/model');
    const report = model.evaluation;
    ai('modelSummary').textContent = `${model.algorithm}. Test: ${report.test.n.toLocaleString()} later orders · ROC AUC ${report.test.roc_auc.toFixed(3)} · accuracy ${(100*report.test.accuracy).toFixed(1)}% · recall ${(100*report.test.recall).toFixed(1)}% at threshold ${report.threshold.toFixed(2)}. Majority baseline accuracy: ${(100*report.constant_baseline.accuracy).toFixed(1)}%.`;
    if(report.selection) ai('modelSummary').textContent += ' Model and threshold selected on validation; historical test comparison is retrospective.';
    ai('modelEvaluation').textContent = JSON.stringify(report, null, 2);
    const defaults = {'Shipping Mode':'Standard Class', 'Days for shipment (scheduled)':'4',
      'Order Region':'Western Europe', 'Market':'Europe', 'Customer Segment':'Consumer',
      'Order Country':'Francia', 'Type':'DEBIT'};
    for (const feature of model.features) {
      const label = document.createElement('label');
      label.textContent = feature;
      const select = document.createElement('select');
      select.dataset.feature = feature;
      for (const value of model.choices[feature]) {
        const option = document.createElement('option');
        option.value = value; option.textContent = value;
        select.append(option);
      }
      if (model.choices[feature].includes(defaults[feature])) select.value = defaults[feature];
      label.append(select); ai('riskInputs').append(label);
    }
    ai('predictRisk').disabled = false;
    ai('runStress').disabled = false;
  } catch (error) {
    ai('modelSummary').textContent = error.message;
  }
  try {
    const context = await getJSON('/api/context');
    ai('contextSummary').textContent = `CSET: ${context.cset.inputs} input categories, ${context.cset.provider_records} providers. SMAT2022 LVHM_E: ${context.smat.sheets.Equipment.records.toLocaleString()} equipment records, ${context.smat.sheets.Vehicle.records} vehicles, ${context.smat.sheets.Rail.records.toLocaleString()} rail segments. These are separate sources with no validated record-level join.`;
    const selector = ai('chipInput');
    for (const item of context.cset.country_exposure) {
      const option = document.createElement('option');
      option.value = item.input_id; option.textContent = `${item.input} (${item.year})`;
      selector.append(option);
    }
    const showExposure = () => {
      const item = context.cset.country_exposure.find(x => x.input_id === selector.value);
      if (!item) return;
      table('countryExposure', item.countries, [['country','Reported geography'], ['reported_share_percent','Reported share (%)'], ['source','Source']]);
      ai('shareNote').textContent = `Reported shares total ${item.reported_share_sum_percent.toFixed(1)}%. ${context.cset.caveat}`;
    };
    selector.addEventListener('change', showExposure); showExposure();
    table('factoryTopology', Object.entries(context.smat.sheets).map(([sheet, entry]) => ({sheet, records:entry.records})), [['sheet','SMAT sheet'], ['records','Records']]);
    ai('topologyNote').textContent = context.smat.caveat;
  } catch (error) {
    ai('contextSummary').textContent = error.message;
  }
}

function selectedFeatures() {
  return Object.fromEntries([...ai('riskInputs').querySelectorAll('select')].map(s => [s.dataset.feature,s.value]));
}

function showPrediction(prediction) {
  ai('riskOutput').hidden = false;
  ai('riskProbability').textContent = `${(prediction.late_delivery_probability*100).toFixed(1)}% estimated probability of DataCo's late-delivery label`;
  ai('riskScope').textContent = prediction.scope + ' ' + prediction.interpretation + (prediction.warning ? ' ' + prediction.warning : '');
  table('riskContributions', prediction.contributions.map(c => ({...c, log_odds_contribution:c.log_odds_contribution.toFixed(3)})),
    [['feature','Feature'], ['value','Value'], ['log_odds_contribution','Log-odds contribution']]);
}

async function runIntelligence(stress) {
  const version = ++intelligenceVersion;
  ai('intelligenceError').textContent = '';
  ai('riskOutput').hidden = true; ai('stressOutput').hidden = true;
  ai('aiStatus').textContent = 'Running local model…';
  try {
    const payload = {features:selectedFeatures()};
    let data;
    if (stress) {
      if (!result) throw new Error('Wait for a feasible recovery plan before running a delay scenario.');
      payload.requests = result.audit.shared_requests;
      payload.offers = result.audit.shared_offers;
      payload.supplier = ai('stressSupplier').value;
      payload.delay_days = Number(ai('stressDays').value);
      data = await getJSON('/api/analyze', payload);
    } else data = await getJSON('/api/risk', payload);
    if (version !== intelligenceVersion) return;
    showPrediction(stress ? data.prediction : data);
    if (stress) {
      ai('stressOutput').hidden = false;
      ai('stressResult').textContent = data.stress.feasible
        ? `If ${payload.supplier} arrives ${payload.delay_days} days later: network cost ${money(data.stress.plan.objective)} (${money(data.cost_increase_if_scenario_occurs)} increase); unmet demand ${data.stress.plan.decisions.reduce((n,d)=>n+d.unmet,0)}.`
        : `This delay scenario is infeasible: ${data.stress.error}`;
      ai('stressExplanation').textContent = data.explanation;
    }
    ai('aiStatus').textContent = 'Analysis complete. Recovery plan inputs were not changed.';
  } catch (error) {
    if (version !== intelligenceVersion) return;
    ai('intelligenceError').textContent = error.message;
    ai('aiStatus').textContent = '';
  }
}

ai('predictRisk').addEventListener('click', () => runIntelligence(false));
ai('runStress').addEventListener('click', () => runIntelligence(true));
// Any changed input invalidates the old analysis before a response can arrive.
document.addEventListener('input', () => {
  ++intelligenceVersion;
  ai('riskOutput').hidden = true; ai('stressOutput').hidden = true;
  ai('aiStatus').textContent = ''; ai('intelligenceError').textContent = '';
});
document.addEventListener('change', event => {
  if (event.target.id === 'view') {
    ai('intelligencePanel').hidden = event.target.value !== 'Coordinator';
  }
});
sessionReady.then(session => {if(session.role === 'coordinator') initializeIntelligence();}).catch(() => {});
