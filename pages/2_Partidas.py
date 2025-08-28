# pages/2_Partidas.py
import streamlit as st
import pandas as pd
from core import api_client, ui_utils

PAGE_TITLE = "📅 Partidas"

st.title(PAGE_TITLE)

# ------------------------------------------------------------
# Helpers de UI
# ------------------------------------------------------------
def team_chip(name: str, logo: str, size: int = 32):
    """Renderiza logo + nome em linha (evita quebra vertical)."""
    if not name:
        name = "-"
    if not logo:
        logo = "https://placehold.co/64x64?text=?"
    html = f"""
    <div style="display:flex;align-items:center;gap:8px;">
      <img src="{logo}" style="width:{size}px;height:{size}px;border-radius:50%;object-fit:contain" />
      <span style="font-weight:600;">{name}</span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def grid_names(names, cols=5):
    """Mostra nomes em grade responsiva (corrige alinhamento quebrado)."""
    names = [n for n in names if n]
    if not names:
        st.caption("—")
        return
    # distribui em colunas
    columns = st.columns(cols)
    for i, name in enumerate(names):
        with columns[i % cols]:
            st.write(name)

def fmt_date(iso_str: str) -> str:
    try:
        return pd.to_datetime(iso_str).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(iso_str)[:16]

def is_finished(fx) -> bool:
    try:
        stt = ((fx.get("fixture") or {}).get("status") or {})
        short = (stt.get("short") or "").upper()
        long = (stt.get("long") or "").lower()
        return short in {"FT", "AET", "PEN"} or "match finished" in long
    except Exception:
        return False

# ------------------------------------------------------------
# Filtros
# ------------------------------------------------------------
season = st.sidebar.selectbox("Temporada", [2025, 2024, 2023], index=0)
team = api_client.find_team("Coritiba")
league = api_client.autodetect_league(team["team_id"], season, "Brazil")

# Header com logos
c1, c2, c3 = st.columns([1, 4, 1])
with c1:
    ui_utils.load_image(team["team_logo"], size=56, alt="Logo do Coritiba")
with c2:
    st.subheader(f"{team['team_name']} — {season} • {league['league_name']}")
with c3:
    ui_utils.load_image(league["league_logo"], size=56, alt="Logo da Liga")

# ------------------------------------------------------------
# Dados
# ------------------------------------------------------------
fixtures = api_client.fixtures(team["team_id"], season) or []

# ordena e filtra somente os finalizados
for m in fixtures:
    try:
        m["_d"] = pd.to_datetime(m["fixture"]["date"], errors="coerce")
    except Exception:
        m["_d"] = pd.NaT
fixtures = [fx for fx in fixtures if is_finished(fx)]
fixtures = sorted(
    fixtures,
    key=lambda x: x.get("_d") if x.get("_d") is not None else pd.Timestamp(0),
    reverse=True,
)

total = len(fixtures)

# Quantos mostrar (inicial 3, carregar +3 a cada clique)
key_limit = "partidas_limit"
if key_limit not in st.session_state:
    st.session_state[key_limit] = 3   # <— inicial

col_top = st.columns([1, 3, 1])
with col_top[0]:
    if st.button("Carregar\nmais 3"):
        st.session_state[key_limit] = min(total, st.session_state[key_limit] + 3)
with col_top[1]:
    st.caption(f"Mostrando {min(st.session_state[key_limit], total)} de {total} jogos (somente já disputados).")

show = fixtures[: st.session_state[key_limit]]

# ------------------------------------------------------------
# Render por jogo
# ------------------------------------------------------------
for fx in show:
    fix = fx.get("fixture") or {}
    league_info = fx.get("league") or {}
    teams = fx.get("teams") or {}
    home = teams.get("home", {})
    away = teams.get("away", {})
    goals = fx.get("goals") or {}

    gh, ga = goals.get("home"), goals.get("away")

    st.markdown("---")
    left, center, right = st.columns([3, 2, 3])

    with left:
        team_chip(home.get("name", "-"), home.get("logo"))
    with center:
        st.markdown(
            f"<div style='text-align:center;font-size:42px;font-weight:700;'>{gh if gh is not None else 0} : {ga if ga is not None else 0}</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"{fmt_date(fix.get('date'))}")
    with right:
        with st.container():
            # alinhar à direita mantendo o chip horizontal
            st.markdown("<div style='display:flex;justify-content:flex-end;'>", unsafe_allow_html=True)
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:8px;">
                    <span style="font-weight:600;margin-right:6px;"></span>
                    <img src="{away.get('logo')}" style="width:32px;height:32px;border-radius:50%;object-fit:contain"/>
                    <span style="font-weight:600;">{away.get('name','-')}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

    # Sub-infos
    cA, cB, cC = st.columns([3, 4, 3])
    with cA:
        st.markdown(f"**{home.get('name','-')}**")
        st.caption(f"Liga: {league_info.get('name','-')} • {league_info.get('round','-')}")
    with cB:
        status = (fix.get("status") or {}).get("long", "—")
        st.caption(f"Status: {status}")
    with cC:
        pass

    # --------------------------------------------------------
    # Expander de detalhes
    # --------------------------------------------------------
    with st.expander("▸ Ver detalhes", expanded=False):
        # ----------------- Estatísticas do jogo -----------------
        st.subheader("Estatísticas do jogo")
        stats = api_client.fixture_statistics(fix.get("id")) or []
        # stats vem como lista com item por time
        stat_map = {}  # {team_name: {stat_name: value}}
        for row in stats:
            t = (row.get("team") or {}).get("name") or "-"
            for kv in (row.get("statistics") or []):
                n = kv.get("type")
                v = kv.get("value")
                try:
                    if isinstance(v, str) and v.endswith("%"):
                        v = float(v.strip("%")) / 100.0
                except Exception:
                    pass
                stat_map.setdefault(t, {})[n] = v

        # Monta DataFrame lado a lado
        if stat_map:
            left_team = home.get("name", "-")
            right_team = away.get("name", "-")
            all_keys = sorted(set(list(stat_map.get(left_team, {}).keys()) + list(stat_map.get(right_team, {}).keys())))
            rows = []
            for k in all_keys:
                rows.append({
                    "Métrica": k,
                    left_team: stat_map.get(left_team, {}).get(k, "—"),
                    right_team: stat_map.get(right_team, {}).get(k, "—"),
                })
            df_stats = pd.DataFrame(rows)
            st.dataframe(df_stats, use_container_width=True, hide_index=True)
        else:
            st.caption("Sem estatísticas disponíveis para este jogo.")

        st.markdown("---")

        # ----------------- Lineups & formações -----------------
        st.subheader("Lineups & formações")
        lineups = api_client.fixture_lineups(fix.get("id")) or []

        # Indexa por ID de time
        by_id = {}
        for l in lineups:
            tid = (l.get("team") or {}).get("id")
            by_id[tid] = l

        def render_team_lineup(team_dict):
            tname = team_dict.get("team", {}).get("name", "-")
            tlogo = team_dict.get("team", {}).get("logo")
            formation = team_dict.get("formation", "-")
            starters = [p.get("player", {}).get("name") for p in (team_dict.get("startXI") or [])]
            subs = [p.get("player", {}).get("name") for p in (team_dict.get("substitutes") or [])]

            # Chip + formação badge
            cc1, cc2 = st.columns([4, 1])
            with cc1:
                team_chip(tname, tlogo, size=28)
            with cc2:
                st.markdown(
                    f"<div style='display:inline-block;padding:4px 8px;border-radius:8px;background:#1f2937;color:#fff;font-size:12px;'>formação: <b>{formation}</b></div>",
                    unsafe_allow_html=True,
                )
            st.markdown("**Titulares:**")
            grid_names(starters, cols=5)
            if subs:
                with st.expander("Ver banco de reservas"):
                    grid_names(subs, cols=5)

        # Render dos dois times (Evita quebras verticais)
        left_l, right_l = st.columns(2)
        with left_l:
            render_team_lineup(by_id.get(home.get("id"), {}))
        with right_l:
            render_team_lineup(by_id.get(away.get("id"), {}))

        # ----------------- Eventos (opcional, curto) ------------
        # (mantemos simples para não pesar)
        # events = api_client.fixture_events(fix.get("id")) or []
        # if events:
        #     st.subheader("Eventos")
        #     tiny = [{"min": e.get("time", {}).get("elapsed"), 
        #              "team": (e.get("team") or {}).get("name"),
        #              "player": (e.get("player") or {}).get("name"),
        #              "type": e.get("type"),
        #              "detail": e.get("detail")} for e in events]
        #     st.dataframe(pd.DataFrame(tiny), use_container_width=True, hide_index=True)

# ------------------------------------------------------------
# Rodapé
# ------------------------------------------------------------
st.caption(f"Fonte: API-Football — /fixtures, /fixtures/statistics, /fixtures/lineups  (league={league['league_id']}, season={season}, team={team['team_id']})")
