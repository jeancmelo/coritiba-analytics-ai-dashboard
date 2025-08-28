import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from core import api_client, ui_utils

st.title("📈 Tendências & Alertas — Série B")

# ---------------------------------------------------------------------
# Filtros e cabeçalho
# ---------------------------------------------------------------------
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
last_n = st.sidebar.slider("Considerar últimos N jogos (finalizados)", 5, 38, 12, 1)

team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption("Análise de tendências usando **somente partidas finalizadas**. As médias móveis ignoram buracos quando uma estatística não está disponível no jogo.")

# ---------------------------------------------------------------------
# 1) Coleta — só jogos FINALIZADOS
# ---------------------------------------------------------------------
ALL_FINALS = {"FT", "AET", "PEN"}  # finalizados
OUR_ID = team["team_id"]

def _is_final(fx) -> bool:
    return (fx["fixture"].get("status", {}).get("short") or "") in ALL_FINALS

fixtures = api_client.fixtures(OUR_ID, season) or []
if not fixtures:
    st.info("Nenhuma partida retornada para esta temporada.")
    st.stop()

for m in fixtures:
    m["_date"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
# ordena asc para calcular séries no tempo; filtra finais; pega últimos N
finals = [f for f in sorted(fixtures, key=lambda x: x.get("_date") or pd.Timestamp(0)) if _is_final(f)]
finals = finals[-last_n:]

if not finals:
    st.info("Não há partidas finalizadas suficientes para a janela selecionada.")
    st.stop()

def _stat_value(items, keys):
    """Busca valor numérico tentando várias chaves; normaliza %."""
    for k in keys:
        for it in items:
            if (it.get("type") or "").lower() == k.lower():
                v = it.get("value")
                if v is None:
                    return None
                if isinstance(v, str) and "%" in v:
                    try:
                        return float(v.replace("%", "").strip())
                    except Exception:
                        return None
                try:
                    return float(v)
                except Exception:
                    try:
                        return int(v)
                    except Exception:
                        return None
    return None

rows = []
progress = st.progress(0)
for i, fx in enumerate(finals, start=1):
    progress.progress(i / len(finals))

    f = fx["fixture"]
    h, a = fx["teams"]["home"], fx["teams"]["away"]
    our_home = (h["id"] == OUR_ID)

    gf = fx["goals"]["home"] if our_home else fx["goals"]["away"]
    ga = fx["goals"]["away"] if our_home else fx["goals"]["home"]

    # estatísticas do jogo (podem faltar em alguns jogos)
    try:
        blocks = api_client.fixture_statistics(f["id"])
    except Exception:
        blocks = []

    my_items, opp_items = [], []
    for b in (blocks or []):
        tid = (b.get("team") or {}).get("id")
        if tid == OUR_ID:
            my_items = b.get("statistics") or []
        else:
            opp_items = b.get("statistics") or []

    shots_total = _stat_value(my_items, ["Total Shots", "Shots Total", "Shots"])
    shots_on = _stat_value(my_items, ["Shots on Goal", "Shots on Target", "SOT"])
    poss = _stat_value(my_items, ["Ball Possession", "Possession"])
    corners_for = _stat_value(my_items, ["Corner Kicks", "Corners"])
    corners_against = _stat_value(opp_items, ["Corner Kicks", "Corners"])
    fouls_for = _stat_value(my_items, ["Fouls"])
    fouls_against = _stat_value(opp_items, ["Fouls"])
    yc_for = _stat_value(my_items, ["Yellow Cards"])
    rc_for = _stat_value(my_items, ["Red Cards"])

    rows.append({
        "date": pd.to_datetime(f["date"], errors="coerce"),
        "fixture_id": f["id"],
        "GF": gf, "GA": ga,
        "SOT": shots_on, "Shots": shots_total, "Poss%": poss,
        "Corners_for": corners_for, "Corners_against": corners_against,
        "Fouls_for": fouls_for, "Fouls_against": fouls_against,
        "YC_for": yc_for, "RC_for": rc_for,
    })

progress.empty()
df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

# ---------------------------------------------------------------------
# 2) Tendências com janelas móveis (5 e 10) — ignorando buracos
# ---------------------------------------------------------------------
WINDOWS = [5, 10]
METRICS = [
    ("GF", "Gols Pró (média)"),
    ("GA", "Gols Contra (média)"),
    ("SOT", "Chutes no alvo (média)"),
    ("Shots", "Chutes totais (média)"),
    ("Poss%", "Posse (%) (média)"),
    ("Corners_for", "Escanteios a favor (média)"),
    ("Corners_against", "Escanteios contra (média)"),
    ("YC_for", "Amarelos (CFC) (média)"),
    ("RC_for", "Vermelhos (CFC) (média)"),
]

def rolling_current(series: pd.Series, window: int):
    """Média dos últimos 'window' valores válidos (ignora NaN)."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return float(s.tail(min(window, len(s))).mean())

def rolling_series(series: pd.Series, window: int):
    """Série de médias móveis usando somente valores válidos até cada ponto."""
    out = []
    history = []
    for v in series:
        history.append(v)
        h = pd.Series(pd.to_numeric(history, errors="coerce")).dropna()
        out.append(float(h.tail(min(window, len(h))).mean()) if not h.empty else np.nan)
    return out

season_means = {}
for key, _ in METRICS:
    season_means[key] = pd.to_numeric(df[key], errors="coerce").dropna().mean()

for key, _ in METRICS:
    df[f"{key}_roll5"] = rolling_series(df[key], 5)
    df[f"{key}_roll10"] = rolling_series(df[key], 10)

def classify_delta(delta_pct: float) -> str:
    if delta_pct is None or np.isnan(delta_pct):
        return "low"
    absd = abs(delta_pct)
    if absd >= 30: return "high"
    if absd >= 15: return "medium"
    return "low"

def arrow(delta: float) -> str:
    if delta is None or np.isnan(delta): return "↔"
    return "▲" if delta > 0 else ("▼" if delta < 0 else "↔")

def conf(n_games: int, window: int) -> float:
    return round(min(n_games, window) / window, 2)

st.divider()
st.subheader("🔔 Tendências detectadas (janelas 5 e 10 jogos)")

n_games = len(df)
cards = []
for col, label in METRICS:
    current5 = rolling_current(df[col], 5)
    current10 = rolling_current(df[col], 10)
    base = season_means.get(col, np.nan)

    d5 = ((current5 - base) / base * 100.0) if (pd.notna(base) and base != 0 and current5 is not None) else None
    d10 = ((current10 - base) / base * 100.0) if (pd.notna(base) and base != 0 and current10 is not None) else None

    cards.append({
        "metric": label, "window": 5,
        "value": None if current5 is None else round(current5, 2),
        "delta_pct": None if d5 is None else round(d5, 1),
        "severity": classify_delta(d5),
        "confidence": conf(n_games, 5),
        "arrow": arrow(d5),
    })
    cards.append({
        "metric": label, "window": 10,
        "value": None if current10 is None else round(current10, 2),
        "delta_pct": None if d10 is None else round(d10, 1),
        "severity": classify_delta(d10),
        "confidence": conf(n_games, 10),
        "arrow": arrow(d10),
    })

for c in cards:
    with st.container(border=True):
        vtxt = "—" if c["value"] is None else str(c["value"])
        dtxt = "—" if c["delta_pct"] is None else f"{c['delta_pct']}%"
        sev_emoji = {"high": "🟥", "medium": "🟨", "low": "🟩"}[c["severity"]]
        st.markdown(f"**{c['metric']}** — janela **{c['window']}** jogos")
        st.write(f"Valor atual: **{vtxt}**  •  Δ vs média: **{c['arrow']} {dtxt}**  •  Severidade: {sev_emoji} **{c['severity']}**  •  Confiança: **{c['confidence']}**")

st.divider()

# ---------------------------------------------------------------------
# 3) Gráfico da métrica escolhida (fix: evitar conflito do melt)
# ---------------------------------------------------------------------
st.subheader("📉 Séries temporais com janelas móveis")

label2col = {m[1]: m[0] for m in METRICS}
plot_metric = st.selectbox("Escolha uma métrica para visualizar", list(label2col.keys()), index=0)
col = label2col[plot_metric]

# seleciona e renomeia colunas para nomes únicos
df_plot = df[["date", col, f"{col}_roll5", f"{col}_roll10"]].copy()
df_plot = df_plot.rename(columns={
    col: "Observado",
    f"{col}_roll5": "Média (5j)",
    f"{col}_roll10": "Média (10j)",
})

# usa só as séries que têm pelo menos 1 valor não-nulo
value_vars = [c for c in ["Observado", "Média (5j)", "Média (10j)"] if df_plot[c].notna().any()]

if not value_vars:
    st.info("Não há dados suficientes dessa métrica para plotar.")
else:
    df_melt = df_plot.melt(
        id_vars="date",
        value_vars=value_vars,
        var_name="Série",
        value_name="Valor"  # agora não conflita com nenhuma coluna existente
    )
    fig = px.line(df_melt, x="date", y="Valor", color="Série")
    fig.update_layout(xaxis_title="Data", yaxis_title=plot_metric)
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------
# 4) Tabela-base (debug opcional)
# ---------------------------------------------------------------------
with st.expander("Ver tabela base (debug)"):
    st.dataframe(df, use_container_width=True, hide_index=True)

st.caption("Notas: Só jogos finalizados entram no cálculo. Quando uma estatística não existe para um jogo, a janela usa os valores válidos mais recentes (ignorando buracos).")
