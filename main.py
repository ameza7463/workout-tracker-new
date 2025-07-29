import streamlit as st
import pandas as pd
import datetime
import uuid
import os
import time
from supabase import create_client, Client
from st_cookie_manager.cookie_manager import CookieManager

# --- Page config ---
st.set_page_config(page_title="Workout Tracker", layout="centered")
st.title("🏋️ Workout Tracker")

# --- Supabase setup ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Cookie manager ---
cookie_manager = CookieManager()

# --- Read cookies on load ---
access_token = cookie_manager.get("access_token")
refresh_token = cookie_manager.get("refresh_token")

if access_token and refresh_token:
    try:
        session_response = supabase.auth.set_session(access_token, refresh_token)
        if session_response.user:
            st.session_state.user = session_response.user
            st.session_state.access_token = access_token
            st.session_state.refresh_token = refresh_token
    except Exception as e:
        print("Failed to restore session:", e)

# --- Login ---
if "user" not in st.session_state:
    st.subheader("🔐 Login to Continue")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    col1, col2 = st.columns(2)

    if col1.button("Login"):
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            if auth_response.session and auth_response.user:
                st.session_state.user = auth_response.user
                st.session_state.access_token = auth_response.session.access_token
                st.session_state.refresh_token = auth_response.session.refresh_token
                cookie_manager.set("access_token", auth_response.session.access_token)
                cookie_manager.set("refresh_token", auth_response.session.refresh_token)
                st.success(f"Logged in as {st.session_state.user.email}")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Login failed. Check credentials.")
        except Exception as e:
            st.error(f"Login error: {e}")

    if col2.button("Sign Up"):
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            st.success("Account created. Please login.")
        except Exception as e:
            st.error(f"Signup failed: {e}")

    st.stop()

# --- Main App after login ---
user_id = st.session_state.user.id
if "current_exercises" not in st.session_state:
    st.session_state.current_exercises = []

# --- Add Exercise ---
st.subheader("➕ Add Exercise")
exercise_name = st.text_input("Exercise Name")
reps = st.number_input("Reps", min_value=1, step=1)
weight = st.number_input("Weight (lbs)", min_value=0, step=1)

if st.button("Add Set"):
    if exercise_name:
        st.session_state.current_exercises.append({
            "exercise": exercise_name,
            "reps": reps,
            "weight": weight
        })
        st.success("Set added!")

# --- View Current Session ---
if st.session_state.current_exercises:
    st.markdown("### 📜 Current Workout")
    for idx, ex in enumerate(st.session_state.current_exercises):
        st.write(f"• {ex['exercise']} - {ex['reps']} reps @ {ex['weight']} lbs")
        if st.button(f"❌ Remove", key=f"del_{idx}"):
            st.session_state.current_exercises.pop(idx)
            st.rerun()

# --- Save Workout to Supabase ---
if st.button("📂 Save Workout"):
    if st.session_state.current_exercises:
        supabase.auth.set_session(st.session_state.access_token, st.session_state.refresh_token)

        supabase.table("workouts").insert({
            "user_id": user_id,
            "date": str(datetime.date.today()),
            "exercises": st.session_state.current_exercises
        }).execute()
        st.success("Workout saved!")
        st.session_state.current_exercises = []
    else:
        st.warning("No exercises to save.")

# --- Load Workouts ---
st.subheader("📋 Workout History")
res = supabase.table("workouts").select("*").eq("user_id", user_id).order("date", desc=True).execute()
if res.data:
    for w in res.data:
        with st.expander(w["date"]):
            for ex in w["exercises"]:
                try:
                    st.write(f"{ex['exercise']} - {ex['reps']} reps @ {ex['weight']} lbs")
                except KeyError:
                    st.error("⚠️ Skipped broken workout entry. Some fields were missing.")

# --- Logout ---
if st.button("Logout"):
    cookie_manager.delete("access_token")
    cookie_manager.delete("refresh_token")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.success("Logged out.")
    st.rerun()




