import React from 'react';
import {
  Layers,
  CheckCircle2,
  Clock,
  ShieldCheck,
  AlertTriangle,
  Truck,
  DollarSign,
  TrendingUp,
  Radio,
} from 'lucide-react';
import type { LiveState, User } from '../types';
import { Badge } from '../components/common/Badge';
import { Panel } from '../components/common/Panel';
import { Table, decisionCols, shipmentCols } from '../components/common/Table';
import { money, pct } from '../utils/formatters';

interface ParticipantPageProps {
  state: LiveState;
  user: User;
}

export function ParticipantPage({ state, user }: ParticipantPageProps) {
  const isFactory = user.role === 'factory';
  const isSupplier = user.role === 'supplier';

  const decisions = state.approved_plan?.decisions || [];
  const shipments = state.approved_plan?.shipments || [];

  // Factory metrics
  const factoryDecision = decisions.find(d => d.factory === user.participant) || decisions[0];
  const requested = factoryDecision?.requested ?? state.request?.quantity ?? 0;
  const allocated = factoryDecision?.allocated ?? 0;
  const minimum = factoryDecision?.minimum ?? state.request?.minimum ?? 0;
  const unmet = factoryDecision?.unmet ?? Math.max(0, requested - allocated);
  const deadline = state.request?.deadline ?? (shipments[0]?.arrival ?? 2);
  const penalty = state.request?.penalty ?? 20;

  const fulfillmentPct = requested > 0 ? Math.min(100, Math.round((allocated / requested) * 100)) : 100;
  const minimumPct = requested > 0 ? Math.min(100, Math.round((minimum / requested) * 100)) : 67;
  const isQuotaMet = allocated >= minimum;

  // Supplier metrics
  const stockPools = state.stock_pools || [];
  const totalCapacity = stockPools.reduce((sum, p) => sum + (p.capacity || 0), 0);
  const totalCommitted = shipments.reduce((sum, s) => sum + (s.quantity || 0), 0);
  const totalSurplus = Math.max(0, totalCapacity - totalCommitted);
  const utilizationPct = totalCapacity > 0 ? Math.min(100, Math.round((totalCommitted / totalCapacity) * 100)) : 0;
  const totalRevenue = shipments.reduce((sum, s) => {
    const pool = stockPools.find(p => p.name === s.supplier);
    return sum + (s.quantity || 0) * (pool?.unit_cost || 0);
  }, 0);

  return (
    <>
      <div className="page-heading pop-in">
        <div>
          <span className="eyebrow">
            {isFactory
              ? 'FACTORY WORKSPACE · DEMAND & ALLOCATIONS'
              : isSupplier
              ? 'SUPPLIER WORKSPACE · INVENTORY & DISPATCH'
              : 'YOUR WORKSPACE / SHARED ALLOCATION'}
          </span>
          <h1>{user.participant}</h1>
          <p className="muted">
            {isFactory
              ? 'Monitors real-time chip allocations, incoming shipments, and assembly quota safety.'
              : isSupplier
              ? 'Active shipment commitments, inventory pools, and dispatch schedules.'
              : 'Your assignments from the coordinator-approved plan.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <Badge tone={isFactory ? (isQuotaMet ? 'green' : 'red') : 'green'}>
            {isFactory
              ? isQuotaMet
                ? 'Quota Satisfied'
                : 'Quota At Risk'
              : 'Active Network Supplier'}
          </Badge>
          <Badge tone="blue">Revision {state.approved_revision}</Badge>
        </div>
      </div>

      {isFactory && (
        <>
          <div className="stats-grid pop-in">
            <div className="stat pop-in" style={{ animationDelay: '0.05s' }}>
              <span>
                <Layers size={14} /> Requested Demand
              </span>
              <strong>{requested.toLocaleString()}</strong>
              <em>Total chip requirement</em>
            </div>

            <div className="stat pop-in" style={{ animationDelay: '0.1s' }}>
              <span>
                <CheckCircle2 size={14} /> Approved Allocation
              </span>
              <strong style={{ color: isQuotaMet ? 'var(--green, #1c7965)' : '#cf3c3c' }}>
                {allocated.toLocaleString()}
              </strong>
              <em>{fulfillmentPct}% fulfilled</em>
            </div>

            <div className="stat pop-in" style={{ animationDelay: '0.15s' }}>
              <span>
                <ShieldCheck size={14} /> Hard Minimum Quota
              </span>
              <strong>{minimum.toLocaleString()}</strong>
              <em>{isQuotaMet ? 'Production quota met' : `${minimum - allocated} chip shortfall`}</em>
            </div>

            <div className="stat pop-in" style={{ animationDelay: '0.2s' }}>
              <span>
                <Clock size={14} /> Delivery Deadline
              </span>
              <strong>Day {deadline}</strong>
              <em>Shortage penalty: ${penalty}/chip</em>
            </div>
          </div>

          <Panel
            title="Demand fulfillment & allocation tracking"
            eyebrow="REQUESTED VS ALLOCATED GRAPH"
            className="pop-in"
            style={{ animationDelay: '0.25s' }}
          >
            <div className="bar-item">
              <div>
                <span>Requested Target Demand</span>
                <strong>{requested.toLocaleString()} chips (100%)</strong>
              </div>
              <div className="bar-track">
                <i
                  style={
                    {
                      '--target-width': '100%',
                      animationDelay: '0.1s',
                    } as React.CSSProperties
                  }
                />
              </div>
            </div>

            <div className="bar-item">
              <div>
                <span>Approved Allocated Supply</span>
                <strong style={{ color: isQuotaMet ? 'var(--green, #1c7965)' : '#cf3c3c' }}>
                  {allocated.toLocaleString()} chips ({fulfillmentPct}% fulfilled)
                </strong>
              </div>
              <div className="bar-track">
                <i
                  style={
                    {
                      '--target-width': `${fulfillmentPct}%`,
                      animationDelay: '0.2s',
                    } as React.CSSProperties
                  }
                />
              </div>
            </div>

            <div className="bar-item">
              <div>
                <span>Hard Minimum Threshold (Must arrive by Day {deadline})</span>
                <strong>
                  {minimum.toLocaleString()} chips ({minimumPct}% of requested)
                </strong>
              </div>
              <div className="bar-track">
                <i
                  style={
                    {
                      '--target-width': `${minimumPct}%`,
                      animationDelay: '0.3s',
                      background: 'linear-gradient(90deg, #78909c 0%, #455a64 100%)',
                    } as React.CSSProperties
                  }
                />
              </div>
            </div>

            {shipments.length > 0 && (
              <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--line, #e4ebe7)' }}>
                <span className="eyebrow">INBOUND SHIPMENTS BY SUPPLY POOL</span>
                {shipments.map((s, idx) => {
                  const share = requested > 0 ? Math.min(100, Math.round((s.quantity / requested) * 100)) : 100;
                  return (
                    <div className="bar-item" key={idx} style={{ margin: '12px 0' }}>
                      <div>
                        <span>
                          <strong>{s.supplier}</strong> · Delivery by Day {s.arrival}
                        </span>
                        <strong>
                          {s.quantity.toLocaleString()} chips ({share}%)
                        </strong>
                      </div>
                      <div className="bar-track">
                        <i
                          style={
                            {
                              '--target-width': `${share}%`,
                              animationDelay: `${0.35 + idx * 0.1}s`,
                            } as React.CSSProperties
                          }
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>
        </>
      )}

      {isSupplier && (
        <>
          <div className="stats-grid pop-in">
            <div className="stat pop-in" style={{ animationDelay: '0.05s' }}>
              <span>
                <Truck size={14} /> Committed Dispatches
              </span>
              <strong>{totalCommitted.toLocaleString()}</strong>
              <em>Total chips allocated</em>
            </div>

            <div className="stat pop-in" style={{ animationDelay: '0.1s' }}>
              <span>
                <Layers size={14} /> Available Capacity
              </span>
              <strong>{totalCapacity.toLocaleString()}</strong>
              <em>Across inventory pools</em>
            </div>

            <div className="stat pop-in" style={{ animationDelay: '0.15s' }}>
              <span>
                <TrendingUp size={14} /> Pool Utilization
              </span>
              <strong>{utilizationPct}%</strong>
              <em>{totalSurplus.toLocaleString()} buffer chips remaining</em>
            </div>

            <div className="stat pop-in" style={{ animationDelay: '0.2s' }}>
              <span>
                <DollarSign size={14} /> Committed Value
              </span>
              <strong>{money(totalRevenue)}</strong>
              <em>Approved purchase amount</em>
            </div>
          </div>

          <Panel
            title="Capacity commitments & inventory pools"
            eyebrow="SUPPLY ALLOCATION GRAPH"
            className="pop-in"
            style={{ animationDelay: '0.25s' }}
          >
            <div className="bar-item">
              <div>
                <span>Overall Capacity Utilization</span>
                <strong>
                  {totalCommitted.toLocaleString()} / {totalCapacity.toLocaleString()} chips ({utilizationPct}%)
                </strong>
              </div>
              <div className="bar-track">
                <i
                  style={
                    {
                      '--target-width': `${utilizationPct}%`,
                      animationDelay: '0.1s',
                    } as React.CSSProperties
                  }
                />
              </div>
            </div>

            {stockPools.map((pool, idx) => {
              const committedInPool = shipments
                .filter(s => s.supplier === pool.name)
                .reduce((sum, s) => sum + (s.quantity || 0), 0);
              const poolPct = pool.capacity > 0 ? Math.min(100, Math.round((committedInPool / pool.capacity) * 100)) : 0;
              return (
                <div className="bar-item" key={pool.name}>
                  <div>
                    <span>
                      {pool.name} · Day {pool.arrival} availability · ${pool.unit_cost}/chip
                    </span>
                    <strong>
                      {committedInPool.toLocaleString()} / {pool.capacity.toLocaleString()} chips ({poolPct}%)
                    </strong>
                  </div>
                  <div className="bar-track">
                    <i
                      style={
                        {
                          '--target-width': `${poolPct}%`,
                          animationDelay: `${0.2 + idx * 0.1}s`,
                        } as React.CSSProperties
                      }
                    />
                  </div>
                </div>
              );
            })}

            {state.signal && (
              <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--line, #e4ebe7)' }}>
                <span className="eyebrow">LIVE TELEMETRY SIGNALS</span>
                <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', fontSize: '13px' }}>
                  <div>
                    <span className="muted">Reported ETA: </span>
                    <strong>Day {state.signal.reported_eta_day}</strong>
                  </div>
                  <div>
                    <span className="muted">Route Condition: </span>
                    <strong style={{ textTransform: 'capitalize' }}>{state.signal.route_status}</strong>
                  </div>
                  <div>
                    <span className="muted">Backlog Ratio: </span>
                    <strong>{state.signal.backlog_ratio?.toFixed(2)}x</strong>
                  </div>
                  <div>
                    <span className="muted">Transit Progress: </span>
                    <strong>{pct(state.signal.progress)}</strong>
                  </div>
                </div>
              </div>
            )}
          </Panel>
        </>
      )}

      <Panel
        title="Approved assignments & logistics"
        eyebrow="SHARED NETWORK PLAN"
        className="pop-in"
        style={{ animationDelay: '0.35s' }}
      >
        {decisions.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <span className="eyebrow">FACTORY ALLOCATION QUOTA</span>
            <Table rows={decisions} cols={decisionCols} />
          </div>
        )}
        <div>
          <span className="eyebrow">APPROVED SHIPMENT SCHEDULE</span>
          <Table rows={shipments} cols={shipmentCols} emptyText="No approved shipments assigned to your workspace yet." />
        </div>
        <p className="fine">
          Assignments reflect the approved shared plan. Pending coordinator recommendations do not change these numbers.
        </p>
      </Panel>
    </>
  );
}
