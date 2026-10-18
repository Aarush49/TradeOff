# A three-minute TradeOff demonstration

Run `python3 server.py`, open http://localhost:8501 (via the SSH tunnel when remote),
and sign in as **Network_Coordinator** with its generated password (see README). The model and SQLite state
run on that server. The page is an event-driven simulation, not live factory data.

1. **Describe the decision.** Factory A makes medical devices and needs at least
   400 chips by day 2. Factory B needs chips by day 4. Supplier S is the primary
   shipment; normal and reserved alternative supply are separate synthetic pools.
2. **Start new replay
3. → Gradual congestion.** New checkpoints arrive every five
   seconds. Show the received revision, changing ETA/backlog/route signals,
   simulation-trained miss risk, and proposed backup reservation. The approved
   shipment table remains unchanged while the proposal is pending.
4. **Wait for the pause before the outcome.** After four checkpoints, the replay
   stops. Expand arrival scenarios/candidate plans. Explain the illustrative
   modeled-risk constraint and expected-cost calculation.
5. **Review recommendation.** Inspect the proposed allocation and shipment table.
   Add an optional decision note, then **Approve & publish**. Approval
   updates the shared plan, not a real purchase order.
6. **Show the participant view.** Sign out and sign in as **Factory_A**, or use a separate
   browser profile/private window to retain the coordinator session. Factory A
   sees its approved alternative-supply assignment, not the network's private
   proposals or audit. Its account has a server-assigned factory role.
7. **Reveal simulated outcome.** Return to the coordinator and click **Reveal
   simulated outcome**. The final arrival is emitted now, after the decision.
   Show realized cost, unmet demand, and minimum breaches under the approved plan.
8. **Show evidence.** Open **Decision audit** to inspect the timeline and export it. In
   policy comparison, run 300 episodes on the server; show its architecture and
   separate server-only processing latency from browser/human response time.

For a counterfactual, repeat the same congestion replay and reject/leave the
proposal unapproved, then reveal the outcome. Compare the default plan's realized
shortfall with the approved-response run; both are explicitly synthetic scenarios.
The 300-episode comparison includes an always-reserve baseline to expose the
cost of protecting every order rather than selectively reserving.

Suggested pitch: **TradeOff processes shipment events on LinuxONE, estimates
arrival risk, and proposes constrained supply reallocations for human approval.
The prototype demonstrates the decision loop using labeled simulated streams;
real industrial prediction quality still needs validation.**

Do not claim the simulation model was trained on real semiconductor outcomes,
that its synthetic score is comparable to DataCo accuracy, or that a laptop
latency figure demonstrates IBM Z acceleration. Leave Google OAuth for the next
phase; keep the demo's synthetic-data scope visible.
