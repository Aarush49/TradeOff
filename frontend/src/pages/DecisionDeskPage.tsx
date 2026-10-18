import React, { useState, useEffect } from 'react';
import {
  FileText,
  Radio,
  Play,
  Pause,
  ChevronRight,
  ChevronDown,
  Check,
  CheckCircle2,
  ArrowUpRight,
  SkipForward,
  ShieldCheck,
  Layers,
  Activity,
  Truck,
} from 'lucide-react';
import type { LiveState, MetricsState } from '../types';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Icon } from '../components/common/Icon';
import { Panel } from '../components/common/Panel';
import { Empty } from '../components/common/Empty';
import { Table, decisionCols, shipmentCols } from '../components/common/Table';
import { RiskChart } from '../components/charts/RiskChart';
import { NetworkMap } from '../components/charts/NetworkMap';
import { ReviewModal } from '../components/desk/ReviewModal';
import { money, pct } from '../utils/formatters';

interface DecisionDeskPageProps {
  state: LiveState;
  metrics: MetricsState | null;
  act: (path: string, payload: any) => Promise<boolean>;
  busy: boolean;
  onAudit: () => void;
}

export function DecisionDeskPage({
  state,
  metrics,
  act,
  busy,
  onAudit,
}: DecisionDeskPageProps) {
  const [scenario, setScenario] = useState('congestion');
  const [review, setReview] = useState(false);
  const [note, setNote] = useState('');

  const proposal = state.proposals?.[0];
  const analysis = proposal?.data.analysis;
  const recommended = analysis?.recommended;
  const replay = state.replay;
  const outcome = metrics?.outcome;

  const canDecide =
    proposal?.status === 'pending' &&
    proposal.revision === state.revision &&
    !state.network?.outcome;

  useEffect(() => {
    setReview(false);
    setNote('');
  }, [proposal?.proposal_id, state.run_id]);

  const context = { run_id: state.run_id, revision: state.revision };

  const step = replay.complete
    ? 3
    : replay.awaiting_outcome || proposal
    ? 2
    : replay.running
    ? 1
    : 0;

  const headline = replay.complete
    ? 'The result is in.'
    : proposal?.status === 'approved'
    ? 'Recovery plan approved.'
    : replay.awaiting_outcome
    ? 'Your next move matters.'
    : replay.running
    ? 'Following your shipment.'
    : proposal
    ? 'A recommendation is ready.'
    : 'Ready for the next disruption.';

  const focusCopy = replay.complete
    ? 'Review the outcome below. Your decision trail is ready in the audit.'
    : proposal?.status === 'approved'
    ? replay.scenario
      ? 'Your allocation is published. Reveal the outcome to see how it performed.'
      : 'Your allocation is published. Submit another update to reassess the network.'
    : proposal?.status === 'rejected'
    ? replay.scenario
      ? 'The previous plan stays active. Reveal the outcome when you’re ready.'
      : 'The previous plan stays active. Submit a new signal to reassess.'
    : replay.awaiting_outcome
    ? 'Updates are paused. Review the latest recommendation before revealing the result.'
    : replay.running
    ? 'The model is reassessing delivery risk as new checkpoints arrive.'
    : proposal
    ? 'Review the recommendation based on the latest update. Approval publishes the new allocation.'
    : 'Choose a scenario above. We’ll monitor delivery risk and help you find a recovery plan.';

  // Fast-forward / reveal outcome reliably
  async function handleRevealOutcome() {
    if (busy) return;
    const runId = state.run_id;
    let idx = Number(state.replay.index || 0);

    // If scenario hasn't started yet, start it first
    if (!state.replay.scenario) {
      await act('replay', {
        ...context,
        action: 'start',
        scenario,
        interval_seconds: 5,
      });
      return;
    }

    // Step through remaining checkpoints to reveal outcome
    for (let i = 0; i < 5; i++) {
      const ok = await act('replay', {
        action: 'step',
        run_id: runId,
        index: idx,
      });
      if (!ok) break;
      idx++;
      if (idx > 4) break;
    }
  }

  const progressPercent = replay.complete
    ? 100
    : replay.scenario
    ? Math.min(replay.index || 0, 4) * 25
    : 0;

  return (
    <>
      <div className="page-heading pop-in">
        <div>
          <div className="eyebrow">OPERATIONS / DECISION DESK</div>
          <h1>
            Critical supply decision desk
            <span className="heading-dot" />
          </h1>
          <p className="muted">
            A clear path from a shipment signal to a coordinated response.
          </p>
        </div>
        <Button className="secondary" icon={FileText} onClick={onAudit}>
          Decision audit
        </Button>
      </div>

      <div className="scenario-bar pop-in">
        <div className="scenario-intro">
          <span className="round-icon">
            <Icon icon={Radio} />
          </span>
          <div>
            <strong>Shipment replay</strong>
            <small>Simulated events · every 5 seconds</small>
          </div>
        </div>

        <select
          aria-label="Replay scenario"
          value={scenario}
          onChange={e => setScenario(e.target.value)}
          disabled={busy}
        >
          <option value="congestion">Gradual congestion</option>
          <option value="outage">Route outage</option>
          <option value="normal">Normal delivery</option>
        </select>

        <Button
          icon={Play}
          disabled={busy}
          onClick={() =>
            act('replay', {
              ...context,
              action: 'start',
              scenario,
              interval_seconds: 5,
            })
          }
        >
          Start scenario
        </Button>

        {replay.scenario && !replay.complete && (
          <Button
            className="ghost"
            icon={replay.running ? Pause : Play}
            disabled={busy || replay.awaiting_outcome}
            onClick={() =>
              act('replay', {
                action: replay.running ? 'pause' : 'resume',
                run_id: state.run_id,
              })
            }
          >
            {replay.running ? 'Pause' : 'Resume'}
          </Button>
        )}
      </div>

      <div className="workflow-strip pop-in">
        {['Follow shipment', 'Review & decide', 'See outcome'].map((s, i) => (
          <div
            key={s}
            className={step > i ? 'done' : step === i + 1 ? 'active' : ''}
          >
            <span>{step > i ? <Check size={13} /> : `0${i + 1}`}</span>
            {s}
            {i < 2 && <ChevronRight size={14} />}
          </div>
        ))}
      </div>

      <div className="overview-grid">
        <Panel
          title={headline}
          eyebrow="NEXT ACTION"
          className="focus-panel pop-in"
          action={
            <Badge tone={replay.complete ? 'green' : 'amber'}>
              {replay.complete
                ? 'Complete'
                : proposal?.status === 'approved'
                ? 'Approved'
                : replay.awaiting_outcome
                ? 'Decision needed'
                : replay.running
                ? 'Observing'
                : proposal
                ? 'Recommendation ready'
                : 'Ready'}
            </Badge>
          }
        >
          <p className="focus-copy">{focusCopy}</p>

          <div className="next-actions pop-in">
            {canDecide && (
              <Button
                icon={ArrowUpRight}
                onClick={() => setReview(true)}
                disabled={busy}
              >
                Review recommendation
              </Button>
            )}
            <Button
              className="secondary"
              icon={SkipForward}
              disabled={busy || replay.complete}
              onClick={handleRevealOutcome}
            >
              Reveal simulated outcome
            </Button>
          </div>

          <div className="progress-row">
            <span>
              {replay.complete
                ? 'Delivery outcome recorded'
                : replay.scenario
                ? `${Math.min(replay.index || 0, 4)} of 4 checkpoints received`
                : `Manual mode · observed revision ${state.revision}`}
            </span>
            <span>Run {state.run_id.slice(0, 8)}</span>
          </div>

          <div className="progress-track">
            <i
              style={{
                width: `${progressPercent}%`,
              }}
            />
          </div>
        </Panel>

        <Panel
          title="Delivery risk"
          eyebrow="AI SIGNAL"
          className="pop-in"
          action={<Badge>Factory A</Badge>}
        >
          <RiskChart state={state} />
        </Panel>
      </div>

      <div className="stats-grid pop-in">
        <div className="stat">
          <span>
            <ShieldCheck size={17} /> Published allocation
          </span>
          <strong>Revision {state.approved_revision}</strong>
          <small>{state.approved_by}</small>
        </div>

        <div className="stat">
          <span>
            <Layers size={17} /> Recommended backup
          </span>
          <strong>
            {recommended ? recommended.reserve_quantity.toLocaleString() : '—'}
            <em> chips</em>
          </strong>
          <small>{proposal ? proposal.status : 'Awaiting recommendation'}</small>
        </div>

        <div className="stat">
          <span>
            <Activity size={17} /> Expected recovery cost
          </span>
          <strong>
            {recommended ? money(recommended.expected_cost) : '—'}
          </strong>
          <small>Modeled procurement + shortages</small>
        </div>

        <div className="stat">
          <span>
            <Truck size={17} /> Chips assigned
          </span>
          <strong>
            {state.approved_plan.shipments
              .reduce((n, s) => n + s.quantity, 0)
              .toLocaleString()}
            <em> chips</em>
          </strong>
          <small>Current published plan</small>
        </div>
      </div>

      {outcome && (
        <Panel
          title="What actually happened"
          eyebrow="SIMULATED OUTCOME"
          className="pop-in"
          action={
            <Badge tone={outcome.result.minimum_breaches ? 'amber' : 'green'}>
              {outcome.result.minimum_breaches} minimum breaches
            </Badge>
          }
        >
          <div className="outcome-banner">
            <CheckCircle2 size={26} />
            <div>
              <strong>
                Primary shipment arrived on day {outcome.actual_arrival_day}
              </strong>
              <p>
                Total cost {money(outcome.result.objective)} ·{' '}
                {outcome.result.unmet} chips unmet
              </p>
            </div>
          </div>
          <Table
            rows={outcome.result.decisions}
            cols={[
              ['factory', 'Factory'],
              ['allocated', 'On-time chips'],
              ['unmet', 'Unmet'],
              ['minimum', 'Hard minimum'],
            ]}
          />
          <p className="fine">{outcome.accounting}</p>
        </Panel>
      )}

      <div className="plan-grid pop-in">
        <Panel
          title="The shared plan"
          eyebrow="APPROVED & PUBLISHED"
          action={
            <Badge tone="green">
              <CheckCircle2 size={12} /> Revision {state.approved_revision}
            </Badge>
          }
        >
          <Table rows={state.approved_plan.decisions} cols={decisionCols} />
          <details>
            <summary>
              View shipment instructions <ChevronDown size={14} />
            </summary>
            <Table rows={state.approved_plan.shipments} cols={shipmentCols} />
          </details>
          <p className="fine">
            New signals do not change assignments until a coordinator approves a plan.
          </p>
        </Panel>

        <Panel title="Supply connections" eyebrow="NETWORK VIEW">
          <NetworkMap plan={state.approved_plan} />
        </Panel>
      </div>

      <details className="panel pop-in">
        <summary>
          Explore the model’s reasoning <ChevronDown size={16} />
        </summary>
        {analysis ? (
          <>
            <p className="muted">{analysis.policy.description}</p>

            {analysis.arrival_scenarios && analysis.arrival_scenarios.length > 0 && (
              <div style={{ margin: '22px 0 26px' }}>
                <h3 style={{ fontSize: 13, marginBottom: 12, color: '#2b4938' }}>
                  Current arrival scenarios
                </h3>
                {analysis.arrival_scenarios.map((s, idx) => (
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
                ))}
              </div>
            )}
            <Table
              rows={analysis.forecast.map(f => ({
                ...f,
                risk: pct(f.miss_probability),
              }))}
              cols={[
                ['factory', 'Factory'],
                ['deadline', 'Deadline day'],
                ['risk', 'Primary-shipment miss risk'],
              ]}
            />
            <Table
              rows={analysis.candidates.map(c => ({
                ...c,
                cost: money(c.expected_cost),
                risk: pct(c.minimum_breach_probability),
                eligible: c.eligible ? 'Meets policy' : 'Outside policy',
              }))}
              cols={[
                ['source', 'Candidate'],
                ['reserve_quantity', 'Backup chips'],
                ['cost', 'Expected cost'],
                ['risk', 'Minimum breach risk'],
                ['eligible', 'Assessment'],
              ]}
            />
            <p className="fine">{analysis.caveat}</p>
            <p className="fine">
              Server processing p95:{' '}
              {metrics?.event_to_proposal_ms.p95?.toFixed(2) ?? '—'} ms.{' '}
              {metrics?.measurement}
            </p>
          </>
        ) : (
          <Empty>A shipment update will generate the first forecast.</Empty>
        )}
      </details>

      {review && proposal && (
        <ReviewModal
          proposal={proposal}
          state={state}
          busy={busy}
          canDecide={canDecide}
          note={note}
          onNoteChange={setNote}
          onClose={() => setReview(false)}
          onDecide={async decision => {
            const ok = await act('decision', {
              proposal_id: proposal.proposal_id,
              revision: proposal.revision,
              decision,
              note,
            });
            if (ok) setReview(false);
          }}
        />
      )}
    </>
  );
}
