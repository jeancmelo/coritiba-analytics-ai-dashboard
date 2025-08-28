import math
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from core import api_client, ui_utils

st.title("📊 Desempenho do Time — Série B")

# ---------------------------------------------------------------------
# filtros + cabeçalho
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

st.caption("KPIs agregados da temporada na Série B, tendências com médias móveis e uma previsão probabilística simples do próximo jogo (modelo de Poisson).")

OUR_ID = team["team_id"]
FINALS = {"FT", "AET", "PEN"}

# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------
def as_float(x):
    if x is None:
        return None
    if isinstance(x, str) and "%" in x:
        try:
            return float(x.replace("%", "").strip())
        except Exception:
            return None
    try:
        return float(x)
    except Exception:
        try:
            return int(x)
        except Exception:
            return None

def stat_value(items, keys):
    for k in keys:
        for it in items:
            if (it.get("type") or "").lower() == k.lower():
                return as_float(it.get("value"))
    return None

def is_final(fx):
    return (fx["fixture"].get("status", {}) or {}).get("short") in FINALS

def fmt_metric(x, digits=2):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "–"
    return round(x, digits) if isinstance(x, (int, float)) else x

def mean_clean(values):
    vals = [as_float(v) for v in values if as_float(v) is not None]
    return float(np.mean(vals)) if vals else None

# ---------------------------------------------------------------------
# 1) fixtures + estatísticas por jogo
# ---------------------------------------------------------------------
fixtures_all = api_client.fixtures(OUR_ID, season) or []
for m in fixtures_all:
    m["_date"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
fixtures_all = sorted(fixtures_all, key=lambda x: x.get("_date") or pd.Timestamp(0))

fixtures = [f for f in fixtures_all if is_final(f)]

rows = []
if fixtures:
    progress = st.progress(0)
else:
    progress = None

for i, fx in enumerate(fixtures, start=1):
    if progress:
        progress.progress(i / len(fixtures))
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
    for b in blocks:
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
        "GF": as_float(gf), "GA": as_float(ga),
        "Shots": shots, "SOT": sot, "Poss%": poss, "Pass%": pass_acc,
        "Corners_for": corners_for, "Corners_against": corners_against
    })

if progress:
    progress.empty()

df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

# ---------------------------------------------------------------------
# 2) KPIs gerais + gols por minuto
# ---------------------------------------------------------------------
stats = api_client.team_statistics(league["league_id"], season, OUR_ID) or {}
if isinstance(stats, list):
    stats = stats[0] if stats else {}

games_played = len(df)
gf_pg = mean_clean(df["GF"].tolist()) if games_played else None
ga_pg = mean_clean(df["GA"].tolist()) if games_played else None
shots_pg = mean_clean(df["Shots"].tolist()) if games_played else None
sot_pg = mean_clean(df["SOT"].tolist()) if games_played else None
poss_avg = mean_clean(df["Poss%"].tolist()) if games_played else None
pass_pct = mean_clean(df["Pass%"].tolist()) if games_played else None
corn_for_pg = mean_clean(df["Corners_for"].tolist()) if games_played else None
corn_against_pg = mean_clean(df["Corners_against"].tolist()) if games_played else None
clean_sheets = int((df["GA"] == 0).sum()) if not df.empty else 0

st.markdown("#### KPIs da temporada")
st.caption("**Chutes/SOT** = por jogo; **Posse/Passes** = médias; **Escanteios** = por jogo; **Clean sheets** = jogos sem sofrer gol.")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Chutes/jogo", fmt_metric(shots_pg))
k2.metric("SOT/jogo", fmt_metric(sot_pg))
k3.metric("Posse (%)", fmt_metric(poss_avg))
k4.metric("Passes certos (%)", fmt_metric(pass_pct))

k5, k6, k7, k8 = st.columns(4)
k5.metric("Gols Pró/jogo", fmt_metric(gf_pg))
k6.metric("Gols Contra/jogo", fmt_metric(ga_pg))
k7.metric("Escanteios/jogo", fmt_metric(corn_for_pg))
k8.metric("Clean Sheets", clean_sheets)

st.markdown("---")

def minute_df(side_key: str):
    """
    Usa /teams/statistics para pegar distribuição de gols por faixa de minuto.
    Nem sempre esse dado existe para todas as ligas/temporadas.
    """
    try:
        minute_map = (((stats.get("goals") or {}).get(side_key) or {}).get("minute")) or {}
    except Exception:
        minute_map = {}
    rows_ = []
    for rng, obj in (minute_map or {}).items():
        total = (obj or {}).get("total")
        if total is None:
            continue
        rows_.append({"minuto": rng, "total": as_float(total)})
    return pd.DataFrame(rows_)

df_m_for = minute_df("for")
df_m_against = minute_df("against")

c1, c2 = st.columns(2)
with c1:
    st.subheader("⚽ Gols Pró por faixa de minuto")
    st.caption("Quantidade de gols marcados em janelas de 15 minutos.")
    if not df_m_for.empty and df_m_for["total"].notna().any():
        fig = px.bar(df_m_for, x="minuto", y="total")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem distribuição por minuto disponível.")
with c2:
    st.subheader("🧱 Gols Contra por faixa de minuto")
    st.caption("Quantidade de gols sofridos em janelas de 15 minutos.")
    if not df_m_against.empty and df_m_against["total"].notna().any():
        fig = px.bar(df_m_against, x="minuto", y="total")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem distribuição por minuto disponível.")

st.caption("Fonte: API-Football — /teams/statistics e /fixtures(/statistics).")
st.markdown("---")

# ---------------------------------------------------------------------
# 3) Tendências — rolling
# ---------------------------------------------------------------------
st.subheader("📉 Tendências (médias móveis)")
st.caption("Evolução ao longo da temporada. A média móvel suaviza variações curtas (janela configurável).")

if df.empty:
    st.info("Sem jogos finalizados nesta temporada.")
else:
    win = st.slider("Janela (jogos)", min_value=3, max_value=min(10, max(3, len(df))), value=min(5, len(df)))

    def plot_rolling(col, label):
        s = pd.to_numeric(df[col], errors="coerce")
        if s.notna().sum() == 0:
            st.info(f"Sem dados suficientes para **{label}**.")
            return
        roll = s.rolling(win, min_periods=1).mean()
        base = pd.DataFrame({"data": df["date"], label: s, f"{label} (média {win}j)": roll})
        melt = base.melt(id_vars="data", var_name="Série", value_name="Valor")
        fig = px.line(melt, x="data", y="Valor", color="Série")
        fig.update_layout(xaxis_title="Data", yaxis_title=label)
        st.plotly_chart(fig, use_container_width=True)

    plot_rolling("GF", "Gols Pró")
    plot_rolling("GA", "Gols Contra")
    plot_rolling("SOT", "Chutes no alvo")

st.markdown("---")

# ---------------------------------------------------------------------
# 4) Casa x Fora
# ---------------------------------------------------------------------
st.subheader("🏟️ Casa x Fora — Médias por jogo")
st.caption("Comparação do desempenho médio quando jogamos em casa (H) e fora (A).")

if df.empty:
    st.info("Sem jogos finalizados.")
else:
    ha = df.groupby("H/A").agg({"GF": "mean", "GA": "mean", "SOT": "mean", "Poss%": "mean"}).reset_index()
    for c in ["GF", "GA", "SOT", "Poss%"]:
        ha[c] = ha[c].round(2)

    tabs = st.tabs(["GF/GA", "SOT", "Posse (%)"])
    with tabs[0]:
        melt = ha.melt(id_vars="H/A", value_vars=["GF", "GA"], var_name="Métrica", value_name="Valor")
        st.plotly_chart(px.bar(melt, x="H/A", y="Valor", color="Métrica", barmode="group"), use_container_width=True)
    with tabs[1]:
        st.plotly_chart(px.bar(ha, x="H/A", y="SOT"), use_container_width=True)
    with tabs[2]:
        st.plotly_chart(px.bar(ha, x="H/A", y="Poss%"), use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------
# 5) Conversão & Escanteios
# ---------------------------------------------------------------------
st.subheader("🎯 Conversão & Escanteios")
st.caption("**Conversão** = Gols/SOT. **Escanteios** = média por jogo (a favor e contra).")

if df.empty:
    st.info("Sem jogos finalizados.")
else:
    total_sot = pd.to_numeric(df["SOT"], errors="coerce").sum(min_count=1)
    total_gf = pd.to_numeric(df["GF"], errors="coerce").sum(min_count=1)
    conv = round((total_gf / total_sot) * 100, 1) if (total_sot is not None and total_sot > 0) else None

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Conversão (Gols/SOT)", f"{conv}%" if conv is not None else "–")
    with c2:
        cf = mean_clean(df["Corners_for"].tolist())
        ca = mean_clean(df["Corners_against"].tolist())
        if cf is None and ca is None:
            st.info("Sem dados de escanteios.")
        else:
            corner_plot = pd.DataFrame({
                "Tipo": ["A favor", "Contra"],
                "Escanteios/jogo": [cf or 0, ca or 0]
            })
            st.plotly_chart(px.bar(corner_plot, x="Tipo", y="Escanteios/jogo"), use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------
# 6) Previsão do próximo jogo (Poisson)
# ---------------------------------------------------------------------
st.subheader("🔮 Previsão (Poisson) — Próximo jogo")
st.caption("Modelo simples que usa médias recentes para estimar a probabilidade de placares e de V/E/D. Interpretação **indicativa**, não determinística.")

next_fx = api_client.fixtures(OUR_ID, season, next=1)

if not next_fx:
    st.info("Nenhum próximo jogo encontrado na API.")
else:
    fx = next_fx[0]
    home = fx["teams"]["home"]; away = fx["teams"]["away"]
    is_home = (home["id"] == OUR_ID)
    opp = away if is_home else home

    # topo do bloco
    colh, colt = st.columns([1, 5])
    with colh:
        ui_utils.load_image(opp["logo"], size=48, alt=opp["name"])
    with colt:
        st.markdown(f"**Próximo adversário:** {opp['name']} • **Local:** {'Casa' if is_home else 'Fora'}")
        try:
            st.caption(pd.to_datetime(fx['fixture']['date']).strftime("%d/%m/%Y %H:%M"))
        except Exception:
            pass

    # janela para médias (N últimos jogos finalizados)
    if not df.empty:
        win_pred = st.slider("Usar últimos N jogos para as médias", min_value=3, max_value=min(12, len(df)), value=min(8, len(df)))
        df_recent = df.tail(win_pred)
    else:
        df_recent = df

    lam_for = mean_clean(df_recent["GF"].tolist()) or 1.0
    lam_against = mean_clean(df_recent["GA"].tolist()) or 1.0

    # pega médias do adversário (se disponível)
    opp_stats = api_client.team_statistics(league["league_id"], season, opp["id"]) or {}
    if isinstance(opp_stats, list):
        opp_stats = opp_stats[0] if opp_stats else {}

    def read_avg_goals(block, side):
        try:
            g = (block.get("goals") or {}).get(side) or {}
            v = (g.get("average") or {}).get("total")
            return as_float(v)
        except Exception:
            return None

    opp_for = read_avg_goals(opp_stats, "for")
    opp_against = read_avg_goals(opp_stats, "against")

    # combinação: nossa média pró com média contra do adversário (e vice-versa)
    lam_us = float(np.mean([x for x in [lam_for, opp_against] if x is not None])) if any([lam_for, opp_against]) else 1.0
    lam_them = float(np.mean([x for x in [lam_against, opp_for] if x is not None])) if any([lam_against, opp_for]) else 1.0

    # matriz de placares via Poisson (0..5)
    max_goals = 5

    def pois_pmf(k, lam):
        return math.exp(-lam) * (lam ** k) / math.factorial(k)

    grid = np.array([[pois_pmf(i, lam_us) * pois_pmf(j, lam_them) for j in range(max_goals + 1)]
                     for i in range(max_goals + 1)])
    grid = grid / grid.sum()

    # agregados
    if is_home:
        p_win = float(np.triu(grid, 1).sum())
        p_lose = float(np.tril(grid, -1).sum())
    else:
        p_lose = float(np.triu(grid, 1).sum())
        p_win = float(np.tril(grid, -1).sum())
    p_draw = float(np.trace(grid))

    p_over25 = float(sum(grid[i, j] for i in range(max_goals+1) for j in range(max_goals+1) if i + j >= 3))
    p_btts = float(sum(grid[i, j] for i in range(1, max_goals+1) for j in range(1, max_goals+1)))

    cols = st.columns(3)
    cols[0].metric("Vitória", f"{round(p_win*100,1)}%")
    cols[1].metric("Empate", f"{round(p_draw*100,1)}%")
    cols[2].metric("Derrota", f"{round(p_lose*100,1)}%")

    cols = st.columns(3)
    cols[0].metric("Over 2.5 gols", f"{round(p_over25*100,1)}%")
    cols[1].metric("BTTS (ambos marcam)", f"{round(p_btts*100,1)}%")
    cols[2].metric("λ esperado (nós)", fmt_metric(lam_us))

    # top-6 placares
    out = []
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            out.append((i, j, float(grid[i, j])))
    out = sorted(out, key=lambda x: x[2], reverse=True)[:6]

    st.markdown("**Placares mais prováveis**")
    df_scores = pd.DataFrame([{"Placar": f"{i}–{j}", "Prob%": round(p*100, 2)} for i, j, p in out])
    st.dataframe(df_scores, use_container_width=True, hide_index=True)

st.caption("Notas: quando um dado não está disponível na API, substituímos por “–” e evitamos que os gráficos quebrem. O modelo de Poisson usa médias recentes e supõe independência dos gols.")
