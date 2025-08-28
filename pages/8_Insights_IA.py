import streamlit as st
import pandas as pd
from core import api_client, ui_utils, ai

st.title("🧠 Insights com IA — Hub")

# -----------------------------------------------------------------------------
# Filtros básicos
# -----------------------------------------------------------------------------
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

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

st.caption("Central de inteligência: insights automáticos e respostas orientadas por prompt, usando dados da Série B.")

# -----------------------------------------------------------------------------
# 1) Coleta de contexto (sem exibir objetos na tela)
# -----------------------------------------------------------------------------
with st.expander("🔄 Coletando dados de contexto", expanded=False):
    st.caption("O contexto inclui estatísticas agregadas da temporada, últimos jogos, standings e próximo adversário.")

# Estatísticas de temporada
stats = api_client.team_statistics(league["league_id"], season, team["team_id"])
stats = stats[0] if isinstance(stats, list) and stats else stats

# Standings (posição atual)
std = api_client.standings(league["league_id"], season)
rank = None
try:
    table = std[0]["league"]["standings"][0]
    for row in table:
        if row["team"]["id"] == team["team_id"]:
            rank = row["rank"]
            break
except Exception:
    pass

# Últimos jogos (até 10)
fixtures = api_client.fixtures(team["team_id"], season) or []
for m in fixtures:
    m["_d"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
fixtures = sorted(fixtures, key=lambda x: x.get("_d") or pd.Timestamp(0), reverse=True)

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
        "is_home": is_home,
        "round": fx["league"].get("round"),
    }

# Monta o contexto
context = {
    "season": season,
    "league": league,
    "team": team,
    "standings_rank": rank,
    "stats": stats,
    "last_games": last_games,
    "next_fixture": next_context,
}

if not stats:
    st.warning("Sem estatísticas de temporada na API; a qualidade dos insights pode ficar limitada.")

# -----------------------------------------------------------------------------
# 2) Insights automáticos (geração 1x por sessão, com botão de regerar)
# -----------------------------------------------------------------------------
st.subheader("⚡ Insights automáticos")

if "auto_insights_done" not in st.session_state:
    st.session_state["auto_insights"] = []
    try:
        with st.spinner("Gerando insights automáticos…"):
            st.session_state["auto_insights"] = ai.generate_insights(context) or []
    except Exception as e:
        st.error(f"Falha ao gerar insights automáticos: {e}")
    st.session_state["auto_insights_done"] = True

if st.button("🔁 Regerar insights automáticos"):
    try:
        with st.spinner("Gerando…"):
            st.session_state["auto_insights"] = ai.generate_insights(context) or []
    except Exception as e:
        st.error(f"Falha ao gerar insights: {e}")

auto_insights = st.session_state.get("auto_insights") or []
if not auto_insights:
    st.info("A IA não retornou insights automáticos para o contexto atual.")
else:
    for ins in auto_insights:
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

# -----------------------------------------------------------------------------
# 3) Pergunte à IA (prompt)
# -----------------------------------------------------------------------------
st.subheader("💬 Pergunte à IA")
user_prompt = st.text_area(
    "Escreva sua pergunta ou foque em algo (ex.: 'explore bolas paradas', 'por que caímos no 2º tempo?', 'qual o impacto do 4-3-3?')",
    placeholder="Digite sua pergunta em pt-BR…",
    height=100,
)
col_p1, col_p2 = st.columns([1,4])
with col_p1:
    ask_clicked = st.button("Perguntar agora")

if ask_clicked and user_prompt.strip():
    ask_ctx = dict(context)  # shallow copy
    # dica para o motor de IA: foco explícito do usuário
    ask_ctx["user_focus"] = user_prompt.strip()
    ask_ctx["mode"] = "freeform"

    try:
        with st.spinner("Gerando resposta…"):
            resp_cards = ai.generate_insights(ask_ctx) or []
    except Exception as e:
        resp_cards = []
        st.error(f"Falha ao consultar a IA: {e}")

    if not resp_cards:
        st.info("A IA não retornou resposta para esse prompt.")
    else:
        # guarda para export
        st.session_state["qa_export"] = {"prompt": user_prompt.strip(), "insights": resp_cards}
        st.markdown("### 📋 Resposta da IA")
        for ins in resp_cards:
            with st.container(border=True):
                st.caption(ins.get("type", "qa"))
                st.subheader(ins.get("title", "(resposta)"))
                st.write(ins.get("summary", ""))

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

# -----------------------------------------------------------------------------
# 4) Exportações
# -----------------------------------------------------------------------------
st.subheader("⬇️ Exportar")

# export automáticos
if auto_insights:
    import json
    payload = json.dumps({"insights": auto_insights}, ensure_ascii=False, indent=2)
    st.download_button(
        label="Baixar insights automáticos (JSON)",
        data=payload.encode("utf-8"),
        file_name=f"insights_auto_coritiba_{season}.json",
        mime="application/json",
        use_container_width=True
    )
else:
    st.caption("Gere os insights automáticos para habilitar o download.")

# export Q/A
if "qa_export" in st.session_state:
    import json
    qap = json.dumps(st.session_state["qa_export"], ensure_ascii=False, indent=2)
    st.download_button(
        label="Baixar resposta do prompt (JSON)",
        data=qap.encode("utf-8"),
        file_name=f"insights_prompt_coritiba_{season}.json",
        mime="application/json",
        use_container_width=True
    )
else:
    st.caption("Envie uma pergunta para habilitar o download da resposta.")
