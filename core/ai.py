import os, json
from typing import Dict, Any, List, Optional
from openai import OpenAI

def _get_secret(key: str) -> Optional[str]:
    val = os.getenv(key)
    if val: return val
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None

def _client() -> OpenAI:
    key = _get_secret("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY não definida em ambiente/secrets.")
    return OpenAI(api_key=key)

SYSTEM = (
    "Você é um analista tático. Gere até 5 insights objetivos para o Coritiba com base nos dados, "
    "sempre em JSON (chave 'insights' = lista). Cada insight deve conter: type, title, summary, "
    "why_it_matters, recommended_action, metrics_used, evidence (lista de {label,value,baseline,unit}), "
    "severity (low|medium|high), confidence (0-1), timeframe e disclaimers quando aplicável. "
    "Se faltar algum dado (ex.: xG), aponte claramente."
)

def generate_insights(context: Dict[str, Any], model: str = "gpt-4o-mini") -> List[Dict[str, Any]]:
    client = _client()
    user_prompt = (
        "Gere até 5 insights táticos e de desempenho para o Coritiba, considerando temporada, forma recente "
        "e próximo adversário. Responda APENAS com um JSON do tipo {\"insights\":[...]}.

"
        f"DADOS:\n{json.dumps(context)[:7000]}\n"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role":"system","content": SYSTEM},
                {"role":"user","content": user_prompt},
            ],
            temperature=0.2
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
        return data.get("insights", [])
    except Exception as e:
        print("Falha ao gerar insights:", e)
        return []
