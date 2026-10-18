import React, { useState, useEffect } from 'react';
import {
  RefreshCw,
  Printer,
  Check,
  Activity,
  ChevronDown,
} from 'lucide-react';
import type { AuditData } from '../types';
import { api } from '../api/client';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Panel } from '../components/common/Panel';
import { Empty } from '../components/common/Empty';
import { Table, decisionCols, shipmentCols } from '../components/common/Table';
import { money, date } from '../utils/formatters';

const actionLabels: Record<string, string> = {
  approved: 'Recovery allocation approved',
  rejected: 'Proposal rejected',
  new_simulation_run: 'Scenario started',
  event_accepted: 'Shipment event received',
};

export function AuditPage() {
  const [data, setData] = useState<AuditData | null>(null);
  const [run, setRun] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function loadAudit() {
    setBusy(true);
    try {
      const d = await api<AuditData>('/api/live/audit');
      setData(d);
      setRun(v => v || d.current_run.run_id);
      setError('');
    } catch (e: any) {
      setError(e.message || 'Failed to load audit data');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadAudit();
  }, []);

  const actions =
    data?.actions
      .filter(a => a.run_id === run)
      .sort((a, b) => a.seq - b.seq) || [];

  const current = data?.current_run;

  const proposals =
    data?.proposals.filter(p => p.run_id === run) || [];

  function handlePrint() {
    const details = Array.from(document.querySelectorAll('details'));
    const wasOpen = details.map(d => d.open);
    details.forEach(d => (d.open = true));
    window.print();
    details.forEach((d, i) => (d.open = wasOpen[i]));
  }

  return (
    <>
      <div className="page-heading pop-in">
        <div>
          <span className="eyebrow">ACCOUNTABILITY / AUDIT</span>
          <h1>A decision trail you can follow.</h1>
          <p className="muted">
            Every signal, recommendation, and approval in one place.
          </p>
        </div>

        <div className="button-row">
          <Button
            className="secondary"
            icon={RefreshCw}
            disabled={busy}
            onClick={loadAudit}
          >
            Refresh
          </Button>
          <Button
            icon={Printer}
            onClick={handlePrint}
            disabled={!data}
          >
            Print / PDF
          </Button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {data && current ? (
        <>
          <div className="audit-tools pop-in">
            <label>
              Inspect run
              <select value={run} onChange={e => setRun(e.target.value)}>
                {[
                  ...new Set([
                    current.run_id,
                    ...data.actions.map(a => a.run_id),
                    ...data.proposals.map(p => p.run_id),
                    ...data.events.map(e => e.run_id),
                  ]),
                ].map(id => (
                  <option key={id} value={id}>
                    {id === current.run_id ? 'Current' : 'Archived'} · {id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </label>

            <span className="fine">
              Snapshot {date(data.generated_at)} · up to {data.limit_per_collection}{' '}
              records per collection
            </span>
          </div>

          {run === current.run_id && (
            <Panel
              title={
                current.network.outcome ? 'The outcome' : 'The published plan'
              }
              className="pop-in"
              action={
                <Badge tone="green">
                  Revision {current.approved_revision}
                </Badge>
              }
            >
              <div className="audit-outcome">
                <strong>
                  {money(
                    (
                      current.network.outcome?.result || current.approved_plan
                    ).objective
                  )}
                </strong>
                <span>Total simulated cost</span>
                <p>
                  {current.network.outcome
                    ? `${current.network.outcome.result.unmet} chips unmet · ${current.network.outcome.result.minimum_breaches} hard minimum breaches · Primary arrival day ${current.network.outcome.actual_arrival_day}`
                    : 'Outcome not revealed yet.'}
                </p>
              </div>

              <p className="fine">
                Procurement{' '}
                {money(
                  (
                    current.network.outcome?.result || current.approved_plan
                  ).procurement
                )}{' '}
                · Shortage penalties{' '}
                {money(
                  (
                    current.network.outcome?.result || current.approved_plan
                  ).shortage_penalty
                )}
              </p>

              <Table
                rows={
                  current.network.outcome?.result.decisions ||
                  current.approved_plan.decisions
                }
                cols={
                  current.network.outcome
                    ? [
                        ['factory', 'Factory'],
                        ['allocated', 'On-time chips'],
                        ['unmet', 'Unmet'],
                        ['minimum', 'Hard minimum'],
                      ]
                    : decisionCols
                }
              />
            </Panel>
          )}

          {run !== current.run_id && (
            <p className="notice pop-in">
              Archived records below; a full outcome summary is included only for
              the current run.
            </p>
          )}

          <div className="audit-grid">
            <Panel title="Decision timeline" eyebrow="OLDEST FIRST" className="pop-in">
              <ol className="timeline">
                {actions.map((a, index) => (
                  <li
                    key={a.seq}
                    style={{ animationDelay: `${index * 0.08}s` }}
                  >
                    <span
                      className={`timeline-dot ${
                        a.action === 'approved' ? 'green' : ''
                      }`}
                    >
                      {a.action === 'approved' ? (
                        <Check size={12} />
                      ) : (
                        <Activity size={12} />
                      )}
                    </span>
                    <div>
                      <strong>
                        {actionLabels[a.action] ||
                          a.action.replaceAll('_', ' ')}
                      </strong>
                      <small>
                        {date(a.created_at)} · {a.actor}
                      </small>
                      <p>
                        {[
                          a.details.revision != null
                            ? `Revision ${a.details.revision}`
                            : null,
                          a.details.entity,
                          a.details.scenario,
                          a.details.note,
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
              {!actions.length && <Empty>No retained actions.</Empty>}
            </Panel>

            <Panel
              title="Recommendations"
              eyebrow="MODEL → HUMAN DECISION"
              className="pop-in"
            >
              {proposals.map(p => (
                <details key={p.proposal_id} className="proposal-record">
                  <summary>
                    <span>Revision {p.revision}</span>
                    <Badge tone={p.status === 'approved' ? 'green' : ''}>
                      {p.status}
                    </Badge>
                  </summary>
                  <p>{p.data.analysis.action}</p>
                  {p.data.analysis.recommended && (
                    <>
                      <p className="muted">
                        {
                          p.data.analysis.recommended.reserve_quantity
                        }{' '}
                        backup chips ·{' '}
                        {money(
                          p.data.analysis.recommended.expected_cost
                        )}{' '}
                        expected cost
                      </p>
                      <Table
                        rows={
                          p.data.analysis.recommended.plan.shipments
                        }
                        cols={shipmentCols}
                      />
                    </>
                  )}
                  <p className="fine">{p.data.analysis.model_id}</p>
                </details>
              ))}
              {!proposals.length && <Empty>No retained proposals.</Empty>}
            </Panel>
          </div>

          <details className="panel pop-in">
            <summary>
              Event details <ChevronDown size={16} />
            </summary>
            <Table
              rows={data.events
                .filter(e => e.run_id === run)
                .sort((a, b) => a.seq - b.seq)
                .map(e => ({
                  ...e,
                  type: e.payload.type.replaceAll('_', ' '),
                  entity: e.payload.entity,
                  changes: Object.entries(e.payload.changes || {})
                    .map(([k, v]) => `${k.replaceAll('_', ' ')}: ${v}`)
                    .join(' · '),
                }))}
              cols={[
                ['revision', 'Revision'],
                ['type', 'Type'],
                ['entity', 'Entity'],
                ['status', 'Status'],
                ['changes', 'Reported changes'],
              ]}
            />
          </details>

          <p className="fine">
            Simulated network. Record limits apply across all runs; the server
            retains archived runs.
          </p>
        </>
      ) : (
        <Empty>Loading your audit…</Empty>
      )}
    </>
  );
}
