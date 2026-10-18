import React, { useState, useEffect, useRef } from 'react';
import { Network, Activity, FlaskConical } from 'lucide-react';
import type {
  LiveState,
  ModelInfo,
  LiveModelInfo,
  ContextData,
  BenchmarkReport,
  RiskPrediction,
} from '../types';
import { api } from '../api/client';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Panel } from '../components/common/Panel';
import { Empty } from '../components/common/Empty';
import { Table } from '../components/common/Table';
import { money, pct, date } from '../utils/formatters';

interface ModelExplorerPageProps {
  state: LiveState;
}

export function ModelExplorerPage({ state }: ModelExplorerPageProps) {
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [shipment, setShipment] = useState<LiveModelInfo | null>(null);
  const [context, setContext] = useState<ContextData | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkReport | null>(null);
  const [features, setFeatures] = useState<Record<string, string>>({});
  const [prediction, setPrediction] = useState<RiskPrediction | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [chip, setChip] = useState('');
  const [tab, setTab] = useState<'shipment' | 'historical' | 'context'>('shipment');

  const predictionVersion = useRef(0);

  useEffect(() => {
    let active = true;

    Promise.allSettled([
      api<ModelInfo>('/api/model'),
      api<LiveModelInfo>('/api/live/model'),
      api<ContextData>('/api/context'),
      api<BenchmarkReport>('/api/live/benchmark'),
    ]).then(results => {
      if (!active) return;
      const [m, s, c, b] = results;

      if (m.status === 'fulfilled') {
        setModel(m.value);
        const defaults: Record<string, string> = {
          'Shipping Mode': 'Standard Class',
          'Days for shipment (scheduled)': '4',
          'Order Region': 'Western Europe',
          Market: 'Europe',
          'Customer Segment': 'Consumer',
          'Order Country': 'Francia',
          Type: 'DEBIT',
        };
        setFeatures(
          Object.fromEntries(
            m.value.features.map(k => {
              const opts = m.value.choices?.[k] || [];
              return [
                k,
                opts.includes(defaults[k])
                  ? defaults[k]
                  : opts[0] || '',
              ];
            })
          )
        );
      }

      if (s.status === 'fulfilled') setShipment(s.value);

      if (c.status === 'fulfilled') {
        setContext(c.value);
        setChip(String(c.value.cset?.country_exposure?.[0]?.input_id || ''));
      }

      if (b.status === 'fulfilled') setBenchmark(b.value);

      const errs = results
        .filter((r): r is PromiseRejectedResult => r.status === 'rejected')
        .map(r => r.reason.message)
        .join(' ');
      if (errs) setError(errs);
    });

    return () => {
      active = false;
    };
  }, []);

  async function runOperation(fn: () => Promise<void>) {
    setError('');
    setBusy(true);
    try {
      await fn();
    } catch (e: any) {
      setError(e.message || 'Operation failed');
    } finally {
      setBusy(false);
    }
  }

  const exposure = context?.cset?.country_exposure?.find(
    c => String(c.input_id) === String(chip)
  );

  const latestProposal = state.proposals?.[0];
  const arrivalScenarios = latestProposal?.data?.analysis?.arrival_scenarios;

  return (
    <>
      <div className="page-heading pop-in">
        <div>
          <span className="eyebrow">INTELLIGENCE / MODEL EXPLORER</span>
          <h1>Understand the intelligence.</h1>
          <p className="muted">Explore each model in its own context.</p>
        </div>
        <Badge tone="green">Local inference</Badge>
      </div>

      <div className="model-tabs pop-in" role="tablist">
        {[
          ['shipment', 'Shipment AI'],
          ['historical', 'Historical delivery model'],
          ['context', 'Semiconductor context'],
        ].map(([id, name]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            className={tab === id ? 'active' : ''}
            onClick={() => setTab(id as any)}
          >
            {name}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}

      {tab === 'shipment' && (
        <>
          <div className="model-intro pop-in">
            <div className="model-symbol">
              <Network size={28} />
            </div>
            <div>
              <Badge tone="amber">SYNTHETIC TRAINING DATA</Badge>
              <h2>Shipment arrival forecasting</h2>
              <p className="muted">
                Estimates arrival scenarios from checkpoint signals. The optimizer turns those estimates into recovery options.
              </p>
            </div>
          </div>

          <div className="overview-grid">
            <Panel title="Current arrival scenarios" eyebrow="PREDICTION DISTRIBUTION" className="pop-in">
              {arrivalScenarios && arrivalScenarios.length > 0 ? (
                arrivalScenarios.map((s, idx) => (
                  <div className="bar-item" key={s.arrival_day}>
                    <div>
                      <span>Day {s.arrival_day}</span>
                      <strong>{pct(s.probability)}</strong>
                    </div>
                    <div className="bar-track">
                      <i
                        style={
                          {
                            '--target-width': pct(s.probability),
                            animationDelay: `${idx * 0.12}s`,
                          } as React.CSSProperties
                        }
                      />
                    </div>
                  </div>
                ))
              ) : (
                <Empty>Start a scenario on the decision desk to see predictions.</Empty>
              )}
              <p className="fine">{shipment?.model_id}</p>
            </Panel>

            <Panel title="What each part does" className="pop-in">
              <div className="explain-row pop-in" style={{ animationDelay: '0.1s' }}>
                <span>01</span>
                <div>
                  <strong>Naive Bayes forecasts arrival risk</strong>
                  <p>
                    Checkpoint age, progress, backlog, route status, and ETA inform possible arrival dates.
                  </p>
                </div>
              </div>
              <div className="explain-row pop-in" style={{ animationDelay: '0.2s' }}>
                <span>02</span>
                <div>
                  <strong>Integer min-cost flow allocates supply</strong>
                  <p>
                    Checks capacity, deadlines, hard minimums, and shortage costs. This is an exact optimizer.
                  </p>
                </div>
              </div>
              <div className="explain-row pop-in" style={{ animationDelay: '0.3s' }}>
                <span>03</span>
                <div>
                  <strong>You approve the response</strong>
                  <p>Recommendations remain separate from the shared plan until approval.</p>
                </div>
              </div>
            </Panel>
          </div>

          <Panel
            title="Compare decision policies"
            eyebrow="INDEPENDENT SYNTHETIC EPISODES"
            className="pop-in"
            action={
              <Button
                icon={FlaskConical}
                disabled={busy}
                onClick={() =>
                  runOperation(async () => {
                    const res = await api<BenchmarkReport>('/api/live/benchmark', { episodes: 300 });
                    setBenchmark(res);
                  })
                }
              >
                {busy ? 'Running…' : 'Run comparison'}
              </Button>
            }
          >
            {benchmark && benchmark.policies && (
              <>
                <Table
                  rows={Object.entries(benchmark.policies).map(([k, r]) => ({
                    policy:
                      ({
                        eta_rule: 'Reported ETA rule',
                        facts_optimizer: 'Reported-facts optimizer',
                        always_reserve: 'Always reserve backup',
                        ai_scenarios: 'AI scenario planning',
                      } as Record<string, string>)[k] || k,
                    cost: money(r?.mean_cost),
                    unmet: r?.unmet ?? 0,
                    breaches: r?.minimum_breaches ?? 0,
                    reserve: r?.mean_reserve_quantity != null ? r.mean_reserve_quantity.toFixed(1) : '—',
                  }))}
                  cols={[
                    ['policy', 'Policy'],
                    ['cost', 'Mean cost'],
                    ['unmet', 'Total unmet'],
                    ['breaches', 'Minimum breaches'],
                    ['reserve', 'Mean backup chips'],
                  ]}
                />
                <p className="fine">
                  {benchmark.episodes} episodes · {benchmark.host?.system || 'System'}/
                  {benchmark.host?.architecture || 'Arch'} · {benchmark.generated_at ? date(benchmark.generated_at) : '—'}.{' '}
                  {benchmark.limitations?.join(' ') || ''}
                </p>
              </>
            )}
          </Panel>
        </>
      )}

      {tab === 'historical' && model && (
        <>
          <div className="notice pop-in">
            <strong>Historical retail benchmark</strong>
            <p>
              Trained on DataCo orders. Its late-delivery score does not predict a semiconductor shortage or a specific supplier’s delay.
            </p>
          </div>

          <div className="stats-grid pop-in">
            <div className="stat">
              <span>Test accuracy</span>
              <strong>{pct(model.evaluation?.test?.accuracy)}</strong>
            </div>
            <div className="stat">
              <span>ROC AUC</span>
              <strong>{model.evaluation?.test?.roc_auc != null ? model.evaluation.test.roc_auc.toFixed(3) : '—'}</strong>
            </div>
            <div className="stat">
              <span>Recall</span>
              <strong>{pct(model.evaluation?.test?.recall)}</strong>
            </div>
            <div className="stat">
              <span>Later test orders</span>
              <strong>{model.evaluation?.test?.n != null ? model.evaluation.test.n.toLocaleString() : '—'}</strong>
            </div>
          </div>

          <Panel title="Explore delivery risk" eyebrow="INTERACTIVE INFERENCE" className="pop-in">
            <form
              onSubmit={e => {
                e.preventDefault();
                const version = ++predictionVersion.current;
                runOperation(async () => {
                  const result = await api<RiskPrediction>('/api/risk', { features });
                  if (version === predictionVersion.current) setPrediction(result);
                });
              }}
            >
              <div className="field-grid">
                {(model.features || []).map(f => (
                  <label key={f}>
                    {f}
                    <select
                      value={features[f] || ''}
                      onChange={e => {
                        predictionVersion.current++;
                        setFeatures({ ...features, [f]: e.target.value });
                        setPrediction(null);
                      }}
                    >
                      {(model.choices?.[f] || []).map(v => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <Button disabled={busy} icon={Activity}>
                {busy ? 'Predicting…' : 'Estimate delivery risk'}
              </Button>
            </form>

            {prediction && (
              <div className="prediction-result pop-in">
                <span>Estimated late-delivery probability</span>
                <strong>{pct(prediction.late_delivery_probability)}</strong>
                <p className="muted">
                  {prediction.interpretation} {prediction.warning}
                </p>
                <Table
                  rows={(prediction.contributions || []).map(c => ({
                    ...c,
                    contribution: c.log_odds_contribution != null ? c.log_odds_contribution.toFixed(3) : '—',
                  }))}
                  cols={[
                    ['feature', 'Feature'],
                    ['value', 'Value'],
                    ['contribution', 'Log-odds contribution'],
                  ]}
                />
              </div>
            )}
          </Panel>
        </>
      )}

      {tab === 'context' && context && (
        <>
          <div className="notice pop-in">
            <strong>Context, not a joined prediction model</strong>
            <p>
              CSET and SMAT2022 describe supply geography and factory topology. They are separate datasets without a validated record-level join to shipment outcomes.
            </p>
          </div>

          <div className="overview-grid">
            <Panel title="Supply geography" eyebrow="CSET CHIP EXPLORER" className="pop-in">
              <label>
                Semiconductor input
                <select value={chip} onChange={e => setChip(e.target.value)}>
                  {(context.cset?.country_exposure || []).map(c => (
                    <option key={c.input_id} value={c.input_id}>
                      {c.input} · {c.year}
                    </option>
                  ))}
                </select>
              </label>

              {(exposure?.countries || []).map((c, i) => (
                <div className="bar-item" key={i}>
                  <div>
                    <span>{c.country}</span>
                    <strong>{c.reported_share_percent ?? '—'}%</strong>
                  </div>
                  <div className="bar-track">
                    <i
                      style={
                        {
                          '--target-width': `${Math.min(
                            100,
                            c.reported_share_percent || 0
                          )}%`,
                          animationDelay: `${i * 0.08}s`,
                        } as React.CSSProperties
                      }
                    />
                  </div>
                </div>
              ))}
              <p className="fine">{context.cset?.caveat}</p>
            </Panel>

            <Panel title="Factory topology" eyebrow="SMAT2022" className="pop-in">
              <Table
                rows={Object.entries(context.smat?.sheets || {}).map(([sheet, r]) => ({
                  sheet,
                  records: r?.records != null ? r.records.toLocaleString() : '—',
                }))}
                cols={[
                  ['sheet', 'Topology component'],
                  ['records', 'Records'],
                ]}
              />
              <p className="fine">{context.smat?.caveat}</p>
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
