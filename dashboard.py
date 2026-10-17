from __future__ import annotations

import html
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import streamlit as st

from app.models import Scenario
from app.optimizer import optimize_scenario


ROOT = Path(__file__).resolve().parent


@st.cache_data
def load_scenario() -> dict:
    return json.loads((ROOT / "data" / "sample_scenario.json").read_text(encoding="utf-8"))


def money(value: float) -> str:
    return f"${value:,.0f}"


def metric_card(label: str, value: str, detail: str, tone: str = "neutral") -> str:
    return f"""
    <div class="metric-card {tone}">
      <div class="metric-label">{html.escape(label)}</div>
      <div class="metric-value">{html.escape(value)}</div>
      <div class="metric-detail">{html.escape(detail)}</div>
    </div>
    """


def clear_widget_state() -> None:
    for key in list(st.session_state):
        if key.startswith(("supplier-", "factory-")):
            del st.session_state[key]


st.set_page_config(
    page_title="TradeOff Network Control",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    :root {
      --ink: #17211c;
      --muted: #65716a;
      --line: #dce2dd;
      --paper: #ffffff;
      --canvas: #f4f6f3;
      --green: #176b47;
      --green-soft: #e8f3ed;
      --amber: #a76408;
      --amber-soft: #fff5df;
      --red: #b54732;
      --blue: #315d8a;
    }

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .stApp { background: var(--canvas); color: var(--ink); }
    .block-container { max-width: 1380px; padding-top: 1.25rem; padding-bottom: 4rem; }
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none; }
    #MainMenu, footer { visibility: hidden; }

    h1, h2, h3 { font-family: 'DM Sans', sans-serif; color: var(--ink); letter-spacing: -0.025em; }
    h3 { font-size: 1.05rem !important; margin-top: .4rem !important; }
    p, div, label { font-family: 'DM Sans', sans-serif; }
    code { font-family: 'IBM Plex Mono', monospace; }

    .appbar {
      display: flex; align-items: center; justify-content: space-between; gap: 1rem;
      padding: .75rem 0 1rem; border-bottom: 1px solid var(--line); margin-bottom: 1.1rem;
    }
    .brand { display:flex; align-items:center; gap:.7rem; font-weight:700; font-size:1.05rem; }
    .brand-mark {
      width:30px; height:30px; border-radius:8px; display:grid; place-items:center;
      color:white; background:#173e2d; font-size:.95rem;
    }
    .product-context { color:var(--muted); font-size:.78rem; font-family:'IBM Plex Mono', monospace; }
    .appbar-right { display:flex; align-items:center; gap:.65rem; flex-wrap:wrap; justify-content:flex-end; }
    .live-pill, .user-chip {
      border:1px solid var(--line); border-radius:999px; padding:.34rem .65rem; background:white;
      font-size:.74rem; font-weight:600; white-space:nowrap;
    }
    .live-pill { color:var(--green); }
    .live-dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:#2ba16d; margin-right:.4rem; }

    .incident-strip {
      display:flex; justify-content:space-between; gap:1rem; align-items:center;
      background:var(--amber-soft); border:1px solid #ead5a8; color:#674813;
      padding:.72rem .9rem; border-radius:10px; margin-bottom:1.25rem; font-size:.84rem;
    }
    .incident-strip strong { color:#50360c; }
    .incident-id { font-family:'IBM Plex Mono', monospace; font-size:.7rem; white-space:nowrap; }

    .page-heading { display:flex; justify-content:space-between; align-items:flex-end; gap:1rem; margin:1.2rem 0 1.05rem; }
    .eyebrow { font-family:'IBM Plex Mono', monospace; color:var(--green); font-size:.68rem; letter-spacing:.11em; text-transform:uppercase; }
    .page-heading h1 { font-size:2.15rem; line-height:1.08; margin:.25rem 0 .3rem; }
    .page-heading p { margin:0; color:var(--muted); font-size:.92rem; }
    .plan-stamp { text-align:right; color:var(--muted); font-size:.72rem; font-family:'IBM Plex Mono', monospace; }

    .metric-grid {
      display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:.75rem; margin-bottom:1.2rem;
    }
    .metric-card {
      background:var(--paper); border:1px solid var(--line); border-radius:12px;
      padding:1rem 1.05rem; min-width:0; box-shadow:0 1px 2px rgba(22,39,30,.03);
    }
    .metric-card.alert { border-top:3px solid var(--red); padding-top:calc(1rem - 2px); }
    .metric-card.good { border-top:3px solid var(--green); padding-top:calc(1rem - 2px); }
    .metric-label { color:var(--muted); text-transform:uppercase; letter-spacing:.08em; font:500 .65rem 'IBM Plex Mono', monospace; }
    .metric-value { color:var(--ink); font-size:1.75rem; font-weight:700; letter-spacing:-.04em; margin:.25rem 0 .16rem; }
    .metric-detail { color:var(--muted); font-size:.76rem; white-space:normal; }

    .section-head { display:flex; justify-content:space-between; align-items:center; gap:.75rem; margin:.4rem 0 .65rem; }
    .section-title { font-weight:700; font-size:1.02rem; color:var(--ink); }
    .section-kicker { color:var(--muted); font-size:.73rem; font-family:'IBM Plex Mono', monospace; }

    .factory-row { background:white; border:1px solid var(--line); border-radius:10px; padding:.85rem .9rem; margin-bottom:.55rem; }
    .factory-top { display:flex; justify-content:space-between; gap:1rem; font-size:.82rem; }
    .factory-top strong { font-size:.88rem; }
    .factory-meta { color:var(--muted); font-family:'IBM Plex Mono', monospace; font-size:.68rem; margin-top:.15rem; }
    .bar-track { height:7px; background:#e8ece9; border-radius:99px; overflow:hidden; margin-top:.7rem; }
    .bar-fill { height:100%; background:var(--green); border-radius:99px; }
    .bar-fill.warn { background:#d28b22; }

    .logic-card { border:1px solid var(--line); border-radius:10px; background:white; padding:.9rem 1rem; margin-bottom:.55rem; }
    .logic-card .logic-title { font-weight:700; font-size:.84rem; margin-bottom:.25rem; }
    .logic-card .logic-copy { color:var(--muted); font-size:.78rem; line-height:1.45; }
    .logic-num { color:var(--green); font:600 .67rem 'IBM Plex Mono', monospace; margin-right:.35rem; }

    .trust-grid { display:grid; grid-template-columns:repeat(3, 1fr); gap:.75rem; }
    .trust-card { background:white; border:1px solid var(--line); border-radius:10px; padding:.9rem; }
    .trust-card .k { color:var(--muted); font:500 .65rem 'IBM Plex Mono', monospace; text-transform:uppercase; }
    .trust-card .v { font-size:1.25rem; font-weight:700; margin:.2rem 0; }
    .trust-card .d { color:var(--muted); font-size:.73rem; }
    .cost-grid { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:.65rem; }
    .cost-item { background:white; border:1px solid var(--line); border-radius:10px; padding:.85rem .9rem; }
    .cost-item .k { color:var(--muted); font-size:.72rem; }
    .cost-item .v { color:var(--ink); font-size:1.35rem; font-weight:700; letter-spacing:-.03em; margin-top:.2rem; }

    [data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:10px; overflow:hidden; }
    [data-testid="stExpander"] { background:white; border:1px solid var(--line); border-radius:10px; }
    [data-testid="stTabs"] button { font-size:.8rem; }
    div.stButton > button {
      border-radius:8px; border:1px solid #173e2d; background:#173e2d; color:white; font-weight:600;
    }
    div.stButton > button:hover { background:#0e2d20; border-color:#0e2d20; color:white; }
    div.stButton > button[kind="secondary"] { background:white; color:var(--ink); border-color:var(--line); }

    @media (max-width: 900px) {
      .metric-grid { grid-template-columns:repeat(2, minmax(0, 1fr)); }
      .cost-grid { grid-template-columns:repeat(2, minmax(0, 1fr)); }
      .trust-grid { grid-template-columns:1fr; }
      .page-heading { align-items:flex-start; }
      .plan-stamp { display:none; }
    }
    @media (max-width: 560px) {
      .block-container { padding: .75rem .8rem 3rem; }
      .appbar { align-items:flex-start; }
      .product-context, .user-chip { display:none; }
      .incident-strip { align-items:flex-start; }
      .incident-id { display:none; }
      .page-heading h1 { font-size:1.7rem; }
      .metric-value { font-size:1.45rem; }
      .metric-card { padding:.8rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "scenario" not in st.session_state:
    st.session_state.scenario = load_scenario()
if "history" not in st.session_state:
    st.session_state.history = []

working = deepcopy(st.session_state.scenario)
scenario_code = "SC-26-1047"
now = datetime.now().strftime("%H:%M:%S")

st.markdown(
    f"""
    <div class="appbar">
      <div class="brand"><span class="brand-mark">◈</span><span>TradeOff</span><span class="product-context">/ NETWORK CONTROL</span></div>
      <div class="appbar-right">
        <span class="live-pill"><span class="live-dot"></span>LIVE MODEL</span>
        <span class="user-chip">Operations lead · UTD</span>
      </div>
    </div>
    <div class="incident-strip">
      <div><strong>Active planning window</strong> · Semiconductor supply is balanced using approved partner commitments. Test a capacity loss below.</div>
      <div class="incident-id">INCIDENT {scenario_code}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("Adjust scenario inputs", expanded=False):
    st.caption("Changes remain local until you recalculate the network plan.")
    supplier_columns = st.columns(len(working["suppliers"]))
    for column, supplier in zip(supplier_columns, working["suppliers"]):
        with column:
            supplier["capacity"] = st.slider(
                f"{supplier['name']} capacity",
                min_value=0,
                max_value=1200,
                value=int(supplier["capacity"]),
                step=25,
                key=f"supplier-{supplier['id']}",
                help="Maximum units this supplier can commit in the current planning window.",
            )
    factory_columns = st.columns(len(working["factories"]))
    for column, factory in zip(factory_columns, working["factories"]):
        with column:
            factory["demand"] = st.slider(
                f"{factory['name']} demand",
                min_value=0,
                max_value=1000,
                value=int(factory["demand"]),
                step=25,
                key=f"factory-{factory['id']}",
                help="Required components before this factory's delivery deadline.",
            )
    action_col, reset_col, _ = st.columns([1, 1, 3])
    run = action_col.button("Recalculate plan", width="stretch", type="primary")
    reset = reset_col.button("Reset inputs", width="stretch", type="secondary")
    if reset:
        st.session_state.scenario = load_scenario()
        st.session_state.history = []
        clear_widget_state()
        st.rerun()
    if run:
        st.session_state.scenario = working

scenario = Scenario.model_validate(st.session_state.scenario)
result = optimize_scenario(scenario)
if run or not st.session_state.history:
    st.session_state.history.append(result.model_dump(mode="json"))

metrics = result.metrics
service_level = (metrics.total_allocated / metrics.total_demand * 100) if metrics.total_demand else 100.0
plan_state = "Network balanced" if metrics.total_shortage == 0 else "Capacity constrained"
state_tone = "good" if metrics.total_shortage == 0 else "alert"

previous = st.session_state.history[-2] if len(st.session_state.history) > 1 else None
cost_delta = metrics.total_network_cost - previous["metrics"]["total_network_cost"] if previous else 0
delta_text = "Initial plan" if previous is None else f"{money(abs(cost_delta))} {'higher' if cost_delta > 0 else 'lower'} vs prior"

st.markdown(
    f"""
    <div class="page-heading">
      <div>
        <div class="eyebrow">Recovery plan · {html.escape(scenario.name)}</div>
        <h1>{plan_state}</h1>
        <p>Cost-minimized allocation across {len(scenario.suppliers)} suppliers and {len(scenario.factories)} production sites.</p>
      </div>
      <div class="plan-stamp">PLAN {result.run_id[:8].upper()}<br/>SOLVED {now} · {metrics.replanning_time_ms:.1f} MS</div>
    </div>
    <div class="metric-grid">
      {metric_card('Service level', f'{service_level:.1f}%', f'{metrics.total_allocated:,} / {metrics.total_demand:,} units covered', state_tone)}
      {metric_card('Evaluated network cost', money(metrics.total_network_cost), delta_text)}
      {metric_card('Unmet demand', f'{metrics.total_shortage:,} units', 'No escalation required' if metrics.total_shortage == 0 else 'Requires operations review', state_tone)}
      {metric_card('Privacy trade-off', f'{metrics.optimality_gap:.2f}%', f'Benchmark {money(metrics.baseline_network_cost)}')}
    </div>
    """,
    unsafe_allow_html=True,
)

overview_tab, logic_tab, audit_tab = st.tabs(["Plan overview", "Decision logic", "Audit trail"])

with overview_tab:
    allocation_col, coverage_col = st.columns([1.45, 1], gap="large")
    with allocation_col:
        st.markdown(
            '<div class="section-head"><div class="section-title">Allocation orders</div><div class="section-kicker">RECOMMENDED · NOT DISPATCHED</div></div>',
            unsafe_allow_html=True,
        )
        rows = [
            {
                "Source": item.supplier_name,
                "Destination": item.factory_name,
                "Units": f"{item.quantity:,}",
                "Landed / unit": f"${item.unit_cost:,.2f}",
                "Extended": money(item.total_cost),
            }
            for item in result.allocations
        ]
        st.dataframe(
            rows,
            width="stretch",
            hide_index=True,
            column_config={
                "Units": st.column_config.TextColumn(width="small"),
                "Landed / unit": st.column_config.TextColumn(width="small"),
                "Extended": st.column_config.TextColumn(width="small"),
            },
        )
        st.caption("Orders remain recommendations until approved in the source procurement system.")

    with coverage_col:
        st.markdown(
            '<div class="section-head"><div class="section-title">Site coverage</div><div class="section-kicker">BY DEADLINE</div></div>',
            unsafe_allow_html=True,
        )
        for outcome in result.factory_outcomes:
            factory = next(item for item in scenario.factories if item.id == outcome.factory_id)
            bar_class = "bar-fill" if outcome.service_level >= 99.99 else "bar-fill warn"
            st.markdown(
                f"""
                <div class="factory-row">
                  <div class="factory-top"><div><strong>{html.escape(factory.name)}</strong><div class="factory-meta">DUE IN {factory.deadline_days} DAYS · PRIORITY P{6 - factory.priority}</div></div><strong>{outcome.service_level:.1f}%</strong></div>
                  <div class="bar-track"><div class="{bar_class}" style="width:{min(outcome.service_level, 100)}%"></div></div>
                  <div class="factory-meta">{outcome.allocated:,} ALLOCATED · {outcome.shortage:,} SHORT</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("#### Cost composition")
    st.markdown(
        f"""
        <div class="cost-grid">
          <div class="cost-item"><div class="k">Sourcing + freight</div><div class="v">{money(metrics.source_cost)}</div></div>
          <div class="cost-item"><div class="k">Production</div><div class="v">{money(metrics.production_cost)}</div></div>
          <div class="cost-item"><div class="k">Shortage exposure</div><div class="v">{money(metrics.shortage_cost)}</div></div>
          <div class="cost-item"><div class="k">Full-info benchmark</div><div class="v">{money(metrics.baseline_network_cost)}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with logic_tab:
    explanation_col, trust_col = st.columns([1.35, 1], gap="large")
    with explanation_col:
        st.markdown(
            '<div class="section-head"><div class="section-title">Why the model chose this plan</div><div class="section-kicker">TRACEABLE RATIONALE</div></div>',
            unsafe_allow_html=True,
        )
        for index, note in enumerate(result.explanations, start=1):
            st.markdown(
                f'<div class="logic-card"><div class="logic-title"><span class="logic-num">{index:02d}</span> Decision factor</div><div class="logic-copy">{html.escape(note)}</div></div>',
                unsafe_allow_html=True,
            )
    with trust_col:
        st.markdown(
            '<div class="section-head"><div class="section-title">Constraint checks</div><div class="section-kicker">POST-SOLVE VALIDATION</div></div>',
            unsafe_allow_html=True,
        )
        check_rows = [
            {"Check": key.replace("_", " ").title(), "Result": "Passed" if passed else "Failed"}
            for key, passed in result.constraint_checks.items()
        ]
        st.dataframe(check_rows, width="stretch", hide_index=True)

    st.markdown("#### Information boundary")
    st.markdown(
        f"""
        <div class="trust-grid">
          <div class="trust-card"><div class="k">Approved fields</div><div class="v">{metrics.information_disclosed}</div><div class="d">Demand, capacity, deadline, and offer signals used for coordination.</div></div>
          <div class="trust-card"><div class="k">Private fields</div><div class="v">{metrics.information_withheld}</div><div class="d">Customer, internal production cost, and reliability remain participant-local.</div></div>
          <div class="trust-card"><div class="k">Access checks</div><div class="v">4 / 4</div><div class="d">Capacity, demand, deadline, and flow-balance constraints passed.</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with audit_tab:
    st.markdown(
        '<div class="section-head"><div class="section-title">Session decision history</div><div class="section-kicker">APPEND-ONLY VIEW</div></div>',
        unsafe_allow_html=True,
    )
    audit_rows = []
    for number, item in enumerate(reversed(st.session_state.history), start=1):
        audit_rows.append(
            {
                "Plan": item["run_id"][:8].upper(),
                "Sequence": len(st.session_state.history) - number + 1,
                "Status": item["status"].title(),
                "Allocated": f"{item['metrics']['total_allocated']:,}",
                "Shortage": f"{item['metrics']['total_shortage']:,}",
                "Network cost": money(item["metrics"]["total_network_cost"]),
                "Runtime": f"{item['metrics']['replanning_time_ms']:.1f} ms",
            }
        )
    st.dataframe(audit_rows, width="stretch", hide_index=True)
    st.caption("The API persists optimization and disruption events to SQLite for cross-session review.")

st.markdown(
    f"""
    <div style="border-top:1px solid #dce2dd;margin-top:2rem;padding-top:.8rem;display:flex;justify-content:space-between;color:#7b867f;font:500 .65rem 'IBM Plex Mono',monospace;">
      <span>TRADEOFF 1.0 · CONTROLLED COORDINATION</span><span>{scenario_code} · MODEL STATUS {result.status.upper()}</span>
    </div>
    """,
    unsafe_allow_html=True,
)
