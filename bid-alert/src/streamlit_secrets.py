"""Load Streamlit secrets into environment when deployed."""

from __future__ import annotations

import os

def load_streamlit_secrets() -> None:
    try:
        import streamlit as st

        if hasattr(st, "secrets") and st.secrets:
            for key, value in st.secrets.items():
                if isinstance(value, (str, int, float)) and key not in os.environ:
                    os.environ[key] = str(value)
    except Exception:
        pass
