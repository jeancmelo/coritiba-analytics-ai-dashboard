import streamlit as st
from core import api_client, ai

st.title("🧠 Insights com IA")

season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

if not league:
    st.error("Liga não detectada para a temporada selecionada.")
    st.stop()

stats = api_client.team_statistics(league["league_id"], season, team["team_id"])
stats = stats[0] if isinstance(stats, list) and stats else stats

context = {"team": team, "season": season, "league": league, "stats": stats}

if st.button("Gerar insights"):
    try:
        insights = ai.generate_insights(context)
    except Exception as e:
        st.error(f"Falha ao gerar insights: {e}")
        st.stop()

    if not insights:
        st.warning("Nenhum insight gerado.")
    else:
        for ins in insights:
            with st.container(border=True):
                st.caption(ins.get("type","insight"))
                st.subheader(ins.get("title","(sem título)"))
                st.write(ins.get("summary",""))
                st.write("**Por que importa:**", ins.get("why_it_matters",""))
                st.write("**Ação sugerida:**", ins.get("recommended_action",""))
                ev = ins.get("evidence") or []
                if ev:
                    st.markdown("**Evidências**")
                    for e in ev:
                        lbl = e.get("label","-"); val = e.get("value","-"); base = e.get("baseline"); unit = e.get("unit","")
                        base_txt = f" | baseline: {base}" if base is not None else ""
                        st.markdown(f"- **{lbl}**: {val}{unit}{base_txt}")
                st.caption(f"Severidade: {ins.get('severity','-')} • Confiança: {ins.get('confidence','-')}")
