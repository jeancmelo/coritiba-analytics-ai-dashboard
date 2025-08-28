import os, requests
from typing import Dict, Any, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

# ==============================
# IDs FIXOS (conforme solicitado)
# ==============================
CORITIBA_ID = 147      # Coritiba Foot Ball Club
BR_SERIE_B_ID = 72      # Campeonato Brasileiro Série B (2025)
# Obs: o "season" continua vindo do select da UI (2025/2024/2023 etc.)

BASE = "https://v3.football.api-sports.io"

def _get_secret(key: str) -> Optional[str]:
    val = os.getenv(key)
    if val: 
        return val
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None

def _headers():
    key = _get_secret("APISPORTS_KEY")
    if not key:
        raise RuntimeError("APISPORTS_KEY não definida em ambiente/secrets.")
    return {"x-apisports-key": key}

@retry(stop=stop_after_attempt(3), wait=wait_exponential(1, 2, 8))
def api_get(endpoint: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    r = requests.get(f"{BASE}/{endpoint}", headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("response", [])

# ======================================================
# FUNÇÕES FIXAS (mantêm as mesmas assinaturas da v2)
# ======================================================

def find_team(name: str = "Coritiba") -> Dict[str, Any]:
    """
    Retorna SEMPRE o Coritiba (ID fixo) para evitar autodetect equivocado.
    """
    # Logo direto do CDN oficial da API-Football:
    team_logo = f"https://media-4.api-sports.io/football/teams/{CORITIBA_ID}.png"
    return {
        "team_id": CORITIBA_ID,
        "team_name": "Coritiba",
        "team_logo": team_logo,
        # Venue não vem fixo da API aqui; colocamos algo amigável:
        "venue": {"name": "Estádio Couto Pereira"}
    }

def autodetect_league(team_id: int, season: int, country: str = "Brazil") -> Dict[str, Any]:
    """
    Retorna SEMPRE a Série B (ID fixo). Mantém o nome para não quebrar páginas existentes.
    """
    league_logo = f"https://media-4.api-sports.io/football/leagues/{BR_SERIE_B_ID}.png"
    return {
        "league_id": BR_SERIE_B_ID,
        "league_name": "Serie B",
        "league_logo": league_logo,
        "seasons": [season]
    }

# ======================================================
# Wrappers de endpoints (iguais aos anteriores)
# ======================================================

def fixtures(team_id: int, season: int, **kw):
    p = {"team": team_id, "season": season}
    p.update(kw)
    return api_get("fixtures", p)

def fixture_statistics(fixture_id: int):
    return api_get("fixtures/statistics", {"fixture": fixture_id})

def fixture_events(fixture_id: int):
    return api_get("fixtures/events", {"fixture": fixture_id})

def fixture_lineups(fixture_id: int):
    return api_get("fixtures/lineups", {"fixture": fixture_id})

def fixture_players(fixture_id: int):
    return api_get("fixtures/players", {"fixture": fixture_id})

def standings(league_id: int, season: int):
    return api_get("standings", {"league": league_id, "season": season})

def team_statistics(league_id: int, season: int, team_id: int):
    return api_get("teams/statistics", {"league": league_id, "season": season, "team": team_id})
