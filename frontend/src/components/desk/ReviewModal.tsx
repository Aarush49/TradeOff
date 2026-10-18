import React, { useEffect } from 'react';
import { X, Check } from 'lucide-react';
import type { Proposal, LiveState } from '../../types';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { Table, decisionCols, shipmentCols } from '../common/Table';
import { money } from '../../utils/formatters';

interface ReviewModalProps {
  proposal: Proposal;
  state: LiveState;
  busy: boolean;
  canDecide: boolean;
  note: string;
  onNoteChange: (note: string) => void;
  onClose: () => void;
  onDecide: (decision: 'approve' | 'reject') => Promise<void>;
}

export function ReviewModal({
  proposal,
  state,
  busy,
  canDecide,
  note,
  onNoteChange,
  onClose,
  onDecide,
}: ReviewModalProps) {
  const analysis = proposal.data.analysis;
  const recommended = analysis.recommended;

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const dialog = document.querySelector('.review-modal') as HTMLElement | null;
    dialog?.querySelector('button')?.focus();

    const trap = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !dialog) return;
      const items = Array.from(
        dialog.querySelectorAll<HTMLElement>(
          'button:not(:disabled),textarea,input,select,[tabindex="0"]'
        )
      );
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    };

    dialog?.addEventListener('keydown', trap);
    return () => {
      document.body.style.overflow = overflow;
      dialog?.removeEventListener('keydown', trap);
      previous?.focus();
    };
  }, []);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <section
        className="review-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-title"
        onClick={e => e.stopPropagation()}
      >
        <div className="modal-header">
          <Badge tone="amber">REVISION {proposal.revision}</Badge>
          <Button
            className="icon-button"
            aria-label="Close review"
            icon={X}
            onClick={onClose}
          />
        </div>

        <h2 id="review-title">Review your recovery plan</h2>
        <p className="muted">
          {recommended
            ? `Reserve ${recommended.reserve_quantity.toLocaleString()} alternative chips with an expected total cost of ${money(
                recommended.expected_cost
              )}.`
            : 'No plan currently meets the policy.'}
        </p>

        {recommended && (
          <>
            <Table rows={recommended.plan.decisions} cols={decisionCols} />
            <Table rows={recommended.plan.shipments} cols={shipmentCols} />
          </>
        )}

        <label>
          Decision note <span className="muted">(optional)</span>
          <textarea
            value={note}
            maxLength={500}
            onChange={e => onNoteChange(e.target.value)}
            placeholder="What informed your decision?"
          />
        </label>

        {state.signal_stale && (
          <p className="error">
            Checkpoint is stale. Receive a fresh update before approval.
          </p>
        )}

        <div className="modal-actions">
          <Button
            className="secondary"
            disabled={busy || !canDecide}
            onClick={() => onDecide('reject')}
          >
            Reject proposal
          </Button>
          <Button
            icon={Check}
            disabled={busy || !canDecide || !recommended || state.signal_stale}
            onClick={() => onDecide('approve')}
          >
            Approve & publish
          </Button>
        </div>

        <p className="fine">
          Approval updates simulated reservations, not a real purchase order.
        </p>
      </section>
    </div>
  );
}
