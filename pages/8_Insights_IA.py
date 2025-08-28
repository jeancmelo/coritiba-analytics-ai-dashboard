import json
import pandas as pd
import streamlit as st
from core import api_client, ui_utils, ai

st.title("🧠 Insights com IA — Hub")

# ------------------------------- filtros ------------------------------
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

c1, c2, c3 = st.columns([1,4,1])
with c1: ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with c2: st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with c3: ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")
st.caption("Central de inteligência: insights automáticos e respostas por prompt.")

# -------------------------- contexto enxuto/robusto -------------------
with st.expander("📦 Coletando dados de contexto", expanded=False):
    st.caption("Estatísticas, últimos jogos, ranking e próximo adversário.")

stats = api_client.team_statistics(league["league_id"], season, team["team_id"])
stats = stats[0] if isinstance(stats, list) and stats else stats

rank = None
try:
    std = api_client.standings(league["league_id"], season)
    table = std[0]["league"]["standings"][0]
    for row in table:
        if row["team"]["id"] == team["team_id"]:
            rank = row["rank"]; break
except Exception:
    pass

fixtures = api_client.fixtures(team["team_id"], season) or []
for m in fixtures:
    try: m["_d"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
    except Exception: m["_d"] = pd.NaT
fixtures = sorted(fixtures, key=lambda x: x.get("_d") if x.get("_d") is not None else pd.Timestamp(0), reverse=True)

last_games = []
for fx in fixtures[:10]:
    gh = (fx.get("goals") or {}).get("home")
    ga = (fx.get("goals") or {}).get("away")
    home = (fx.get("teams") or {}).get("home", {})
    away = (fx.get("teams") or {}).get("away", {})
    is_home = home.get("id") == team["team_id"]
    our_goals = gh if is_home else ga
    opp_goals = ga if is_home else gh
    res = "—"
    if our_goals is not None and opp_goals is not None:
        res = "V" if our_goals > opp_goals else ("D" if our_goals < opp_goals else "E")
    last_games.append({
        "date": str((fx.get("fixture") or {}).get("date"))[:19],
        "home": home.get("name","-"),
        "away": away.get("name","-"),
        "score": f"{gh}-{ga}",
        "res": res
    })

next_fx = api_client.fixtures(team["team_id"], season, next=1)
next_context = None
if next_fx:
    fx = next_fx[0]
    home = (fx.get("teams") or {}).get("home", {})
    away = (fx.get("teams") or {}).get("away", {})
    is_home = home.get("id") == team["team_id"]
    opp = away if is_home else home
    next_context = {
        "fixture_id": (fx.get("fixture") or {}).get("id"),
        "date": (fx.get("fixture") or {}).get("date"),
        "opponent": {"id": opp.get("id"), "name": opp.get("name"), "logo": opp.get("logo")},
        "is_home": is_home,
        "round": (fx.get("league") or {}).get("round"),
    }

context = {
    "mode": "auto",
    "season": season,
    "league": league,
    "team": team,
    "standings_rank": rank,
    "stats": stats,
    "last_games": last_games,
    "next_fixture": next_context,
}

# ------------------------------- debug curto --------------------------
with st.expander("🔧 Debug da IA (resumo)", expanded=False):
    summary = {k: (len(v) if isinstance(v, list) else ("<obj>" if isinstance(v, dict) else v))
               for k, v in context.items()}
    st.code(json.dumps(summary, ensure_ascii=False, indent=2))
    if st.checkbox("Ver JSON bruto do contexto (truncado)"):
        raw = json.dumps(context, ensure_ascii=False, indent=2)
        st.code(raw[:4000] + ("...\n(truncado)" if len(raw)>4000 else ""))

# -------------------------- renderizador de cartões -------------------
def render_cards(cards):
    for ins in cards:
        with st.container(border=True):
            st.caption(ins.get("type","insight"))
            st.subheader(ins.get("title","(sem título)"))
            st.write(ins.get("summary",""))
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Por que importa**")
                st.write(ins.get("why_it_matters",""))
            with col2:
                st.write("**Ação sugerida**")
                st.write(ins.get("recommended_action",""))
            ev = ins.get("evidence") or []
            if ev:
                st.markdown("**Evidências**")
                for e in ev:
                    lbl = e.get("label","-"); val = e.get("value","-")
                    base = e.get("baseline"); unit = e.get("unit","")
                    st.markdown(f"- **{lbl}**: {val}{unit}" + (f" • baseline: {base}" if base is not None else ""))
            meta=[]
            if ins.get("severity"): meta.append(f"Severidade: {ins['severity']}")
            if ins.get("confidence") is not None: meta.append(f"Conf.: {ins['confidence']}")
            if ins.get("timeframe"): meta.append(f"Janela: {ins['timeframe']}")
            if meta: st.caption(" • ".join(meta))

# --------------------------- insights automáticos ---------------------
st.subheader("⚡ Insights automáticos")
if st.button("🔁 Regerar insights automáticos"):
    st.session_state.pop("auto_cards", None)

if "auto_cards" not in st.session_state:
    try:
        with st.spinner("Gerando insights…"):
            st.session_state["auto_cards"] = ai.generate_insights(context, mode="auto", max_cards=6)
    except ai.AIError as e:
        st.session_state["auto_cards"] = []
        st.error(f"Falha na IA: {e}")

cards = st.session_state.get("auto_cards") or []
if not cards:
    st.info("A IA não retornou insights automáticos para o contexto atual.")
else:
    render_cards(cards)

st.markdown("---")

# ------------------------------- prompt livre -------------------------
st.subheader("💬 Pergunte à IA")
user_prompt = st.text_area(
    "Escreva sua pergunta (ex.: 'explore bolas paradas', 'por que caímos no 2º tempo?', 'impacto do 4-3-3?')",
    height=100,
    placeholder="Digite sua pergunta em pt-BR…",
)

if st.button("Perguntar agora") and user_prompt.strip():
    ask_ctx = dict(context)
    ask_ctx["mode"] = "freeform"
    ask_ctx["user_focus"] = user_prompt.strip()
    try:
        with st.spinner("Gerando resposta…"):
            qa = ai.generate_insights(ask_ctx, mode="freeform", max_cards=4)
        if qa:
            st.session_state["qa_cards"] = qa
        else:
            st.info("A IA não retornou resposta para esse prompt.")
    except ai.AIError as e:
        st.error(f"Falha na IA: {e}")

if "qa_cards" in st.session_state:
    st.markdown("### 📋 Resposta da IA")
    render_cards(st.session_state["qa_cards"])
