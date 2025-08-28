import math
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from core import api_client, ui_utils

st.title("📊 Desempenho do Time — Série B")

# ---------------------------------------------------------------------
# Filtros e cabeçalho
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

st.caption("KPIs agregados da temporada na Série B, tendências e previsão probabilística do próximo jogo. \
Sempre que um dado não estiver disponível na API, mostramos uma indicação e evitamos gráficos incorretos.")

OUR_ID = team["team_id"]
FINALS = {"FT", "AET", "PEN"}

# --------------------------- helpers --------------------------------
def safe_pct(v):
    """'55%' -> 55.0 | '55' -> 55.0 | None -> None"""
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
        return None

def stat_value(items, keys):
    """Busca um valor nas estatísticas do fixture tentando várias chaves."""
    for k in keys:
        for it in items:
            if (it.get("type") or "").lower() == k.lower():
                return safe_pct(it.get("value"))
    return None

def is_final(fx):
    return (fx["fixture"].get("status", {}) or {}).get("short") in FINALS

def fmt_metric(v, unit=""):
    if v is None or (isinstance(v, float) and (np.isnan(v))):
        return "—"
    if isinstance(v, float):
        v = round(v, 2)
    return f"{v}{unit}"

def avg(values):
    vals = [safe_pct(x) for x in values if x is not None]
    return round(float(np.mean(vals)), 2) if vals else None

# --------------------------- coleta por jogo -------------------------
fixtures_all = api_client.fixtures(OUR_ID, season) or []
for m in fixtures_all:
    m["_date"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
fixtures_all = sorted(fixtures_all, key=lambda x: x.get("_date") or pd.Timestamp(0))
fixtures = [f for f in fixtures_all if is_final(f)]

rows = []
progress = st.progress(0)
for i, fx in enumerate(fixtures, start=1):
    progress.progress(i / max(1, len(fixtures)))
    f = fx["fixture"]
    h, a = fx["teams"]["home"], fx["teams"]["away"]
    our_home = (h["id"] == OUR_ID)
    gf = fx["goals"]["home"] if our_home else fx["goals"]["away"]
    ga = fx["goals"]["away"] if our_home else fx["goals"]["home"]

    try:
        blocks = api_client.fixture_statistics(f["id"]) or []
    except Exception:
        blocks = []

    my_items, opp_items = [], []
    for b in (blocks or []):
        tid = (b.get("team") or {}).get("id")
        if tid == OUR_ID:
            my_items = b.get("statistics") or []
        else:
            opp_items = b.get("statistics") or []

    shots = stat_value(my_items, ["Total Shots", "Shots Total", "Shots"])
    sot = stat_value(my_items, ["Shots on Goal", "Shots on Target", "SOT"])
    poss = stat_value(my_items, ["Ball Possession", "Possession"])
    pass_acc = stat_value(my_items, ["Passes %", "Passes accurate", "Accurate Passes"])
    corners_for = stat_value(my_items, ["Corner Kicks", "Corners"])
    corners_against = stat_value(opp_items, ["Corner Kicks", "Corners"])

    rows.append({
        "date": pd.to_datetime(f["date"], errors="coerce"),
        "H/A": "H" if our_home else "A",
        "GF": gf, "GA": ga,
        "Shots": shots, "SOT": sot, "Poss%": poss, "Pass%": pass_acc,
        "Corners_for": corners_for, "Corners_against": corners_against
    })
progress.empty()

df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

# --------------------------- KPIs + gols por minuto ------------------
stats = api_client.team_statistics(league["league_id"], season, OUR_ID) or {}
if isinstance(stats, list):
    stats = stats[0] if stats else {}

games_played = len(df)
gf_pg = avg(df["GF"].tolist()) if games_played else None
ga_pg = avg(df["GA"].tolist()) if games_played else None
shots_pg = avg(df["Shots"].tolist()) if games_played else None
sot_pg = avg(df["SOT"].tolist()) if games_played else None
poss_avg = avg(df["Poss%"].tolist()) if games_played else None
pass_pct = avg(df["Pass%"].tolist()) if games_played else None
corn_for_pg = avg(df["Corners_for"].tolist()) if games_played else None
corn_against_pg = avg(df["Corners_against"].tolist()) if games_played else None
clean_sheets = int((df["GA"] == 0).sum()) if not df.empty else 0

st.markdown("### 🔢 KPIs principais")
st.caption("**O que é**: Médias por jogo calculadas com base nas partidas finalizadas desta temporada.")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Chutes/jogo", fmt_metric(shots_pg))
k2.metric("SOT/jogo", fmt_metric(sot_pg))
k3.metric("Posse média", fmt_metric(poss_avg, "%"))
k4.metric("Passes certos", fmt_metric(pass_pct, "%"))

k5, k6, k7, k8 = st.columns(4)
k5.metric("Gols Pró/jogo", fmt_metric(gf_pg))
k6.metric("Gols Contra/jogo", fmt_metric(ga_pg))
k7.metric("Escanteios/jogo", fmt_metric(corn_for_pg))
k8.metric("Clean Sheets", clean_sheets)

# Gols por minuto
def minute_df(side_key: str):
    try:
        minute_map = (((stats.get("goals") or {}).get(side_key) or {}).get("minute")) or {}
    except Exception:
        minute_map = {}
    rows = []
    for rng, obj in (minute_map or {}).items():
        total = (obj or {}).get("total")
        if total is None:
            continue
        rows.append({"minuto": rng, "total": safe_pct(total)})
    return pd.DataFrame(rows)

st.markdown("### ⏱️ Gols por faixa de minuto")
st.caption("**O que é**: distribuição de gols marcados/sofridos por intervalos de tempo (dados da API do time).")
df_m_for = minute_df("for")
df_m_against = minute_df("against")
c1, c2 = st.columns(2)
with c1:
    st.subheader("⚽ Gols Pró")
    if not df_m_for.empty:
        st.plotly_chart(px.bar(df_m_for, x="minuto", y="total"), use_container_width=True)
    else:
        st.info("Sem distribuição por minuto disponível.")
with c2:
    st.subheader("🧱 Gols Contra")
    if not df_m_against.empty:
        st.plotly_chart(px.bar(df_m_against, x="minuto", y="total"), use_container_width=True)
    else:
        st.info("Sem distribuição por minuto disponível.")

st.caption("Fonte: API-Football — /teams/statistics e /fixtures(/statistics).")
st.markdown("---")

# --------------------------- Tendências (rolling) --------------------
st.markdown("### 📉 Tendências (médias móveis)")
st.caption("**O que é**: evolução das métricas ao longo do tempo. A linha tracejada usa média móvel para suavizar oscilações.")
if df.empty:
    st.info("Sem jogos finalizados nesta temporada.")
else:
    win_max = max(3, min(10, len(df)))
    win = st.slider("Janela (jogos)", 3, win_max, min(5, win_max))
    for col, label in [("GF", "Gols Pró"), ("GA", "Gols Contra"), ("SOT", "Chutes no alvo")]:
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().sum() < 2:
            st.info(f"Sem dados suficientes para **{label}**.")
            continue
        roll = series.rolling(win, min_periods=1).mean()
        plot = pd.DataFrame({"data": df["date"], label: series, f"{label} (média {win}j)": roll})
        melt = plot.melt(id_vars="data", var_name="Série", value_name="Valor")
        fig = px.line(melt, x="data", y="Valor", color="Série")
        fig.update_layout(xaxis_title="Data", yaxis_title=label)
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# --------------------------- Casa x Fora ------------------------------
st.markdown("### 🏟️ Casa x Fora — Médias por jogo")
st.caption("**O que é**: comparação de desempenho entre partidas como mandante e visitante.")
if df.empty:
    st.info("Sem jogos finalizados para comparar Casa x Fora.")
else:
    ha = df.groupby("H/A").agg({"GF": "mean", "GA": "mean", "SOT": "mean", "Poss%": "mean"}).reset_index()
    for c in ["GF", "GA", "SOT", "Poss%"]:
        ha[c] = ha[c].round(2)
    tabs = st.tabs(["GF/GA", "SOT", "Posse"])
    with tabs[0]:
        melt = ha.melt(id_vars="H/A", value_vars=["GF", "GA"], var_name="Métrica", value_name="Valor")
        st.plotly_chart(px.bar(melt, x="H/A", y="Valor", color="Métrica", barmode="group"), use_container_width=True)
    with tabs[1]:
        st.plotly_chart(px.bar(ha, x="H/A", y="SOT"), use_container_width=True)
    with tabs[2]:
        st.plotly_chart(px.bar(ha, x="H/A", y="Poss%"), use_container_width=True)

st.markdown("---")

# --------------------------- Conversão & Escanteios ------------------
st.markdown("### 🎯 Conversão & Escanteios")
st.caption("**O que é**: conversão = gols/sotaques no alvo (SOT). Escanteios médios a favor e contra por jogo.")
if df.empty:
    st.info("Sem jogos finalizados.")
else:
    conv = None
    if df["SOT"].notna().any():
        total_sot = pd.to_numeric(df["SOT"], errors="coerce").sum(skipna=True)
        total_gf = pd.to_numeric(df["GF"], errors="coerce").sum(skipna=True)
        conv = round((total_gf / total_sot) * 100, 1) if total_sot else None

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Conversão (Gols/SOT)", fmt_metric(conv, "%"))
    with c2:
        if df["Corners_for"].notna().any() or df["Corners_against"].notna().any():
            corner_plot = pd.DataFrame({
                "Tipo": ["A favor", "Contra"],
                "Escanteios/jogo": [
                    avg(df["Corners_for"].tolist()) or 0,
                    avg(df["Corners_against"].tolist()) or 0
                ]
            })
            st.plotly_chart(px.bar(corner_plot, x="Tipo", y="Escanteios/jogo"), use_container_width=True)
        else:
            st.info("Sem dados de escanteios na API para esta temporada.")

st.markdown("---")

# --------------------------- Previsão (Poisson) ----------------------
st.markdown("### 🔮 Previsão (Poisson) — Próximo jogo")
st.caption("**Como funciona**: usa uma aproximação de Poisson com as médias de gols pró/contra do Coxa e do adversário para estimar \
probabilidades de placares e V/E/D. É um modelo simples, apenas indicativo.")

next_fx = api_client.fixtures(OUR_ID, season, next=1)
if not next_fx:
    st.info("Nenhum próximo jogo encontrado na API.")
else:
    fx = next_fx[0]
    home = fx["teams"]["home"]; away = fx["teams"]["away"]
    is_home = (home["id"] == OUR_ID)
    opp = away if is_home else home

    colh, colt = st.columns([1, 6])
    with colh:
        ui_utils.load_image(opp["logo"], size=48, alt=opp["name"])
    with colt:
        st.markdown(f"**Próximo adversário:** {opp['name']}  •  **Local:** {'Casa' if is_home else 'Fora'}")
        try:
            st.caption(pd.to_datetime(fx['fixture']['date']).strftime("%d/%m/%Y %H:%M"))
        except Exception:
            pass

    # λ Coxa a partir das médias desta página (fallbacks seguros)
    lam_for = gf_pg if gf_pg is not None else 1.0
    lam_against = ga_pg if ga_pg is not None else 1.0

    # λ adversário (se disponível)
    opp_stats = api_client.team_statistics(league["league_id"], season, opp["id"]) or {}
    if isinstance(opp_stats, list):
        opp_stats = opp_stats[0] if opp_stats else {}

    def read_avg_goals(block, side):
        try:
            g = (block.get("goals") or {}).get(side) or {}
            val = (g.get("average") or {}).get("total")
            return float(val) if val is not None else None
        except Exception:
            return None

    opp_for = read_avg_goals(opp_stats, "for")
    opp_against = read_avg_goals(opp_stats, "against")

    lam_us = np.mean([x for x in [lam_for, opp_against] if x is not None]) if any([lam_for, opp_against]) else 1.0
    lam_them = np.mean([x for x in [lam_against, opp_for] if x is not None]) if any([lam_against, opp_for]) else 1.0

    # Se por algum motivo ainda vierem inválidos, use 1.0
    lam_us = float(lam_us) if lam_us and lam_us > 0 else 1.0
    lam_them = float(lam_them) if lam_them and lam_them > 0 else 1.0

    # Matriz de probabilidades até 5x5
    def pois_pmf(k, lam):
        return math.exp(-lam) * (lam ** k) / math.factorial(k)

    max_goals = 5
    grid = np.zeros((max_goals + 1, max_goals + 1))
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            grid[i, j] = pois_pmf(i, lam_us) * pois_pmf(j, lam_them)
    grid = grid / grid.sum()

    # Prob. V/E/D (ajuste para mandante/visitante)
    if is_home:
        p_win = float(np.triu(grid, 1).sum())   # nós gols > eles
        p_lose = float(np.tril(grid, -1).sum())
    else:
        p_win = float(np.tril(grid, -1).sum())  # como visitantes, nós gols < eles é DERROTA; invertido para vitória
        p_lose = float(np.triu(grid, 1).sum())
    p_draw = float(np.trace(grid))

    p_over25 = float(sum(grid[i, j] for i in range(max_goals+1) for j in range(max_goals+1) if i + j >= 3))
    p_btts = float(sum(grid[i, j] for i in range(1, max_goals+1) for j in range(1, max_goals+1)))

    out = [(i, j, grid[i, j]) for i in range(max_goals + 1) for j in range(max_goals + 1)]
    out = sorted(out, key=lambda x: x[2], reverse=True)[:6]

    cols = st.columns(3)
    cols[0].metric("Vitória", f"{round(p_win*100,1)}%")
    cols[1].metric("Empate", f"{round(p_draw*100,1)}%")
    cols[2].metric("Derrota", f"{round(p_lose*100,1)}%")

    cols = st.columns(3)
    cols[0].metric("Over 2.5 gols", f"{round(p_over25*100,1)}%")
    cols[1].metric("BTTS (ambos marcam)", f"{round(p_btts*100,1)}%")
    cols[2].metric("xG simples (λ Coxa)", round(lam_us, 2))

    st.markdown("**Placares mais prováveis**")
    df_scores = pd.DataFrame([{"Placar": f"{i}–{j}", "Prob%": round(p*100, 2)} for i, j, p in out])
    st.dataframe(df_scores, use_container_width=True, hide_index=True)

st.caption("Modelo de Poisson simples (independência e médias recentes). Use como referência, não como predição determinística.")
