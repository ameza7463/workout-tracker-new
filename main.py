import os
import datetime
import streamlit as st
from supabase import create_client, Client
from st_cookies_manager import EncryptedCookieManager

# ---------- Config ----------
st.set_page_config(page_title="Workout Tracker", page_icon="💪", layout="centered")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
COOKIE_PASSWORD = os.environ.get("COOKIE_PASSWORD", "change-this-in-prod")
COOKIE_PREFIX = "wtapp_"  # avoids clashes on Streamlit Cloud

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("Missing SUPABASE_URL or SUPABASE_ANON_KEY environment variables.")
    st.stop()

# ---------- Init Supabase ----------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# ---------- Cookies (tokens) ----------
cookies = EncryptedCookieManager(prefix=COOKIE_PREFIX, password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()  # Wait for component to load

def save_tokens(session):
    if not session:
        return
    cookies["access_token"] = session.access_token
    cookies["refresh_token"] = session.refresh_token
    cookies.save()

def clear_tokens():
    for k in ("access_token", "refresh_token"):
        if k in cookies:
            del cookies[k]
    cookies.save()

def restore_session():
    """Restore Supabase session from cookies (if present)."""
    at = cookies.get("access_token")
    rt = cookies.get("refresh_token")
    if at and rt:
        try:
            supabase.auth.set_session(at, rt)  # v2 API: set_session(access, refresh)
            return True
        except Exception:
            # tokens invalid/expired — clear them
            clear_tokens()
    return False

# Try to restore a session once per run
if "session_restored" not in st.session_state:
    st.session_state.session_restored = restore_session()

# ---------- Helpers ----------
def get_current_user():
    try:
        res = supabase.auth.get_user()
        return res.user
    except Exception:
        return None

def require_auth():
    user = get_current_user()
    if user is None:
        st.stop()
    return user

# ---------- Auth UI ----------
def auth_ui():
    tabs = st.tabs(["Log in", "Sign up"])
    with tabs[0]:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pw")
            submitted = st.form_submit_button("Log in")
            if submitted:
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    save_tokens(res.session)
                    st.success("Logged in.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    with tabs[1]:
        with st.form("signup_form", clear_on_submit=False):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password (min 6 chars)", type="password", key="signup_pw")
            submitted = st.form_submit_button("Create account")
            if submitted:
                try:
                    res = supabase.auth.sign_up({"email": email, "password": password})
                    # Some projects require email confirmation before a session exists.
                    if res.session:
                        save_tokens(res.session)
                        st.success("Account created and logged in.")
                    else:
                        st.success("Account created. Please check your email to confirm, then log in.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sign up failed: {e}")

# ---------- App UI (after login) ----------
def topbar(user):
    cols = st.columns([1, 1, 1, 2])
    with cols[0]:
        st.caption(f"Signed in as:")
        st.write(f"**{user.email}**")
    with cols[2]:
        if st.button("Refresh"):
            st.rerun()
    with cols[3]:
        if st.button("Log out", use_container_width=True):
            try:
                supabase.auth.sign_out()
            except Exception:
                pass
            clear_tokens()
            st.success("Logged out.")
            st.rerun()

def add_set_form(user):
    st.subheader("Add Workout Set")
    with st.form("add_set_form", clear_on_submit=True):
        date = st.date_input("Date", value=datetime.date.today())
        exercise = st.text_input("Exercise", placeholder="e.g., Incline DB Press")
        reps = st.number_input("Reps", min_value=1, max_value=1000, value=8, step=1)
        weight = st.number_input("Weight", min_value=0.0, max_value=2000.0, value=135.0, step=2.5)
        notes = st.text_area("Notes", placeholder="Optional")
        submitted = st.form_submit_button("Add set")
        if submitted:
            try:
                payload = {
                    "user_id": user.id,
                    "date": str(date),
                    "exercise": exercise.strip(),
                    "reps": int(reps),
                    "weight": float(weight),
                    "notes": notes.strip() if notes else None,
                }
                if not payload["exercise"]:
                    st.warning("Exercise is required.")
                else:
                    supabase.table("workout_sets").insert(payload).execute()
                    st.success("Set added.")
                    st.rerun()
            except Exception as e:
                st.error(f"Could not add set: {e}")

def list_sets(user):
    st.subheader("Your Workout Sets")
    try:
        query = (
            supabase.table("workout_sets")
            .select("*")
            .eq("user_id", user.id)
            .order("date", desc=True)
            .order("created_at", desc=True)
        )
        data = query.execute().data or []
    except Exception as e:
        st.error(f"Error loading sets: {e}")
        data = []

    if not data:
        st.info("No sets yet. Add your first set above.")
        return

    # Simple table with delete actions
    for row in data:
        with st.container(border=True):
            cols = st.columns([2, 3, 1, 1, 3])
            cols[0].markdown(f"**{row.get('date','')}**")
            cols[1].markdown(f"**{row.get('exercise','')}**")
            cols[2].markdown(f"Reps: **{row.get('reps','')}**")
            cols[3].markdown(f"Weight: **{row.get('weight','')}**")
            cols[4].markdown(row.get("notes") or "")
            del_col = st.columns([8, 2])[1]
            with del_col:
                if st.button("Delete", key=f"del_{row['id']}"):
                    try:
                        supabase.table("workout_sets").delete().eq("id", row["id"]).eq("user_id", user.id).execute()
                        st.success("Deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

# ---------- Render ----------
st.title("🏋️ Workout Tracker")

user = get_current_user()
if not user:
    auth_ui()
else:
    topbar(user)
    add_set_form(user)
    list_sets(user)

# ---------- DB schema note (for reference only) ----------
# Expect a Supabase table named: workout_sets
# Columns (recommended):
# id: uuid primary key default gen_random_uuid()
# user_id: uuid (index) -> references auth.users(id)
# date: date not null
# exercise: text not null
# reps: int4 not null
# weight: float8 not null
# notes: text
# created_at: timestamptz default now()





