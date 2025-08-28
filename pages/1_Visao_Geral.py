# pages/1_Visao_Geral.py
import random
import statistics
import streamlit as st
import pandas as pd
from core import api_client
from core.cache import render_cache_controls
render_cache_controls()  # mostra: última atualização + botões

PAGE_TITLE = "📊 Visão Geral"
st.title(PAGE_TITLE)

# ----------------------- filtros / header -----------------------
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

c1, c2, c3 = st.columns([1, 4, 1])
with c1:
    st.image(team["team_logo"], width=72)
with c2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with c3:
    st.image(league["league_logo"], width=72)

st.markdown("---")

# ----------------------- utils auxiliares -----------------------
def _safe(d, *path, default=None):
    """Acesso seguro a d[path[0]]...[path[n]]"""
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d

def _is_finished(fx) -> bool:
    try:
        stt = ((fx.get("fixture") or {}).get("status") or {})
        short = (stt.get("short") or "").upper()
        long = (stt.get("long") or "").lower()
        return short in {"FT", "AET", "PEN"} or "match finished" in long
    except Exception:
        return False

def _fmt(v):
    return "-" if v is None else v

# ----------------------- dados principais -----------------------
stats = api_client.team_statistics(league["league_id"], season, team["team_id"]) or {}

wins_total = _safe(stats, "fixtures", "wins", "total", default=None)
draws_total = _safe(stats, "fixtures", "draws", "total", default=None)
loses_total = _safe(stats, "fixtures", "loses", "total", default=None)

wins_home = _safe(stats, "fixtures", "wins", "home", default=None)
wins_away = _safe(stats, "fixtures", "wins", "away", default=None)
played_home = _safe(stats, "fixtures", "played", "home", default=None)
played_away = _safe(stats, "fixtures", "played", "away", default=None)

gf_total = _safe(stats, "goals", "for", "total", "total", default=None)
ga_total = _safe(stats, "goals", "against", "total", "total", default=None)

clean_total = _safe(stats, "clean_sheet", "total", default=None)

# últimos jogos para heurísticas (sem IA)
fixtures = api_client.fixtures(team["team_id"], season) or []
for m in fixtures:
    try:
        m["_d"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
    except Exception:
        m["_d"] = pd.NaT
fixtures = [fx for fx in fixtures if _is_finished(fx)]
fixtures = sorted(
    fixtures,
    key=lambda x: x.get("_d") if x.get("_d") is not None else pd.Timestamp(0),
    reverse=True,
)
last10 = fixtures[:10]
last5 = fixtures[:5]

def _our_goals(fx):
    gh = (fx.get("goals") or {}).get("home")
    ga = (fx.get("goals") or {}).get("away")
    home = (fx.get("teams") or {}).get("home", {})
    away = (fx.get("teams") or {}).get("away", {})
    is_home = home.get("id") == team["team_id"]
    return (gh, ga, is_home)

gf_series_10, ga_series_10, res_seq_10 = [], [], []
for fx in last10:
    gh, ga, is_home = _our_goals(fx)
    our, opp = (gh, ga) if is_home else (ga, gh)
    gf_series_10.append(our)
    ga_series_10.append(opp)
    res_seq_10.append("V" if our > opp else ("E" if our == opp else "D"))

avg_gf_10 = round(statistics.mean(gf_series_10), 2) if gf_series_10 else 0.0
avg_ga_10 = round(statistics.mean(ga_series_10), 2) if ga_series_10 else 0.0

# minuto de maior incidência (se disponível)
def _top_minute(side: str) -> str:
    """
    side: "for" | "against"
    retorna bucket de minuto com maior 'total' (ex.: "76-90")
    """
    minute_map = _safe(stats, "goals", side, "minute", default={})
    top_label, top_val = None, -1
    for bucket, obj in (minute_map or {}).items():
        try:
            v = obj.get("total")
            if isinstance(v, (int, float)) and v > top_val:
                top_val = v; top_label = bucket
        except Exception:
            pass
    return top_label or "—"

top_for = _top_minute("for")
top_against = _top_minute("against")

# ----------------------- cards de resumo -----------------------
st.markdown("### ⚡ Resumo da temporada")
cA, cB, cC, cD = st.columns(4)
cA.metric("Vitórias", _fmt(wins_total))
cB.metric("Empates", _fmt(draws_total))
cC.metric("Gols Pró", _fmt(gf_total))
cD.metric("Gols Contra", _fmt(ga_total))

cE, cF, cG, cH = st.columns(4)
cE.metric("Derrotas", _fmt(loses_total))
cF.metric("Clean Sheets", _fmt(clean_total))
cG.metric("Vitórias (Casa)", _fmt(wins_home))
cH.metric("Vitórias (Fora)", _fmt(wins_away))

st.caption("Fonte: API-Football — /teams/statistics e /fixtures")

st.markdown("---")

# ----------------------- 5 curiosidades -----------------------
curiosidades_pool = [
    "O **Coritiba Foot Ball Club** foi fundado em 1909 e é o clube de futebol mais antigo do Paraná.",
    "O **Estádio Major Antônio Couto Pereira** é o maior estádio particular do estado, com mais de 37 mil lugares.",
    "O Coritiba foi o **primeiro campeão brasileiro da região sul**, conquistando o título de 1985.",
    "Em 2011, o Coxa emplacou **24 vitórias consecutivas** e entrou para o **Guinness Book**.",
    "O mascote é o **Vovô Coxa**, símbolo de tradição e pioneirismo do clube.",
    "O apelido **'Coxa'** tem origem na colônia alemã e acompanha o clube desde o início do século XX.",
    "O **rivalidade Atletiba** é uma das mais antigas do país, com clássico oficial desde 1924.",
    "A base coxa-branca revelou nomes marcantes como **Alex**, um dos maiores ídolos do clube.",
    "A torcida do Coritiba é conhecida como **Coxa-Branca** e tem presença forte no Couto Pereira.",
    "O primeiro escudo do clube era **verde e branco** com letras entrelaçadas, mantendo a essência até hoje."
]
curiosidades = random.sample(curiosidades_pool, k=5) if len(curiosidades_pool) >= 5 else curiosidades_pool

st.markdown("### 🎲 Curiosidades do Coritiba")
for c in curiosidades:
    st.info(c)

st.markdown("---")

# ----------------------- 5 insights sugeridos -----------------------
# Heurísticas baseadas em stats/fixtures — sem IA.
insights = []

# 1) aproveitamento casa x fora
if isinstance(wins_home, int) and isinstance(played_home, int) and played_home:
    home_rate = wins_home / played_home
else:
    home_rate = None

if isinstance(wins_away, int) and isinstance(played_away, int) and played_away:
    away_rate = wins_away / played_away
else:
    away_rate = None

if home_rate is not None and away_rate is not None:
    if home_rate > away_rate:
        insights.append("**Aproveitamento superior em casa**: taxa de vitórias como mandante é maior do que como visitante.")
    elif away_rate > home_rate:
        insights.append("**Bom desempenho fora**: vitórias como visitante superam o rendimento em casa.")
    else:
        insights.append("**Aproveitamento equilibrado**: desempenho semelhante em casa e fora.")

# 2) média gols últimos 10
insights.append(f"**Média de gols recente**: nos últimos 10 jogos, o Coritiba marcou {avg_gf_10} gol(s)/jogo e sofreu {avg_ga_10} gol(s)/jogo.")

# 3) sequência de forma
if res_seq_10:
    streak = "".join(res_seq_10[:5])
    insights.append(f"**Forma recente (últimos 5)**: {streak} (V=vitória, E=empate, D=derrota).")

# 4) minutos quentes
if top_for != "—":
    insights.append(f"**Janela de maior produção ofensiva**: {top_for}.")
if top_against != "—":
    insights.append(f"**Janela de maior risco defensivo**: {top_against}.")

# 5) clean sheets
if isinstance(clean_total, int):
    insights.append(f"**Solidez defensiva**: {clean_total} clean sheets na temporada.")

# Garante 5 itens (se faltar, completa com mensagens neutras)
while len(insights) < 5:
    insights.append("**Monitoramento contínuo**: acompanhe tendências de gols, posse de bola e eficiência ofensiva a cada rodada.")

st.markdown("### 🤖 Insights sugeridos")
for tip in insights[:5]:
    st.markdown(f"- {tip}")
