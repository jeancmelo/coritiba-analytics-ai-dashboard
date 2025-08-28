# core/cache.py
import os
import time
import json
import hashlib
import datetime as dt
import streamlit as st
import requests

API_HOST = "https://v3.football.api-sports.io"
DAY = 60 * 60 * 24  # 24 horas

# -------------------- Sessão HTTP (1x por worker) --------------------
@st.cache_resource
def http_session(api_key: str):
    s = requests.Session()
    s.headers.update({
        "x-apisports-key": api_key,
        "Accept": "application/json",
        "User-Agent": "coritiba-analytics-ai/1.0"
    })
    s.timeout = 30
    return s

def _api_key():
    key = os.environ.get("API_FOOTBALL_KEY") or os.environ.get("API_FOOTBALL")
    if not key:
        raise RuntimeError("API_FOOTBALL_KEY não configurado nos Secrets.")
    return key

# -------------------- “forçar refresh” por sessão --------------------
def _refresh_nonce():
    return st.session_state.get("refresh_key", 0)

def bump_refresh_key():
    st.session_state["refresh_key"] = st.session_state.get("refresh_key", 0) + 1

# -------------------- util p/ chave humana --------------------
def _fingerprint(path: str, params: dict) -> str:
    s = json.dumps({"path": path, "params": params}, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def _store_last_update(key: str, ts: float):
    if "_last_updates" not in st.session_state:
        st.session_state["_last_updates"] = {}
    st.session_state["_last_updates"][key] = ts

def last_updates():
    """dict {cache_key: ts} da sessão atual."""
    return st.session_state.get("_last_updates", {})

def last_updated_global() -> float | None:
    """Maior timestamp entre as últimas chamadas desta sessão."""
    lu = last_updates()
    if not lu:
        return None
    return max(lu.values())

def _fmt_dt(ts: float | None) -> str:
    if not ts:
        return "—"
    # formata no fuso local do servidor
    return dt.datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M")

def last_updated_text() -> str:
    ts = last_updated_global()
    if not ts:
        return "— sem dados nesta sessão —"
    ago = int(time.time() - ts)
    hours = ago // 3600
    mins = (ago % 3600) // 60
    return f"{_fmt_dt(ts)} (há {hours}h {mins}m)"

# -------------------- chamada com cache 24h + meta --------------------
@st.cache_data(ttl=DAY)  # cache forte: 24 horas
def _fetch_with_meta(path: str, params: dict, nonce: int):
    sess = http_session(_api_key())
    url = f"{API_HOST}{path}"
    r = sess.get(url, params=params, timeout=60)
    r.raise_for_status()
    return {
        "data": r.json(),          # payload bruto da API
        "fetched_at": time.time()  # quando foi baixado
    }

def get_json(path: str, params: dict, ttl_seconds: int | None = None) -> dict:
    """
    Retorna apenas o payload JSON.
    O TTL é 24h (definido no decorator). O parâmetro ttl_seconds está aqui
    apenas por compatibilidade (ignorado neste modo 'por dia').
    """
    meta = _fetch_with_meta(path, params, _refresh_nonce())
    # registra 'última atualização' humana nesta sessão
    key = _fingerprint(path, params)
    _store_last_update(key, meta.get("fetched_at", time.time()))
    return meta["data"]

def get_json_with_meta(path: str, params: dict) -> tuple[dict, float]:
    """Retorna (data, fetched_at) para quem quiser mostrar timestamp específico."""
    meta = _fetch_with_meta(path, params, _refresh_nonce())
    key = _fingerprint(path, params)
    _store_last_update(key, meta.get("fetched_at", time.time()))
    return meta["data"], meta.get("fetched_at", None)

# -------------------- UI pronta p/ sidebar --------------------
def render_cache_controls():
    st.sidebar.markdown("### 🔄 Dados")
    st.sidebar.caption(f"Última atualização (sessão): **{last_updated_text()}**")
    col1, col2 = st.sidebar.columns(2)
    if col1.button("Atualizar agora"):
        bump_refresh_key()
        st.experimental_rerun()
    if col2.button("Limpar cache"):
        st.cache_data.clear()
        st.success("Cache de dados limpo.")
