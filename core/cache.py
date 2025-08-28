import os
import requests
import streamlit as st
from datetime import datetime, timedelta

# Controle de sessão
_session = None
_last_updated = None

def _api_key():
    """
    Busca a chave da API (APISPORTS_KEY) do st.secrets ou os.environ.
    """
    key = None
    if "APISPORTS_KEY" in st.secrets:
        key = st.secrets["APISPORTS_KEY"]
    elif "APISPORTS_KEY" in os.environ:
        key = os.environ["APISPORTS_KEY"]

    if not key:
        raise RuntimeError("APISPORTS_KEY não configurado nos Secrets/Env.")
    return key


def http_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "x-apisports-key": _api_key(),
            "Accept": "application/json"
        })
    return _session


@st.cache_data(ttl=60*60*24)  # 24h de cache
def api_get(path, params=None):
    """
    Chamada genérica GET para a API-Football.
    """
    base_url = "https://v3.football.api-sports.io"
    url = f"{base_url}{path}"
    sess = http_session()
    r = sess.get(url, params=params or {})
    r.raise_for_status()
    return r.json()
