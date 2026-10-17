from __future__ import annotations

import html

import pandas as pd
import requests
import streamlit as st

from frontend.api_client import TradeOffAPI


st.set_page_config(page_title="TradeOff Network Control", page_icon="◈", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap');
    .stApp{background:#f4f6f3;color:#17211c}.block-container{max-width:1380px;padding-top:1.2rem}
    [data-testid="stHeader"],[data-testid="stToolbar"]{display:none}#MainMenu,footer{visibility:hidden}
    html,body,[class*="css"]{font-family:'DM Sans',sans-serif}
    .bar{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #dce2dd;padding:.6rem 0 1rem;margin-bottom:1rem}
    .brand{font-weight:700;font-size:1.05rem}.mono{font:500 .68rem 'IBM Plex Mono',monospace;color:#68746d;letter-spacing:.08em}
    .pill{border:1px solid #dce2dd;background:white;border-radius:99px;padding:.35rem .7rem;font-size:.73rem;color:#176b47}
    .hero{display:flex;justify-content:space-between;gap:1rem;align-items:end}.hero h1{font-size:2rem;margin:.3rem 0}.hero p{color:#66736b;margin:0}
    .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:1.2rem 0}
    .card{background:white;border:1px solid #dce2dd;border-radius:11px;padding:1rem}.k{font:500 .64rem 'IBM Plex Mono',monospace;color:#6c7871;text-transform:uppercase}
    .v{font-size:1.65rem;font-weight:700;margin:.25rem 0}.d{font-size:.73rem;color:#718078}
    .notice{background:#fff5df;border:1px solid #ead5a8;border-radius:10px;padding:.75rem .9rem;font-size:.82rem;margin:.8rem 0}
    .good{border-top:3px solid #176b47}.warn{border-top:3px solid #b56a1c}
    div.stButton>button{background:#173e2d;color:white;border-radius:8px;border:1px solid #173e2d;font-weight:600}
    div.stButton>button:hover{background:#0d2d20;color:white}
    @media(max-width:850px){.metrics{grid-template-columns:repeat(2,1fr)}.hero{align-items:start}.hero .mono{display:none}}
    </style>
    """,
    unsafe_allow_html=True,
)

api = TradeOffAPI()
try:
    health = api.health()
except requests.RequestException:
    st.error("TradeOff API is unavailable. Start it with `uvicorn backend.main:app --reload`.")
    st.stop()

if "scenario" not in st.session_state:
    st.session_state.scenario = api.create_scenario()
if "plan" not in st.session_state:
    st.session_state.plan = api.optimize(st.session_state.scenario["id"])

scenario = st.session_state.scenario
plan = st.session_state.plan
report = plan["report"]
privacy = next(item for item in report["strategies"] if item["strategy"].startswith("Privacy-Aware"))
full = next(item for item in report["strategies"] if item["strategy"].startswith("Full Information"))
allocated = sum(item["quantity"] for item in privacy["allocations"])
tone = "good" if privacy["unmet_demand"] == 0 else "warn"

st.markdown(
    f"""
    <div class="bar"><div class="brand">◈ TradeOff <span class="mono">/ NETWORK CONTROL</span></div><div class="pill">● {health['optimizer']} · LIVE</div></div>
    <div class="notice"><b>Controlled coordination active.</b> Private participant tables are isolated; the central solver receives only approved demand and supply fields.</div>
    <div class="hero"><div><div class="mono">SCENARIO {scenario['id'][:8].upper()} · {html.escape(scenario['status'])}</div><h1>Semiconductor recovery plan</h1><p>{html.escape(scenario['name'])} · {scenario['horizon_periods']}-period horizon</p></div><div class="mono">PLAN {plan['plan_id'][:8].upper()}</div></div>
    <div class="metrics">
      <div class="card {tone}"><div class="k">Allocated</div><div class="v">{allocated:,}</div><div class="d">units in recommended plan</div></div>
      <div class="card"><div class="k">Network cost</div><div class="v">${privacy['total_network_cost']:,.0f}</div><div class="d">full-info ${full['total_network_cost']:,.0f}</div></div>
      <div class="card {tone}"><div class="k">Unmet demand</div><div class="v">{privacy['unmet_demand']:,}</div><div class="d">units requiring escalation</div></div>
      <div class="card"><div class="k">Privacy gap</div><div class="v">{privacy['optimality_gap']:.2f}%</div><div class="d">{privacy['disclosed_fields']} approved fields</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

control, summary = st.columns([1, 1.4], gap="large")
with control:
    st.markdown("### Disruption control")
    preset_tab, language_tab = st.tabs(["Preset", "Natural language"])
    with preset_tab:
        st.write("Reduce the primary supplier's period-2 capacity by 40% and immediately re-optimize.")
        if st.button("Apply capacity loss −40%", width="stretch"):
            with st.spinner("Re-optimizing authoritative plan…"):
                st.session_state.plan = api.disrupt(scenario["id"])
                st.session_state.scenario = api.get_scenario(scenario["id"])
            st.rerun()
    with language_tab:
        command = st.text_input("Scenario instruction", "Simulate primary supplier losing 50% capacity on day 2")
        if st.button("Parse and run disruption", width="stretch"):
            with st.spinner("Parsing controls and re-optimizing…"):
                st.session_state.plan = api.disrupt(scenario["id"], command)
                st.session_state.scenario = api.get_scenario(scenario["id"])
            st.rerun()
with summary:
    st.markdown("### Executive briefing")
    st.info(report["executive_summary"])
    st.write(report["explanation"])
    st.caption("Narrative is downstream from immutable solver output and never computes allocations.")

overview, compare, privacy_tab = st.tabs(["Allocation plan", "Benchmark comparison", "Privacy & audit"])
with overview:
    rows = [{
        "Supplier": item["supplier_name"], "Factory": item["factory_name"], "Component": item["component"],
        "Quantity": item["quantity"], "Ship period": item["ship_period"], "Delivery period": item["delivery_period"],
        "Unit cost": f"${item['unit_cost']:,.2f}",
    } for item in privacy["allocations"]]
    st.dataframe(rows, width="stretch", hide_index=True)
with compare:
    benchmark_rows = [{
        "Strategy": item["strategy"], "Network cost": item["total_network_cost"],
        "Unmet demand": item["unmet_demand"], "Optimality gap %": item["optimality_gap"],
        "Fields disclosed": item["disclosed_fields"], "Runtime ms": item["solve_time_ms"],
    } for item in report["strategies"]]
    st.dataframe(benchmark_rows, width="stretch", hide_index=True)
    st.bar_chart(pd.DataFrame(benchmark_rows).set_index("Strategy")[["Network cost"]])
with privacy_tab:
    audit = api.audit_log()
    st.success("RBAC active · private endpoints require matching participant identity")
    st.dataframe(audit, width="stretch", hide_index=True)

st.markdown(
    '<div class="mono" style="border-top:1px solid #dce2dd;margin-top:2rem;padding:1rem 0">TRADEOFF 2.0 · OR-TOOLS AUTHORITATIVE · SQLALCHEMY PERSISTED</div>',
    unsafe_allow_html=True,
)
