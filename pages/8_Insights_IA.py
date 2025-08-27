import streamlit as st
import pandas as pd
from core import api_client, ui_utils, ai

st.title("🧠 Insights com IA — Hub")

# Filtros
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

# Time/Liga fixos (IDs no api_client)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

# Header com logos
h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption("Central de inteligência: gere insights táticos, tendências e recomendações acionáveis a partir dos dados da Série B.")

# ----------------------------
# Coleta de contexto
# ----------------------------
st.markdown("### 🔄 Coletando dados de contexto")

# Estatísticas de temporada
stats = api_client.team_statistics(league["league_id"], season, team["team_id"])
stats = stats[0] if isinstance(stats, list) and stats else stats

# Standings (posição atual)
std = api_client.standings(league["league_id"], season)
table = None
pos_coxa = None
if std:
    try:
        table = std[0]["league"]["standings"][0]
        for row in table:
            if row["team"]["id"] == team["team_id"]:
                pos_coxa = row["rank"]
                break
    except Exception:
        table = None

# Últimos jogos (até 10)
fixtures = api_client.fixtures(team["team_id"], season)
for m in fixtures:
    m["_date"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
fixtures = sorted(fixtures, key=lambda x: x.get("_date") or pd.Timestamp(0), reverse=True)
last_games = []
for fx in fixtures[:10]:
    gh, ga = fx["goals"]["home"], fx["goals"]["away"]
    home = fx["teams"]["home"]; away = fx["teams"]["away"]
    is_home = (home["id"] == team["team_id"])
    our_goals = gh if is_home else ga
    opp_goals = ga if is_home else gh
    res = "E"
    if our_goals is not None and opp_goals is not None:
        if our_goals > opp_goals: res = "V"
        elif our_goals < opp_goals: res = "D"
    last_games.append({
        "date": str(fx["fixture"]["date"]),
        "home": home["name"], "away": away["name"],
        "score": f"{gh}-{ga}",
        "res": res
    })

# Próximo adversário
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
    }

# Monta o contexto para a IA
context = {
    "season": season,
    "league": league,
    "team": team,
    "standings_rank": pos_coxa,
    "stats": stats,
    "last_games": last_games,
    "next_fixture": next_context,
}

st.success("Contexto carregado.") if stats else st.warning("Sem estatísticas de temporada; insights podem ficar limitados.")

# Foco opcional para a IA
st.markdown("### 🎯 Foco opcional")
focus = st.text_area(
    "Opcional: diga à IA o que priorizar (ex.: 'pressão alta no 2º tempo', 'explorar bolas paradas', 'minutagem baixa do lateral direito').",
    placeholder="Descreva seu foco (em pt-BR)…",
    height=80
)
if focus:
    context["user_focus"] = focus

# ----------------------------
# Geração de Insights
# ----------------------------
st.markdown("### 🤖 Gerar insights")
colg1, colg2 = st.columns([1,2])
with colg1:
    temp = st.slider("Criatividade (temperature)", 0.0, 1.0, 0.2, 0.1)
with colg2:
    st.caption("Valores mais baixos deixam a IA mais objetiva e determinística.")

if st.button("Gerar insights IA agora"):
    with st.spinner("Gerando…"):
        insights = ai.generate_insights(context)
    if not insights:
        st.info("A IA não retornou insights. Verifique se há dados da temporada/partidas.")
    else:
        # Guarda para exportação
        st.session_state["insights_json"] = {"insights": insights}

        st.markdown("### 📋 Cartões de Insight")
        for ins in insights:
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
                        base_txt = f" | baseline: {base}" if base is not None else ""
                        st.markdown(f"- **{lbl}**: {val}{unit}{base_txt}")

                meta = []
                if ins.get("severity"): meta.append(f"Severidade: {ins['severity']}")
                if ins.get("confidence") is not None: meta.append(f"Conf.: {ins['confidence']}")
                if ins.get("timeframe"): meta.append(f"Janela: {ins['timeframe']}")
                if meta:
                    st.caption(" • ".join(meta))

# ----------------------------
# Exportação
# ----------------------------
st.markdown("### ⬇️ Exportar")
if "insights_json" in st.session_state:
    import json
    payload = json.dumps(st.session_state["insights_json"], ensure_ascii=False, indent=2)
    st.download_button(
        label="Baixar insights (JSON)",
        data=payload.encode("utf-8"),
        file_name=f"insights_coritiba_{season}.json",
        mime="application/json"
    )
else:
    st.caption("Gere os insights para habilitar o download.")
