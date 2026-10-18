import React from 'react';
import { Truck, Clock, Activity, AlertTriangle, CheckCircle2, ShieldCheck, Package } from 'lucide-react';
import type { LiveState, User } from '../types';
import { Badge } from '../components/common/Badge';
import { Panel } from '../components/common/Panel';
import { Table, decisionCols, shipmentCols } from '../components/common/Table';
import { Empty } from '../components/common/Empty';

interface ParticipantPageProps {
  state: LiveState;
  user: User;
}

export function ParticipantPage({ state, user }: ParticipantPageProps) {
  const myDecision = state.approved_plan.decisions.find(
    (d: any) => d.factory === user.participant
  ) || {} as any;

  const myShipments = state.approved_plan.shipments.filter(
    (s: any) => s.factory === user.participant
  );

  const totalChips = myShipments.reduce((n: number, s: any) => n + s.quantity, 0);
  const unmet = myDecision.unmet || 0;
  const requested = myDecision.requested || 0;
  const allocated = myDecision.allocated || 0;
  const earliest = myShipments.length
    ? Math.min(...myShipments.map((s: any) => s.arrival))
    : '—';
  const fillPct = requested ? Math.round((allocated / requested) * 100) : 100;

  return (
    <>
      {/* Page Header */}
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR WORKSPACE / SHARED ALLOCATION</span>
          <h1>
            {user.participant}
            <span className="heading-dot" />
          </h1>
          <p className="muted">
            Live assignments from the coordinator-approved plan. Updates publish only after coordinator approval.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <Badge tone={unmet ? 'amber' : 'green'}>
            {unmet ? `${unmet} chips unmet` : 'Fully allocated'}
          </Badge>
          <Badge tone="green">Revision {state.approved_revision}</Badge>
        </div>
      </div>

      {/* KPI Stats */}
      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', marginBottom: '24px' }}>
        <div className="stat">
          <span><Truck size={17} /> Chips allocated</span>
          <strong>{allocated.toLocaleString()}<em> chips</em></strong>
          <small>From approved plan</small>
        </div>
        <div className="stat">
          <span><AlertTriangle size={17} /> Unmet demand</span>
          <strong style={{ color: unmet ? '#b18536' : '#4d8c5a' }}>
            {unmet.toLocaleString()}<em> chips</em>
          </strong>
          <small>{unmet ? 'Below requested' : 'No shortage'}</small>
        </div>
        <div className="stat">
          <span><Clock size={17} /> Earliest arrival</span>
          <strong>Day {earliest}</strong>
          <small>Soonest shipment</small>
        </div>
        <div className="stat">
          <span><Activity size={17} /> Fill rate</span>
          <strong>{fillPct}<em>%</em></strong>
          <small>{requested.toLocaleString()} chips requested</small>
        </div>
      </div>

      {/* Fill Rate Progress Bar */}
      <div style={{
        background: 'white',
        border: '1px solid #e4ebe7',
        borderRadius: '12px',
        padding: '20px 24px',
        marginBottom: '20px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <span style={{ fontSize: '11px', color: '#758a81', fontWeight: 600, letterSpacing: '1px' }}>
            ALLOCATION FILL RATE
          </span>
          <span style={{ fontSize: '11px', color: fillPct === 100 ? '#4d7d55' : '#a47b28', fontWeight: 600 }}>
            {fillPct}% allocated
          </span>
        </div>
        <div style={{ background: '#edf2e8', borderRadius: '6px', height: '10px', overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${fillPct}%`,
            background: fillPct === 100 ? '#44a77b' : '#d19c4e',
            borderRadius: '6px',
            transition: 'width .5s'
          }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px', fontSize: '10px', color: '#9aa797' }}>
          <span>0 chips</span>
          <span>{requested.toLocaleString()} requested</span>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="plan-grid">
        {/* Approved Assignments Panel */}
        <Panel
          title="Your approved assignments"
          eyebrow="COORDINATOR-PUBLISHED PLAN"
          action={<Badge tone="green"><CheckCircle2 size={12} /> Active</Badge>}
        >
          {myDecision.factory ? (
            <div style={{ marginBottom: '20px' }}>
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
                marginBottom: '16px'
              }}>
                {[
                  ['Factory', myDecision.factory],
                  ['Requested', `${requested.toLocaleString()} chips`],
                  ['Allocated', `${allocated.toLocaleString()} chips`],
                  ['Unmet', unmet ? `${unmet} chips ⚠️` : 'None ✓'],
                ].map(([k, v]) => (
                  <div key={k} style={{
                    background: '#f8faf6',
                    borderRadius: '8px',
                    padding: '14px 16px',
                    border: '1px solid #e4ebe7'
                  }}>
                    <div style={{
                      fontSize: '9px',
                      color: '#8fa088',
                      letterSpacing: '1px',
                      marginBottom: '6px'
                    }}>
                      {k.toUpperCase()}
                    </div>
                    <div style={{
                      fontSize: '14px',
                      fontWeight: 600,
                      color: k === 'Unmet' && unmet ? '#b18536' : '#2d5a3d'
                    }}>
                      {v}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <Empty>No assignment found for your factory.</Empty>
          )}
          <p className="fine">
            Pending recommendations do not change these assignments until a coordinator approves.
          </p>
        </Panel>

        {/* Incoming Shipments Panel */}
        <Panel
          title="Incoming shipments"
          eyebrow="SUPPLY INSTRUCTIONS"
          action={<Badge>{myShipments.length} shipment{myShipments.length !== 1 ? 's' : ''}</Badge>}
        >
          {myShipments.length ? (
            myShipments.map((s: any, i: number) => (
              <div key={i} style={{
                display: 'flex',
                alignItems: 'center',
                gap: '14px',
                padding: '16px 0',
                borderBottom: i < myShipments.length - 1 ? '1px solid #edf1e9' : ''
              }}>
                <div style={{
                  background: '#e8f2e4',
                  color: '#4d7d55',
                  borderRadius: '9px',
                  padding: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0
                }}>
                  <Truck size={18} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: '#2d5a3d' }}>
                    {s.supplier}
                  </div>
                  <div style={{ fontSize: '10px', color: '#8fa088', marginTop: '3px' }}>
                    {s.quantity.toLocaleString()} chips · Arrives Day {s.arrival}
                  </div>
                </div>
                <Badge tone="green">Day {s.arrival}</Badge>
              </div>
            ))
          ) : (
            <Empty>No shipments assigned yet.</Empty>
          )}
          <p className="fine">
            Contact your coordinator if assignments do not match expectations.
          </p>
        </Panel>
      </div>

      {/* Full Table View */}
      <Panel title="Full allocation details" eyebrow="COMPLETE PLAN VIEW">
        {state.approved_plan.decisions.length > 0 && (
          <Table rows={state.approved_plan.decisions} cols={decisionCols} />
        )}
        <Table rows={state.approved_plan.shipments} cols={shipmentCols} />
      </Panel>

      {/* IBM Banner */}
      <div style={{
        background: 'linear-gradient(115deg,#f3f8ef,#fff)',
        border: '1px solid #dce9d7',
        borderRadius: '12px',
        padding: '20px 24px',
        marginBottom: '20px',
        display: 'flex',
        alignItems: 'center',
        gap: '16px'
      }}>
        <div style={{
          background: '#e4f0de',
          color: '#4d7d55',
          borderRadius: '10px',
          padding: '12px',
          display: 'flex',
          flexShrink: 0
        }}>
          <ShieldCheck size={22} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: '#2d5a3d', marginBottom: '4px' }}>
            One shared plan. Your assignments are locked in.
          </div>
          <div style={{ fontSize: '11px', color: '#7b8c7a' }}>
            Recommendations are separate until approved. Your coordinator controls what gets published to the network.
          </div>
        </div>
        <Badge tone="green">IBM Z DATATHON</Badge>
      </div>
    </>
  );
}
