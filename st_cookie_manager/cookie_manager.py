import streamlit as st

class CookieManager:
    def __init__(self):
        if "cookies" not in st.session_state:
            st.session_state["cookies"] = {}

    def get(self, key):
        return st.session_state["cookies"].get(key)

    def set(self, key, value, **kwargs):  # Accept any extra keyword args like 'expires_days'
        st.session_state["cookies"][key] = value

    def delete(self, key):
        if key in st.session_state["cookies"]:
            del st.session_state["cookies"][key]
