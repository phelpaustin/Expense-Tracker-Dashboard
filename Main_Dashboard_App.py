# Main_Dashboard_App.py  (Expense Dashboard - default launch page)
import streamlit as st
import pandas as pd
from datetime import datetime

from config import USE_GOOGLE_SHEETS
from data_manager import init_storage, load_data, save_data, bump_data_version
from ui_components import sidebar_add_expense, filter_section, theme_css
from charts import kpi_row, category_pie
from import_export import import_button, export_buttons


# ----------------- PAGE SETUP -----------------
st.set_page_config(page_title="💰 Expense Dashboard", layout="wide")

# --- Theme ---
dark_mode = st.sidebar.checkbox("🌗 Dark mode", value=False)
theme_css(dark_mode)

st.title("💰 Expense Dashboard")


# ----------------- DATA LOAD -----------------
sheet = init_storage()
version = st.session_state.get("data_version", 0)
df = load_data(_sheet=sheet, version=version)


# ----------------- LOGGING HELPER -----------------
def log(msg):
    """Display logs in the sidebar for debugging."""
    st.sidebar.text(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ----------------- SIDEBAR FEATURES -----------------
sidebar_add_expense(df, lambda d: save_data(d, sheet))
df_filtered = filter_section(df)
imported_df = import_button(existing_columns=df.columns.tolist() if not df.empty else None)


# ----------------- IMPORT + MERGE HANDLING -----------------
log("Import check start")

# Step 1: If import_button signaled ready_to_merge, store it persistently
if imported_df is not None:
    st.session_state["pending_import_df"] = imported_df
    st.session_state["merge_ready"] = True
    log(f"✅ {len(imported_df)} rows ready to merge.")

# Step 2: If merge_ready flag is set, perform the merge
if st.session_state.get("merge_ready", False):
    pending_df = st.session_state.get("pending_import_df", pd.DataFrame())

    if pending_df is not None and not pending_df.empty:
        log(f"🚀 Starting merge process with {len(pending_df)} rows.")
        try:
            # Merge into existing dataset
            df_combined = pd.concat([df, pending_df], ignore_index=True)
            log(f"✅ Merge complete: {len(df)} → {len(df_combined)} rows.")

            # Save to sheet or local CSV
            save_data(df_combined, sheet)
            log("💾 Data saved via save_data().")

            # Invalidate cache and refresh
            st.cache_data.clear()
            bump_data_version()
            st.success("✅ Imported data merged successfully!")

            # Clean up session state AFTER save
            st.session_state.pop("merge_ready", None)
            st.session_state.pop("pending_import_df", None)

            # Force rerun
            st.rerun()

        except Exception as e:
            st.error(f"❌ Merge failed: {e}")
            log(f"❌ Exception: {e}")
    else:
        log("⚠️ No data in pending_import_df to merge.")
else:
    log("⏸️ Waiting for user to confirm import.")


# ----------------- EXPORT BUTTONS -----------------
export_buttons(df)


# ----------------- INCOMPLETE ENTRIES HANDLER -----------------
missing_critical = df[
    df["Date"].isna() | (df["Date"] == "") |
    df["ExpenseType"].isna() | (df["ExpenseType"] == "")
]

if not missing_critical.empty:
    with st.expander(f"⚠️ {len(missing_critical)} Incomplete Entries — Click to Review", expanded=False):
        st.warning(
            "Some entries are missing **Date** or **Expense Type**. "
            "These records are excluded from charts and filters until fixed."
        )

        editable_missing = st.data_editor(
            missing_critical,
            num_rows="dynamic",
            use_container_width=True,
            key="edit_missing_entries"
        )

        if st.button("💾 Save Fixed Entries", use_container_width=True):
            # Remove old incomplete rows
            df = df.drop(missing_critical.index)
            # Add updated entries
            df = pd.concat([df, editable_missing], ignore_index=True)
            save_data(df, sheet)
            bump_data_version()
            st.success("✅ Fixed entries saved successfully!")
            st.rerun()
else:
    st.sidebar.success("✅ No incomplete entries found.")


# ----------------- MAIN DASHBOARD -----------------
st.markdown("## 📈 Overview")
kpi_row(df_filtered)

# --- Auto-fix: Clean up Date and compute missing PricePerUnit ---
df_filtered["Date"] = pd.to_datetime(df_filtered["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

if "PricePerUnit" in df_filtered.columns:
    df_filtered["PricePerUnit"] = df_filtered.apply(
        lambda r: r["PricePaid"] / r["Quantity"]
        if pd.notna(r.get("Quantity")) and r.get("Quantity") not in [0, None, ""] and pd.isna(r.get("PricePerUnit"))
        else r.get("PricePerUnit"),
        axis=1
    )

# --- Expenses by Month Section ---
st.markdown("### 📅 Expenses by Month")

if not df_filtered.empty:
    df_filtered["Date"] = pd.to_datetime(df_filtered["Date"], errors="coerce")
    years = sorted(df_filtered["Date"].dt.year.dropna().unique().tolist(), reverse=True)
    months = sorted(df_filtered["Date"].dt.month.dropna().unique().tolist())

    # Two filters side by side
    col_year, col_month = st.columns([1, 1])
    with col_year:
        selected_year = st.selectbox("Select Year", years)
    with col_month:
        month_names = ["All"] + [pd.Timestamp(2000, m, 1).strftime("%B") for m in months]
        selected_month = st.selectbox("Select Month", month_names)

    # Apply filters
    df_filtered = df_filtered[df_filtered["Date"].dt.year == selected_year]
    if selected_month != "All":
        month_num = pd.to_datetime(selected_month, format="%B").month
        df_filtered = df_filtered[df_filtered["Date"].dt.month == month_num]

    # Drop Year column if present
    df_filtered = df_filtered.drop(columns=[c for c in ["Year"] if c in df_filtered.columns], errors="ignore")

    # Final clean Date display
    df_filtered["Date"] = df_filtered["Date"].dt.strftime("%Y-%m-%d")

    st.dataframe(df_filtered, use_container_width=True)
else:
    st.info("No expense records available yet.")

# ----------------- PIE CHART -----------------
st.markdown("## 🥧 Spending Breakdown")
category_pie(df_filtered)


# ----------------- NAVIGATION BUTTONS -----------------
st.sidebar.markdown("---")
if st.sidebar.button("➡️ Go to Analytics Page"):
    st.switch_page("pages/Analytics_and_Trends.py")

if st.sidebar.button("✏️ Edit / Delete Entries"):
    st.switch_page("pages/Edit_or_Delete.py")
