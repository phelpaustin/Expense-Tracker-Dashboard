# import_export.py
import streamlit as st
from data_manager import import_data, export_data_bytes

def import_button():
    uploaded = st.sidebar.file_uploader("Upload CSV/XLSX", type=["csv", "xlsx"])
    if uploaded:
        df = import_data(uploaded)
        st.sidebar.success("File imported (preview below).")
        st.dataframe(df.head())
        return df
    return None

def export_buttons(df):
    if df.empty:
        st.sidebar.info("No data to export.")
        return
    csv_bytes, csv_mime = export_data_bytes(df, "csv")
    st.sidebar.download_button("⬇️ Download CSV", data=csv_bytes, file_name="expenses.csv", mime=csv_mime)

    xlsx_bytes, xlsx_mime = export_data_bytes(df, "xlsx")
    st.sidebar.download_button("⬇️ Download Excel", data=xlsx_bytes, file_name="expenses.xlsx", mime=xlsx_mime)
