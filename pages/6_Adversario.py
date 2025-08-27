import streamlit as st
import pandas as pd
from core import api_client, ui_utils, ai

st.title("🔎 Scouting do Adversário — Prévia do próximo jogo")

# Filtro global
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

# Time e liga (fixos via api_client)
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

st.caption("Análise do próximo adversário com estatísticas recentes e prévia com IA.")

# Próximo jogo do Coxa
fixtures = api_client.fixtures(team["team_id"], season, next=1)
if not fixtures:
    st.info("Nenhum próximo jogo encontrado.")
    st.stop()

fx = fixtures[0]
fixture = fx["fixture"]
home = fx["teams"]["home"]
away = fx["teams"]["away"]
is_home = home["id"] == team["team_id"]
opponent = away if is_home else home

st.subheader(f"📅 Próximo adversário: {opponent['name']}")
ui_utils.load_image(opponent["logo"], size=72, alt=opponent["name"])
st.caption(f"Data: {fixture.get('date')} • Rodada: {fx['league'].get('round','-')}")

# Estatísticas do adversário (Série B)
opp_stats = api_client.team_statistics(league["league_id"], season, opponent["id"])
opp_stats = opp_stats[0] if isinstance(opp_stats, list) and opp_stats else opp_stats
if not opp_stats:
    st.warning("Sem estatísticas disponíveis para o adversário.")
    st.stop()

# Forma recente do adversário (últimos 5)
opp_fx = api_client.fixtures(opponent["id"], season)
last5 = sorted(opp_fx, key=lambda x: x["fixture"]["date"], reverse=True)[:5]
rows = []
for m in last5:
    fh, fa = m["teams"]["home"], m["teams"]["away"]
    gh, ga = m["goals"]["home"], m["goals"]["away"]
    # resultado do ponto de vista do adversário
    if fa["id"] == opponent["id"]:
        # adversário estava fora
        if gh == ga:
            res = "E"
        else:
            res = "V" if fa.get("winner") else "D"
        adv_name = fh["name"]
    else:
        # adversário estava em casa
        if gh == ga:
            res = "E"
        else:
            res = "V" if fh.get("winner") else "D"
        adv_name = fa["name"]
    rows.append({
        "Data": m["fixture"]["date"][:10],
        "Adversário": adv_name,
        "Placar": f"{gh}-{ga}",
        "Res": res
    })
df_form = pd.DataFrame(rows)

st.markdown("### 📊 Forma recente (últimos 5 jogos)")
st.dataframe(df_form, use_container_width=True, hide_index=True)

# KPIs principais do adversário
st.markdown("### 🔢 KPIs principais do adversário (Série B)")
g = opp_stats.get("goals", {})
shots = opp_stats.get("shots", {})
passes = opp_stats.get("passes", {})
c1, c2, c3, c4 = st.columns(4)
c1.metric("Gols Pró (temp.)", g.get("for", {}).get("total", {}).get("total", 0))
c2.metric("Gols Contra (temp.)", g.get("against", {}).get("total", {}).get("total", 0))
c3.metric("Chutes/Jogo", shots.get("total", {}).get("average", "-"))
c4.metric("Passes certos %", passes.get("accuracy", {}).get("percentage", "-"))

# Prévia IA do confronto (usa generate_insights com contexto do adversário)
st.markdown("### 🤖 Prévia IA do confronto")
context = {
    "season": season,
    "league": league,
    "our_team": team,
    "opponent": {"id": opponent["id"], "name": opponent["name"]},
    "opponent_stats": opp_stats,
    "last5": rows,
    "fixture": {"id": fixture["id"], "date": fixture.get("date")}
}
if st.button("Gerar prévia IA"):
    try:
        insights = ai.generate_insights(context)
        if not insights:
            st.info("A IA não retornou insights.")
        else:
            for ins in insights:
                with st.container(border=True):
                    st.caption(ins.get("type", "pre_match"))
                    st.subheader(ins.get("title", "(sem título)"))
                    st.write(ins.get("summary", ""))
                    st.write("**Por que importa:**", ins.get("why_it_matters", ""))
                    st.write("**Ação sugerida:**", ins.get("recommended_action", ""))
                    ev = ins.get("evidence") or []
                    if ev:
                        st.markdown("**Evidências**")
                        for e in ev:
                            lbl = e.get("label","-"); val = e.get("value","-"); base = e.get("baseline"); unit = e.get("unit","")
                            base_txt = f" | baseline: {base}" if base is not None else ""
                            st.markdown(f"- **{lbl}**: {val}{unit}{base_txt}")
                    st.caption(f"Severidade: {ins.get('severity','-')} • Confiança: {ins.get('confidence','-')}")
    except Exception as e:
        st.error(f"Falha ao gerar prévia IA: {e}")

st.caption("Fonte: API-Football — /fixtures, /teams/statistics (liga=72).")
