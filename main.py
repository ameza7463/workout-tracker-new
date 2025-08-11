import datetime
import streamlit as st
from supabase import create_client, Client
from st_cookies_manager import EncryptedCookieManager

# ========= Config =========
st.set_page_config(page_title="Workout Tracker", page_icon="💪", layout="centered")
DEBUG = True  # turn False after it works

# Read from Streamlit Secrets
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = st.secrets.get("SUPABASE_ANON_KEY", "")
COOKIE_PASSWORD = st.secrets.get("COOKIE_PASSWORD", "change-this")
COOKIE_PREFIX = "wtapp_"

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    st.error("Missing SUPABASE_URL or SUPABASE_ANON_KEY in Secrets.")
    st.stop()

# ========= Clients & Cookies =========
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

cookies = EncryptedCookieManager(prefix=COOKIE_PREFIX, password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()  # wait for component to init

def save_tokens_from_session(sess):
    if not sess:
        return
    cookies["access_token"] = sess.access_token
    cookies["refresh_token"] = sess.refresh_token
    cookies.save()

def clear_tokens():
    for k in ("access_token", "refresh_token"):
        if k in cookies:
            del cookies[k]
    cookies.save()

def restore_session():
    at = cookies.get("access_token")
    rt = cookies.get("refresh_token")
    if at and rt:
        try:
            supabase.auth.set_session(at, rt)  # (access, refresh)
            return True
        except Exception as e:
            if DEBUG:
                st.warning(f"restore_session failed: {e}")
            clear_tokens()
    return False

if "session_restored" not in st.session_state:
    st.session_state.session_restored = restore_session()

def get_current_user():
    try:
        return supabase.auth.get_user().user
    except Exception as e:
        if DEBUG:
            st.warning(f"get_user failed: {e}")
        return None

# ========= Auth UI =========
def auth_ui():
    tabs = st.tabs(["Log in", "Sign up"])

    # Login
    with tabs[0]:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")
            if submitted:
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    if DEBUG:
                        st.code(f"AUTH RESPONSE (login): {res}", language="text")
                        st.json({
                            "res.user": getattr(res, "user", None).__dict__ if getattr(res, "user", None) else None,
                            "res.session_present": bool(getattr(res, "session", None)),
                        })
                    if res.session:
                        save_tokens_from_session(res.session)
                        supabase.auth.set_session(res.session.access_token, res.session.refresh_token)
                        st.session_state.session_restored = True
                        st.success("Logged in.")
                        st.rerun()
                    else:
                        st.error("No session returned. Check email confirmation setting or password.")
                except Exception as e:
                    st.error(f"Login failed: {e}")

    # Signup
    with tabs[1]:
        with st.form("signup_form"):
            email = st.text_input("Email", key="su_email")
            password = st.text_input("Password (min 6 chars)", type="password", key="su_pw")
            submitted = st.form_submit_button("Create account")
            if submitted:
                try:
                    res = supabase.auth.sign_up({"email": email, "password": password})
                    if DEBUG:
                        st.code(f"AUTH RESPONSE (signup): {res}", language="text")
                        st.json({
                            "res.user": getattr(res, "user", None).__dict__ if getattr(res, "user", None) else None,
                            "res.session_present": bool(getattr(res, "session", None)),
                        })
                    if getattr(res, "session", None):
                        save_tokens_from_session(res.session)
                        supabase.auth.set_session(res.session.access_token, res.session.refresh_token)
                        st.session_state.session_restored = True
                        st.success("Account created and logged in.")
                        st.rerun()
                    else:
                        st.success("Account created. Check your email to confirm or turn OFF ‘Confirm email’.")
                except Exception as e:
                    st.error(f"Sign up failed: {e}")

# ========= App UI =========
def topbar(user):
    cols = st.columns([2, 2, 1, 1])
    with cols[0]:
        st.caption("Signed in as")
        st.write(f"**{user.email}**")
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
                    supabase.table("workout_sets").insert({
                        "user_id": user.id,
                        "date": str(date),
                        "exercise": exercise.strip(),
                        "reps": int(reps),
                        "weight": float(weight),
                        "notes": notes.strip() if notes else None,
                    }).execute()
                    st.success("Set added.")
                    st.rerun()
            except Exception as e:
                st.error(f"Could not add set: {e}")

def list_sets(user):
    st.subheader("Your Workout Sets")
    try:
        data = (supabase.table("workout_sets")
                .select("*")
                .eq("user_id", user.id)
                .order("date", desc=True)
                .order("created_at", desc=True)
                .execute().data) or []
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
                        supabase.table("workout_sets").delete().eq("id", row["id"]).eq("user_id", user.id).execute()
                        st.success("Deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

# ========= Render =========
st.title("🏋️ Workout Tracker")

user = get_current_user()

if DEBUG:
    st.caption("🔎 Debug")
    st.json({
        "cookie_has_access_token": bool(cookies.get("access_token")),
        "cookie_has_refresh_token": bool(cookies.get("refresh_token")),
        "session_restored_flag": st.session_state.get("session_restored"),
        "current_user_email": getattr(user, "email", None),
    })

if not user:
    auth_ui()
else:
    topbar(user)
    add_set_form(user)
    list_sets(user)







