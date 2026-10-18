import React from 'react';
import type { LiveState, User } from '../types';
import { Badge } from '../components/common/Badge';
import { Panel } from '../components/common/Panel';
import { Table, decisionCols, shipmentCols } from '../components/common/Table';

interface ParticipantPageProps {
  state: LiveState;
  user: User;
}

export function ParticipantPage({ state, user }: ParticipantPageProps) {
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR WORKSPACE / SHARED ALLOCATION</span>
          <h1>{user.participant}</h1>
          <p className="muted">
            Your assignments from the coordinator-approved plan.
          </p>
        </div>
        <Badge tone="green">Revision {state.approved_revision}</Badge>
      </div>

      <Panel title="Your approved assignments">
        {state.approved_plan.decisions.length > 0 && (
          <Table rows={state.approved_plan.decisions} cols={decisionCols} />
        )}
        <Table rows={state.approved_plan.shipments} cols={shipmentCols} />
        <p className="fine">
          Pending recommendations do not change these assignments.
        </p>
      </Panel>
    </>
  );
}
