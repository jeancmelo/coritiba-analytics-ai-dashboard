import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from core import api_client, ui_utils

st.title("📈 Tendências & Alertas — Série B")

# filtros globais
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)

# time e liga (fixos via api_client)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

# header com logos
h1, h2, h3 = st.columns([1, 4, 1])
with h1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with h2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with h3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

st.caption("Detecção de tendências com janelas móveis (5 e 10 jogos) usando estatísticas por partida.")

# -----------------------------------------------------------------------------
# 1) Coleta de dados por partida
# -----------------------------------------------------------------------------
fixtures = api_client.fixtures(team["team_id"], season)
if not fixtures:
    st.info("Nenhuma partida encontrada para a temporada selecionada.")
    st.stop()

# ordena por data
for m in fixtures:
    m["_date"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
fixtures = sorted(fixtures, key=lambda x: x.get("_date") or pd.Timestamp(0))

def _stat_value(items, keys):
    """Procura o primeiro tipo válido em 'keys' dentro de items e normaliza para número."""
    for k in keys:
        for it in items:
            if it.get("type", "").lower() == k.lower():
                val = it.get("value")
                if val is None:
                    return None
                # normaliza percentuais "55%" -> 55.0
                if isinstance(val, str) and "%" in val:
                    try:
                        return float(val.replace("%", "").strip())
                    except Exception:
                        return None
                # às vezes vem "None" como string
                try:
                    return float(val)
                except Exception:
                    try:
                        return int(val)
                    except Exception:
                        return None
    return None

rows = []
progress = st.progress(0)
total = len(fixtures)

OUR_ID = team["team_id"]

for i, fx in enumerate(fixtures, start=1):
    progress.progress(i / total)

    f = fx["fixture"]
    h = fx["teams"]["home"]
    a = fx["teams"]["away"]
    our_home = h["id"] == OUR_ID
    opp = a if our_home else h

    goals_for = fx["goals"]["home"] if our_home else fx["goals"]["away"]
    goals_against = fx["goals"]["away"] if our_home else fx["goals"]["home"]

    # coleta estatísticas do fixture
    try:
        blocks = api_client.fixture_statistics(f["id"])
    except Exception:
        blocks = []

    # separa nosso bloco vs adversário
    my_block = None
    opp_block = None
    for b in blocks or []:
        tid = (b.get("team") or {}).get("id")
        if tid == OUR_ID:
            my_block = b
        else:
            opp_block = b

    my_items = (my_block or {}).get("statistics") or []
    opp_items = (opp_block or {}).get("statistics") or []

    # chaves comuns da API-Football
    shots_total = _stat_value(my_items, ["Total Shots", "Shots Total", "Shots"])
    shots_on = _stat_value(my_items, ["Shots on Goal", "Shots on Target", "SOT"])
    poss = _stat_value(my_items, ["Ball Possession", "Possession"])
    corners_for = _stat_value(my_items, ["Corner Kicks", "Corners"])
    fouls_for = _stat_value(my_items, ["Fouls"])
    yc_for = _stat_value(my_items, ["Yellow Cards"])
    rc_for = _stat_value(my_items, ["Red Cards"])

    # defensivo (contra)
    corners_against = _stat_value(opp_items, ["Corner Kicks", "Corners"])
    fouls_against = _stat_value(opp_items, ["Fouls"])
    yc_against = _stat_value(opp_items, ["Yellow Cards"])
    rc_against = _stat_value(opp_items, ["Red Cards"])

    rows.append({
        "date": pd.to_datetime(f["date"], errors="coerce"),
        "fixture_id": f["id"],
        "opponent": opp["name"],
        "H/A": "H" if our_home else "A",
        "GF": goals_for,
        "GA": goals_against,
        "SOT": shots_on,
        "Shots": shots_total,
        "Poss%": poss,
        "Corners_for": corners_for,
        "Corners_against": corners_against,
        "Fouls_for": fouls_for,
        "Fouls_against": fouls_against,
        "YC_for": yc_for,
        "RC_for": rc_for,
        "YC_against": yc_against,
        "RC_against": rc_against,
    })

progress.empty()
df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

if df.empty:
    st.info("Sem estatísticas suficientes nas partidas para calcular tendências.")
    st.stop()

# -----------------------------------------------------------------------------
# 2) Cálculos de tendência (rolling 5 e 10)
# -----------------------------------------------------------------------------
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

for col, _ in METRICS:
    df[f"{col}_roll5"] = df[col].rolling(WINDOWS[0], min_periods=1).mean()
    df[f"{col}_roll10"] = df[col].rolling(WINDOWS[1], min_periods=1).mean()

season_means = {m[0]: df[m[0]].mean(skipna=True) for m in METRICS}

def classify_delta(delta_pct: float) -> str:
    """Define severidade por % de variação."""
    if delta_pct is None or np.isnan(delta_pct):
        return "low"
    absd = abs(delta_pct)
    if absd >= 30:
        return "high"
    if absd >= 15:
        return "medium"
    return "low"

def arrow(delta: float) -> str:
    if delta is None or np.isnan(delta):
        return "↔"
    return "▲" if delta > 0 else ("▼" if delta < 0 else "↔")

def conf(n_games: int, window: int) -> float:
    """Confiança ~ cobertura da janela."""
    n = max(min(n_games, window), 0)
    return round(n / window, 2)

st.divider()
st.subheader("🔔 Tendências detectadas (janelas 5 e 10 jogos)")

# último ponto (mais recente)
last_idx = len(df) - 1
n_games = last_idx + 1

cards = []
for col, label in METRICS:
    current5 = df.loc[last_idx, f"{col}_roll5"]
    current10 = df.loc[last_idx, f"{col}_roll10"]
    base = season_means.get(col, np.nan)

    # deltas percentuais vs média da temporada
    d5 = ((current5 - base) / base * 100.0) if pd.notna(base) and base != 0 else np.nan
    d10 = ((current10 - base) / base * 100.0) if pd.notna(base) and base != 0 else np.nan

    sev5 = classify_delta(d5)
    sev10 = classify_delta(d10)

    cards.append({
        "metric": label,
        "window": 5,
        "value": round(current5, 2) if pd.notna(current5) else None,
        "delta_pct": round(d5, 1) if pd.notna(d5) else None,
        "severity": sev5,
        "confidence": conf(n_games, 5),
        "arrow": arrow(d5),
    })
    cards.append({
        "metric": label,
        "window": 10,
        "value": round(current10, 2) if pd.notna(current10) else None,
        "delta_pct": round(d10, 1) if pd.notna(d10) else None,
        "severity": sev10,
        "confidence": conf(n_games, 10),
        "arrow": arrow(d10),
    })

# Render cards
for c in cards:
    with st.container(border=True):
        st.markdown(f"**{c['metric']}** — janela **{c['window']}** jogos")
        vtxt = "—" if c["value"] is None else str(c["value"])
        dtxt = "—" if c["delta_pct"] is None else f"{c['delta_pct']}%"
        sev = c["severity"]
        sev_emoji = "🟥" if sev == "high" else ("🟨" if sev == "medium" else "🟩")
        st.write(f"Valor atual: **{vtxt}**  •  Δ vs média: **{c['arrow']} {dtxt}**  •  Severidade: {sev_emoji} **{sev}**  •  Confiança: **{c['confidence']}**")

st.divider()

# -----------------------------------------------------------------------------
# 3) Gráficos de tendência (rolling)
# -----------------------------------------------------------------------------
st.subheader("📉 Séries temporais com janelas móveis")

plot_metric = st.selectbox(
    "Escolha uma métrica para visualizar",
    options=[m[1] for m in METRICS],
    index=0
)
# map label -> col
label2col = {m[1]: m[0] for m in METRICS}
col = label2col[plot_metric]

df_plot = df[["date", col, f"{col}_roll5", f"{col}_roll10"]].copy()
df_plot = df_plot.rename(columns={
    col: "Valor",
    f"{col}_roll5": "Média (5j)",
    f"{col}_roll10": "Média (10j)"
})

df_melt = df_plot.melt(id_vars="date", var_name="Série", value_name="Valor")
fig = px.line(df_melt, x="date", y="Valor", color="Série")
fig.update_layout(xaxis_title="Data", yaxis_title=plot_metric)
st.plotly_chart(fig, use_container_width=True)

st.caption("Notas: Severidade baseada na variação percentual vs média da temporada. Confiança reflete quantos jogos preencheram a janela (0–1). Jogos sem estatísticas completas são ignorados ou contam parcial.")
