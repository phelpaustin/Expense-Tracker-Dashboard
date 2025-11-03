# import_export.py
import streamlit as st
import pandas as pd
from io import BytesIO

# ============================================================
# 📥 Import Expense Data (CSV / XLSX) with Preview + Edit + Merge
# ============================================================
def import_button(existing_columns=None):
    st.sidebar.subheader("📥 Import Data")
    uploaded_file = st.sidebar.file_uploader("Upload a CSV or Excel file", type=["csv", "xlsx"])

    if not uploaded_file:
        return None

    try:
        if uploaded_file.name.endswith(".csv"):
            df_import = pd.read_csv(uploaded_file)
        else:
            df_import = pd.read_excel(uploaded_file)
    except Exception as e:
        st.sidebar.error(f"⚠️ Failed to read file: {e}")
        return None

    if df_import.empty:
        st.sidebar.warning("⚠️ Uploaded file is empty.")
        return None

    expected_cols = existing_columns or [
        "Date", "ExpenseType", "Category", "Subcategory", "Item", "Brand",
        "Shop", "PricePaid", "Currency", "Quantity", "QuantityUnit", "PricePerUnit"
    ]

    for col in expected_cols:
        if col not in df_import.columns:
            df_import[col] = None

    df_import = df_import[expected_cols]
    df_import["Date"] = pd.to_datetime(df_import["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

    st.markdown("### 👀 Preview Imported Data (Editable)")
    editable_df = st.data_editor(df_import, num_rows="dynamic", width="stretch")

    if st.button("✅ Merge into Main Dataset", width="stretch"):
        st.session_state["pending_import_df"] = editable_df
        st.session_state["merge_ready"] = True
        st.toast("Data ready to merge.")
        st.sidebar.write("🧩 Import flagged for merge.")
        # no rerun here — merge happens in main script
        return editable_df

    return None


# ============================================================
# 📤 Export Buttons (CSV / Excel)
# ============================================================
def export_buttons(df):
    """Provide buttons to export filtered or full dataset."""
    st.sidebar.subheader("📤 Export Data")

    # --- CSV Export ---
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button(
        label="💾 Download CSV",
        data=csv_data,
        file_name="expenses_export.csv",
        mime="text/csv",
    )

    # --- Excel Export ---
    try:
        output = BytesIO()
        df.to_excel(output, index=False, sheet_name="Expenses")
        st.sidebar.download_button(
            label="📘 Download Excel",
            data=output.getvalue(),
            file_name="expenses_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        st.sidebar.warning(f"Excel export unavailable: {e}")
