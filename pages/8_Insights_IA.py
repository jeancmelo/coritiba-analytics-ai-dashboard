# pages/10_Insights_IA.py
import json
import streamlit as st
from core import api_client, ui_utils, ai

st.title("🧠 Insights com IA — Hub")

# ---------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption("Central de inteligência: insights automáticos e respostas orientadas por prompt, usando dados da Série B.")

# ---------------------------------------------------------------------
# Coleta de contexto (ENXUTO)
# ---------------------------------------------------------------------
with st.expander("📦 Coletando dados de contexto", expanded=False):
    st.caption("O contexto inclui estatísticas agregadas da temporada, últimos jogos, standings e próximo adversário.")

# stats
stats = api_client.team_statistics(league["league_id"], season, team["team_id"])
stats = stats[0] if isinstance(stats, list) and stats else stats

# standings (posição)
rank = None
try:
    std = api_client.standings(league["league_id"], season)
    table = std[0]["league"]["standings"][0]
    for row in table:
        if row["team"]["id"] == team["team_id"]:
            rank = row["rank"]
            break
except Exception:
    pass

# últimos jogos (até 10)
fixtures = api_client.fixtures(team["team_id"], season) or []
for m in fixtures:
    m["_d"] = ui_utils.parse_date(m["fixture"]["date"])
fixtures = sorted(fixtures, key=lambda x: x.get("_d") or ui_utils.parse_date("1970-01-01"), reverse=True)

last_games = []
for fx in fixtures[:10]:
    gh, ga = fx["goals"]["home"], fx["goals"]["away"]
    home = fx["teams"]["home"]; away = fx["teams"]["away"]
    is_home = (home["id"] == team["team_id"])
    our_goals = gh if is_home else ga
    opp_goals = ga if is_home else gh
    res = "—"
    if our_goals is not None and opp_goals is not None:
        res = "V" if our_goals > opp_goals else ("D" if our_goals < opp_goals else "E")
    last_games.append({
        "date": str(fx["fixture"]["date"])[:19],
        "home": home["name"], "away": away["name"],
        "score": f"{gh}-{ga}",
        "res": res
    })

# próximo adversário
next_fx = api_client.fixtures(team["team_id"], season, next=1)
next_context = None
if next_fx:
    fx = next_fx[0]
    home = fx["teams"]["home"]; away = fx["teams"]["away"]
    is_home = (home["id"] == team["team_id"])
    opp = away if is_home else home
    next_context = {
        "fixture_id": fx["fixture"]["id"],
        "date": fx["fixture"].get("date"),
        "opponent": {"id": opp["id"], "name": opp["name"], "logo": opp["logo"]},
        "is_home": is_home,
        "round": fx["league"].get("round"),
    }

context = {
    "season": season,
    "league": league,
    "team": team,
    "standings_rank": rank,
    "stats": stats,
    "last_games": last_games,
    "next_fixture": next_context,
}

# ---------------------------------------------------------------------
# Debug curto do contexto e saúde da IA
# ---------------------------------------------------------------------
with st.expander("🔧 Debug da IA", expanded=False):
    st.code(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in context.items()}, ensure_ascii=False, indent=2))
    st.caption(f"Modelo: {ai._DEFAULT_MODEL} • Tem OPENAI_API_KEY: {'✅' if st.secrets.get('OPENAI_API_KEY') or st.session_state.get('OPENAI_API_KEY') or True else '❓'}")

# ---------------------------------------------------------------------
# Insights automáticos
# ---------------------------------------------------------------------
st.subheader("⚡ Insights automáticos")

def _render_cards(cards):
    for ins in cards:
        with st.container(border=True):
            st.caption(ins.get("type", "insight"))
            st.subheader(ins.get("title", "(sem título)"))
            st.write(ins.get("summary", ""))

            colx, coly = st.columns(2)
            with colx:
                st.write("**Por que importa**")
                st.write(ins.get("why_it_matters", ""))
            with coly:
                st.write("**Ação sugerida**")
                st.write(ins.get("recommended_action", ""))

            ev = ins.get("evidence") or []
            if ev:
                st.markdown("**Evidências**")
                for e in ev:
                    lbl = e.get("label","-")
                    val = e.get("value","-")
                    base = e.get("baseline")
                    unit = e.get("unit","")
                    base_txt = f" • baseline: {base}" if base is not None else ""
                    st.markdown(f"- **{lbl}**: {val}{unit}{base_txt}")

            meta = []
            if ins.get("severity"): meta.append(f"Severidade: {ins['severity']}")
            if ins.get("confidence") is not None: meta.append(f"Conf.: {ins['confidence']}")
            if ins.get("timeframe"): meta.append(f"Janela: {ins['timeframe']}")
            if meta:
                st.caption(" • ".join(meta))

if st.button("🔁 Regerar insights automáticos"):
    st.session_state.pop("auto_cards", None)

if "auto_cards" not in st.session_state:
    try:
        with st.spinner("Gerando insights automáticos…"):
            st.session_state["auto_cards"] = ai.generate_insights(context, mode="auto")
    except ai.AIError as e:
        st.session_state["auto_cards"] = []
        st.error(f"Falha na IA: {e}")

auto_cards = st.session_state.get("auto_cards") or []
if not auto_cards:
    st.info("A IA não retornou insights automáticos para o contexto atual.")
else:
    _render_cards(auto_cards)

st.markdown("---")

# ---------------------------------------------------------------------
# Prompt livre
# ---------------------------------------------------------------------
st.subheader("💬 Pergunte à IA")
user_prompt = st.text_area(
    "Escreva sua pergunta ou foque em algo (ex.: 'explore bolas paradas', 'por que caímos no 2º tempo?', 'qual o impacto do 4-3-3?')",
    placeholder="Digite sua pergunta em pt-BR…",
    height=100,
)
if st.button("Perguntar agora") and user_prompt.strip():
    ask_ctx = dict(context)
    ask_ctx["user_focus"] = user_prompt.strip()
    ask_ctx["mode"] = "freeform"
    try:
        with st.spinner("Gerando resposta…"):
            qa_cards = ai.generate_insights(ask_ctx, mode="freeform", max_cards=4)
        if not qa_cards:
            st.info("A IA não retornou resposta para esse prompt.")
        else:
            st.session_state["qa_cards"] = qa_cards
    except ai.AIError as e:
        st.error(f"Falha na IA: {e}")

if "qa_cards" in st.session_state:
    st.markdown("### 📋 Resposta da IA")
    _render_cards(st.session_state["qa_cards"])
