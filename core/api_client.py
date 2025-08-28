from core.cache import api_get

def get_team(team_name: str):
    data = api_get("/teams", {"search": team_name})
    if data and data.get("response"):
        return data["response"][0]["team"]
    return None


def get_team_statistics(team_id: int, season: int, league_id: int):
    return api_get("/teams/statistics", {
        "team": team_id,
        "season": season,
        "league": league_id
    })


def get_team_fixtures(team_id: int, season: int, league_id: int):
    return api_get("/fixtures", {
        "team": team_id,
        "season": season,
        "league": league_id
    })


def get_players_for_team(team_id: int, season: int, league_id: int):
    """
    Busca jogadores com stats do time em determinada liga/temporada.
    """
    data = api_get("/players", {
        "team": team_id,
        "season": season,
        "league": league_id
    })
    return data.get("response", [])
