import datetime
import streamlit as st
from supabase import create_client, Client
from st_cookies_manager import EncryptedCookieManager

# ==============================
# App config
# ==============================
st.set_page_config(page_title="Workout Tracker", page_icon="💪", layout="centered")
DEBUG = True  # set to False after everything works

# ==============================
# Secrets (Streamlit Cloud → Settings → Secrets)
# ==============================
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY", "")
COOKIE_PASSWORD = st.secrets.get("COOKIE_PASSWORD", "change-this")
COOKIE_PREFIX = "wtapp_"  # prevents clashes between apps

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("Missing SUPABASE_URL or SUPABASE_ANON_KEY in Secrets.")
    st.stop()

# ==============================
# Supabase client + Cookies
# ==============================
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def _bind_postgrest_jwt(access_token: str):
    """Ensure PostgREST calls (table/select/insert) carry the auth header."""
    try:
        supabase.postgrest.auth(access_token)
    except Exception as e:
        if DEBUG:
            st.warning(f"postgrest auth bind failed: {e}")

cookies = EncryptedCookieManager(prefix=COOKIE_PREFIX, password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()  # wait for component to initialize

def save_tokens_from_session(sess):
    """Persist tokens in cookie and bind JWT to PostgREST."""
    if not sess:
        return
    cookies["access_token"] = sess.access_token
    cookies["refresh_token"] = sess.refresh_token
    cookies.save()
    _bind_postgrest_jwt(sess.access_token)

def clear_tokens():
    for k in ("access_token", "refresh_token"):
        if k in cookies:
            del cookies[k]
    cookies.save()
    for k in ("user_id", "user_email"):
        if k in st.session_state:
            del st.session_state[k]

def restore_session():
    """Restore Supabase session from cookie and bind JWT."""
    at = cookies.get("access_token")
    rt = cookies.get("refresh_token")
    if at and rt:
        try:
            supabase.auth.set_session(at, rt)  # v2: (access, refresh)
            _bind_postgrest_jwt(at)
            return True
        except Exception as e:
            if DEBUG:
                st.warning(f"restore_session failed: {e}")
            clear_tokens()
    return False

if "session_restored" not in st.session_state:
    st.session_state.session_restored = restore_session()

# ==============================
# Current user (cached)
# ==============================
def get_current_user():
    uid = st.session_state.get("user_id")
    email = st.session_state.get("user_email")
    if uid and email:
        return {"id": uid, "email": email}
    # Fallback: ask Supabase once
    try:
        res = supabase.auth.get_user()
        user = getattr(res, "user", None)
        if user and getattr(user, "id", None):
            st.session_state["user_id"] = user.id
            st.session_state["user_email"] = user.email
            return {"id": user.id, "email": user.email}
    except Exception as e:
        if DEBUG:
            st.warning(f"get_user failed: {e}")
    return None

# ==============================
# Auth UI
# ==============================
def auth_ui():
    tabs = st.tabs(["Log in", "Sign up"])

    # ---- Log in ----
    with tabs[0]:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")
            if submitted:
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    if DEBUG:
                        st.caption("AUTH RESPONSE (login)")
                        st.json({
                            "res_user_email": getattr(getattr(res, "user", None), "email", None),
                            "session_present": bool(getattr(res, "session", None)),
                        })
                    if getattr(res, "session", None):
                        save_tokens_from_session(res.session)
                        supabase.auth.set_session(res.session.access_token, res.session.refresh_token)
                        user = getattr(res, "user", None)
                        if user:
                            st.session_state["user_id"] = user.id
                            st.session_state["user_email"] = user.email
                        st.session_state.session_restored = True
                        st.success("Logged in.")
                        st.rerun()
                    else:
                        st.error("No session returned. If email confirmation is ON, confirm it or turn it OFF (Auth → Providers).")
                except Exception as e:
                    st.error(f"Login failed: {e}")

    # ---- Sign up ----
    with tabs[1]:
        with st.form("signup_form"):
            email = st.text_input("Email", key="su_email")
            password = st.text_input("Password (min 6 chars)", type="password", key="su_pw")
            submitted = st.form_submit_button("Create account")
            if submitted:
                try:
                    res = supabase.auth.sign_up({"email": email, "password": password})
                    if DEBUG:
                        st.caption("AUTH RESPONSE (signup)")
                        st.json({
                            "res_user_email": getattr(getattr(res, "user", None), "email", None),
                            "session_present": bool(getattr(res, "session", None)),
                        })
                    if getattr(res, "session", None):
                        save_tokens_from_session(res.session)
                        supabase.auth.set_session(res.session.access_token, res.session.refresh_token)
                        user = getattr(res, "user", None)
                        if user:
                            st.session_state["user_id"] = user.id
                            st.session_state["user_email"] = user.email
                        st.session_state.session_restored = True
                        st.success("Account created and logged in.")
                        st.rerun()
                    else:
                        st.success("Account created. Check your email to confirm, or turn OFF confirmation while testing.")
                except Exception as e:
                    st.error(f"Sign up failed: {e}")

# ==============================
# App UI
# ==============================
def topbar(user):
    cols = st.columns([2, 2, 1, 1])
    with cols[0]:
        st.caption("Signed in as")
        st.write(f"**{user['email']}**")
    with cols[2]:
        if st.button("Refresh"):
            st.rerun()
    with cols[3]:
        if st.button("Log out"):
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
        notes = st.text_area("Notes (optional)")
        submitted = st.form_submit_button("Add set")
        if submitted:
            try:
                if not exercise.strip():
                    st.warning("Exercise is required.")
                else:
                    # DO NOT send user_id; DB default uses auth.uid()
                    payload = {
                        "date": date.isoformat(),                     # string for JSON
                        "exercise": exercise.strip(),
                        "reps": int(reps),
                        "weight": float(weight),
                        "notes": notes.strip() if notes else None,
                    }
                    supabase.table("workout_sets").insert(payload).execute()
                    st.success("Set added.")
                    st.rerun()
            except Exception as e:
                st.error(f"Could not add set: {e}")

def list_sets(user):
    st.subheader("Your Workout Sets")
    try:
        data = (
            supabase.table("workout_sets")
            .select("*")
            .order("date", desc=True)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    except Exception as e:
        st.error(f"Error loading sets: {e}")
        data = []

    if not data:
        st.info("No sets yet. Add your first set above.")
        return

    for row in data:
        with st.container(border=True):
            cols = st.columns([2, 3, 1, 1, 3])
            cols[0].markdown(f"**{row.get('date','')}**")
            cols[1].markdown(f"**{row.get('exercise','')}**")
            cols[2].markdown(f"Reps: **{row.get('reps','')}**")
            cols[3].markdown(f"Weight: **{row.get('weight','')}**")
            cols[4].markdown(row.get("notes") or "")
            btn_col = st.columns([8, 2])[1]
            with btn_col:
                if st.button("Delete", key=f"del_{row['id']}"):
                    try:
                        supabase.table("workout_sets").delete().eq("id", row["id"]).execute()
                        st.success("Deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

# ==============================
# Render
# ==============================
st.title("🏋️ Workout Tracker")

user = get_current_user()

# Small debug panel to verify session/cookies
if DEBUG:
    st.caption("🔎 Debug")
    st.json({
        "cookie_has_access_token": bool(cookies.get("access_token")),
        "cookie_has_refresh_token": bool(cookies.get("refresh_token")),
        "session_restored_flag": st.session_state.get("session_restored"),
        "cached_user_email": st.session_state.get("user_email"),
        "cached_user_id": st.session_state.get("user_id"),
    })

if not user:
    auth_ui()
else:
    topbar(user)
    add_set_form(user)
    list_sets(user)






