# Main_Dashboard_App.py  (Expense Dashboard - default launch page)
import streamlit as st
import pandas as pd
from datetime import datetime

from config import USE_GOOGLE_SHEETS, DEFAULT_CURRENCY
from data_manager import init_storage, load_data, save_data, bump_data_version, clean_data
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

# Normalize Date column (datetime -> date only)
if not df.empty and "Date" in df.columns:
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date

# Ensure expected columns exist
expected_cols = ["Date", "ExpenseType", "PricePaid", "Quantity", "PricePerUnit"]
for c in expected_cols:
    if c not in df.columns:
        df[c] = None

# Reset merge flags on normal load
if st.session_state.get("merge_complete", False):
    st.session_state.pop("merge_complete", None)
if st.session_state.get("merge_complete_flagged", False):
    st.session_state.pop("merge_complete_flagged", None)


# ----------------- LOGGING HELPER -----------------
def log(msg):
    st.sidebar.text(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ----------------- SIDEBAR FEATURES -----------------
sidebar_add_expense(df, lambda d: save_data(d, sheet))
df_filtered = filter_section(df)


# ----------------- IMPORT + MERGE HANDLING -----------------
log("Import check start")

# Control import preview visibility
show_import_ui = not st.session_state.get("merge_complete", False) and not st.session_state.get("merge_complete_flagged", False)

if show_import_ui:
    imported_df = import_button(existing_columns=df.columns.tolist() if not df.empty else None)

    if imported_df is not None and not imported_df.empty:
        # Normalize Date column
        if "Date" in imported_df.columns:
            imported_df["Date"] = pd.to_datetime(imported_df["Date"], errors="coerce").dt.date

        st.session_state["pending_import_df"] = imported_df
        st.session_state["merge_ready"] = True
        log(f"✅ {len(imported_df)} rows ready to merge.")

        # Show preview
        st.subheader("📄 Preview Imported Data")
        st.dataframe(imported_df, use_container_width=True)
else:
    if st.session_state.get("merge_complete", False):
        st.sidebar.success("✅ Last import merged successfully.")


# Perform merge
if st.session_state.get("merge_ready", False):
    pending_df = st.session_state.get("pending_import_df", pd.DataFrame())
    if not pending_df.empty:
        try:
            log(f"🚀 Starting merge process with {len(pending_df)} rows.")
            df_combined = pd.concat([df, pending_df], ignore_index=True)
            df_combined = clean_data(df_combined)
            save_data(df_combined, sheet)
            st.cache_data.clear()
            bump_data_version()
            st.success("✅ Imported data merged successfully!")

            # Cleanup session
            st.session_state.pop("merge_ready", None)
            st.session_state.pop("pending_import_df", None)

            # Flag to prevent import preview during rerun
            st.session_state["merge_complete_flagged"] = True
            st.session_state["merge_complete"] = True

            # Force immediate rerun to remove preview
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
if not df.empty and all(c in df.columns for c in ["Date", "ExpenseType"]):
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
                df = df.drop(missing_critical.index)
                df = pd.concat([df, editable_missing], ignore_index=True)
                save_data(df, sheet)
                bump_data_version()
                st.success("✅ Fixed entries saved successfully!")
                st.rerun()
    else:
        st.sidebar.success("✅ No incomplete entries found.")
else:
    st.sidebar.info("ℹ️ No data or missing expected columns yet.")


# ----------------- MAIN DASHBOARD -----------------
st.markdown("## 📈 Overview")
if not df_filtered.empty:
    kpi_row(df_filtered)
else:
    st.info("No data to display KPIs yet.")


# --- Auto-fix Date and compute PricePerUnit ---
if "Date" in df_filtered.columns:
    df_filtered["Date"] = pd.to_datetime(df_filtered["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

if {"PricePaid", "Quantity", "PricePerUnit"}.issubset(df_filtered.columns):
    df_filtered["PricePerUnit"] = df_filtered.apply(
        lambda r: (
            r["PricePaid"] / r["Quantity"]
            if pd.notna(r.get("Quantity"))
            and r.get("Quantity") not in [0, None, ""]
            and pd.isna(r.get("PricePerUnit"))
            else r.get("PricePerUnit")
        ),
        axis=1
    )


# ----------------- EXPENSES BY MONTH -----------------
st.markdown("### 📅 Expenses by Month")
if not df_filtered.empty and "Date" in df_filtered.columns:
    df_filtered["Date"] = pd.to_datetime(df_filtered["Date"], errors="coerce")
    if df_filtered["Date"].notna().any():
        years = sorted(df_filtered["Date"].dt.year.dropna().unique().tolist(), reverse=True)
        months = sorted(df_filtered["Date"].dt.month.dropna().unique().tolist())

        col_year, col_month = st.columns([1, 1])
        with col_year:
            selected_year = st.selectbox("Select Year", years)
        with col_month:
            month_names = ["All"] + [pd.Timestamp(2000, m, 1).strftime("%B") for m in months]
            selected_month = st.selectbox("Select Month", month_names)

        df_filtered = df_filtered[df_filtered["Date"].dt.year == selected_year]
        if selected_month != "All":
            month_num = pd.to_datetime(selected_month, format="%B").month
            df_filtered = df_filtered[df_filtered["Date"].dt.month == month_num]

        df_filtered["Date"] = df_filtered["Date"].dt.strftime("%Y-%m-%d")
        st.dataframe(df_filtered, use_container_width=True)
    else:
        st.info("No valid dates found in dataset.")
else:
    st.info("No expense records available yet.")


# ----------------- PIE CHART -----------------
st.markdown("## 🥧 Spending Breakdown")
if not df_filtered.empty:
    category_pie(df_filtered)
else:
    st.info("No spending data to visualize yet.")


# ----------------- NAVIGATION BUTTONS -----------------
st.sidebar.markdown("---")
if st.sidebar.button("➡️ Go to Analytics Page"):
    st.switch_page("pages/Analytics_and_Trends.py")

if st.sidebar.button("✏️ Edit / Delete Entries"):
    st.switch_page("pages/Edit_or_Delete.py")
