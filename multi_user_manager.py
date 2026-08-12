# multi_user_manager.py
"""
Multi-user support — user profiles, shared expenses, split tracking.
"""
import json
import hmac
import hashlib
import secrets
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from config import Columns


USERS_FILE = "data/users.json"
DEFAULT_USERS = [
    {"id": "user_1", "name": "Owner", "color": "#6366f1", "role": "admin", "password_hash": None}
]

from json_store import JsonStore
_USERS_STORE = JsonStore(USERS_FILE, default=DEFAULT_USERS, sync=False)


# ============================================================
# STORAGE
# ============================================================
def load_users() -> list:
    return _USERS_STORE.load()


def save_users(users: list):
    _USERS_STORE.save(users)


def _pbkdf2(password: str, salt: str) -> bytes:
    """Derive a PBKDF2-HMAC-SHA256 key (the CPU-heavy primitive)."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=260_000,
    )


# A single shared worker thread runs the ~100 ms PBKDF2 derivation off the
# Streamlit script-run thread.  ``hashlib.pbkdf2_hmac`` releases the GIL while
# it computes, so offloading keeps the server responsive to other concurrent
# user sessions during login / signup instead of blocking the whole process.
# We still ``.result()`` because the caller needs the hash synchronously.
_hash_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pbkdf2")


def _derive_key(password: str, salt: str) -> bytes:
    return _hash_executor.submit(_pbkdf2, password, salt).result()


def hash_password(password: str) -> str:
    """
    Hash a password with a random per-user salt using PBKDF2-HMAC-SHA256.

    The returned string has the format ``{salt_hex}:{derived_key_hex}`` so
    both pieces are stored together in a single ``password_hash`` field.
    260 000 iterations matches NIST SP 800-132 (2023) guidance.

    NOTE: the derivation costs ~100 ms by design; it is run on a shared worker
    thread (see :data:`_hash_executor`) so it does not stall other sessions.
    """
    salt = secrets.token_hex(32)          # 32 bytes → 64 hex chars
    key = _derive_key(password, salt)
    return f"{salt}:{key.hex()}"



def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify *password* against *stored_hash*.

    Supports two formats:
    - **New** (PBKDF2 + salt): ``"{salt_hex}:{key_hex}"`` — produced by
      :func:`hash_password` above.
    - **Legacy** (plain SHA-256, no colon): kept for backward-compatibility
      so existing users are not locked out.  Any legacy hash is accepted but
      the account should be re-hashed on next successful login if desired.
    """
    if not stored_hash:
        return False

    if ":" in stored_hash:
        # New PBKDF2 format
        try:
            salt, key_hex = stored_hash.split(":", 1)
            expected = _derive_key(password, salt)
            # Use hmac.compare_digest to prevent timing attacks
            return hmac.compare_digest(expected.hex(), key_hex)
        except Exception:
            return False
    else:
        # Legacy plain SHA-256 format (no salt)
        legacy_hash = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(legacy_hash, stored_hash)


def get_user_by_id(user_id: str) -> Optional[dict]:
    return next((u for u in load_users() if u["id"] == user_id), None)


# ============================================================
# USER MANAGEMENT
# ============================================================
def add_user(name: str, role: str = "member", color: str = "#64748b", password: str = "") -> str:
    users = load_users()
    user_id = f"user_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    users.append({
        "id": user_id, "name": name.strip(), "role": role,
        "color": color, "password_hash": hash_password(password) if password else None,
        "created": str(datetime.now().date())
    })
    save_users(users)
    return user_id


def delete_user(user_id: str):
    users = [u for u in load_users() if u["id"] != user_id]
    save_users(users)


def authenticate_user(name: str, password: str) -> Optional[dict]:
    users = load_users()
    for user in users:
        if user["name"] == name:
            stored = user.get("password_hash")
            if stored is None:
                return user
            if verify_password(password, stored):
                # Transparently upgrade legacy unsalted SHA-256 hashes to the
                # current PBKDF2 format on successful login so old records do
                # not linger in a weaker format.
                if ":" not in stored:
                    user["password_hash"] = hash_password(password)
                    save_users(users)
                return user
    return None


# ============================================================
# SESSION USER
# ============================================================
def get_current_user() -> Optional[dict]:
    return st.session_state.get("current_user")


def set_current_user(user: dict):
    st.session_state["current_user"] = user


def logout():
    if "current_user" in st.session_state:
        del st.session_state["current_user"]


def require_login():
    """Show login wall if not authenticated. Returns True if logged in."""
    user = get_current_user()
    if user:
        return True

    users = load_users()
    if len(users) == 1 and users[0].get("password_hash") is None:
        set_current_user(users[0])
        return True

    st.markdown("## 👤 Sign In")
    names = [u["name"] for u in users]
    selected_name = st.selectbox("Select User", names)
    password = st.text_input("Password (leave blank if not set)", type="password")

    # Simple in-session throttling to slow down password guessing.
    attempts = st.session_state.get("_login_attempts", 0)
    locked_until = st.session_state.get("_login_locked_until")
    now = datetime.now()
    if locked_until and now < locked_until:
        wait = int((locked_until - now).total_seconds())
        st.error(f"🔒 Too many failed attempts. Try again in {wait}s.")
        return False

    if st.button("Sign In", type="primary"):
        result = authenticate_user(selected_name, password)
        if result:
            st.session_state["_login_attempts"] = 0
            st.session_state.pop("_login_locked_until", None)
            set_current_user(result)
            st.rerun()
        else:
            attempts += 1
            st.session_state["_login_attempts"] = attempts
            if attempts >= 5:
                st.session_state["_login_locked_until"] = now + timedelta(seconds=30)
                st.session_state["_login_attempts"] = 0
                st.error("🔒 Too many failed attempts. Locked for 30s.")
            else:
                st.error(f"❌ Incorrect password ({5 - attempts} attempt(s) left)")

    return False


# ============================================================
# EXPENSE ATTRIBUTION
# ============================================================
def tag_expense_with_user(row: dict) -> dict:
    user = get_current_user()
    if user:
        row["AddedBy"] = user["name"]
        row["UserId"] = user["id"]
    return row


def filter_by_user(df: pd.DataFrame, user_id: Optional[str] = None) -> pd.DataFrame:
    if df.empty or "UserId" not in df.columns:
        return df
    if user_id is None:
        return df
    return df[df["UserId"] == user_id]


# ============================================================
# SPLIT TRACKING
# ============================================================
def calculate_user_splits(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate how much each user has spent."""
    if df.empty or "AddedBy" not in df.columns:
        return pd.DataFrame()
    return (
        df.groupby("AddedBy")[Columns.PRICE_PAID]
        .agg(["sum", "count"])
        .reset_index()
        .rename(columns={"AddedBy": "User", "sum": "Total (SEK)", "count": "# Expenses"})
        .sort_values("Total (SEK)", ascending=False)
    )


def calculate_fair_share(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate who owes whom for shared expenses."""
    if df.empty or "AddedBy" not in df.columns:
        return pd.DataFrame()
    splits = calculate_user_splits(df)
    if splits.empty:
        return pd.DataFrame()
    total = splits["Total (SEK)"].sum()
    n_users = len(splits)
    fair_share = total / n_users if n_users > 0 else 0
    splits["Fair Share (SEK)"] = fair_share
    splits["Balance (SEK)"] = splits["Total (SEK)"] - fair_share
    splits["Owes / Gets"] = splits["Balance (SEK)"].apply(
        lambda x: f"Gets back {abs(x):,.0f} SEK" if x < -1 else (f"Owes {abs(x):,.0f} SEK" if x > 1 else "Settled ✅")
    )
    return splits


# ============================================================
# UI
# ============================================================
def user_management_ui():
    """Admin panel for user management."""
    st.markdown("## 👥 User Management")
    users = load_users()
    current = get_current_user()

    # User list
    st.markdown("### Current Users")
    for u in users:
        is_me = current and u["id"] == current["id"]
        badge = " 👤 **(You)**" if is_me else ""
        with st.expander(f"{u['name']} — {u['role']}{badge}"):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Role:** {u['role']}")
            c2.markdown(f"**Color:** {u['color']}")
            c3.markdown(f"**Created:** {u.get('created', '—')}")
            if not is_me and current and current.get("role") == "admin":
                if st.button(f"🗑️ Remove {u['name']}", key=f"del_user_{u['id']}"):
                    delete_user(u["id"])
                    st.rerun()

    # Add user
    st.markdown("### ➕ Add New User")
    with st.form("add_user_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name *")
        role = c2.selectbox("Role", ["member", "admin", "viewer"])
        color = c1.color_picker("Color", "#6366f1")
        password = c2.text_input("Password (optional)", type="password")

        if st.form_submit_button("Add User", type="primary"):
            if name.strip():
                add_user(name, role, color, password)
                st.success(f"✅ Added user: {name}")
                st.rerun()
            else:
                st.error("Name is required")


def user_splits_ui(df: pd.DataFrame):
    """Display spending splits and balances."""
    st.markdown("## 💸 Shared Expense Splits")
    if "AddedBy" not in df.columns or df["AddedBy"].dropna().empty:
        st.info("No user-attributed expenses yet. Expenses will be attributed once multiple users are active.")
        return

    splits = calculate_user_splits(df)
    fair_share_df = calculate_fair_share(df)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📊 Spending by User")
        st.dataframe(splits, width="stretch", hide_index=True)
    with col2:
        st.markdown("### ⚖️ Balance Sheet")
        st.dataframe(fair_share_df[["User", "Balance (SEK)", "Owes / Gets"]], width="stretch", hide_index=True)


def user_switcher_widget():
    """Compact user switcher for sidebar."""
    user = get_current_user()
    users = load_users()

    if not user:
        if st.sidebar.button("🔓 Sign In"):
            st.session_state["show_login"] = True
        return

    st.sidebar.markdown(f"**👤 {user['name']}**")
    if len(users) > 1:
        names = [u["name"] for u in users if u["id"] != user["id"]]
        switch_to = st.sidebar.selectbox("Switch User", ["—"] + names, key="user_switch")
        if switch_to != "—":
            target = next((u for u in users if u["name"] == switch_to), None)
            if target and target.get("password_hash") is None:
                set_current_user(target)
                st.rerun()
    if st.sidebar.button("🚪 Logout"):
        logout()
        st.rerun()