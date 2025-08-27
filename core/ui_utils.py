import streamlit as st
import requests
from PIL import Image, ImageDraw
import io

def load_image(url: str, size: int = 32, alt: str = "img", radius: int = 4):
    """
    Carrega imagem de uma URL e exibe no Streamlit.
    - Se falhar, gera um placeholder com iniciais do alt.
    - Mantém tamanho fixo para consistência visual.
    """
    try:
        if url:
            r = requests.get(url, timeout=10)
            if r.ok:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                img = img.resize((size, size))
                return st.image(img, width=size, caption=alt)
    except Exception:
        pass

    # fallback (iniciais em fundo cinza)
    canvas = Image.new("RGB", (size, size), "#ccc")
    d = ImageDraw.Draw(canvas)
    initials = alt[:2].upper() if alt else "?"
    d.text((size // 3, size // 3), initials, fill="black")
    st.image(canvas, width=size, caption=alt)


def team_badge(name: str, logo_url: str, size: int = 24):
    """
    Exibe logo pequeno + nome do time.
    """
    col1, col2 = st.columns([1, 4])
    with col1:
        load_image(logo_url, size=size, alt=f"Logo {name}")
    with col2:
        st.write(name)
