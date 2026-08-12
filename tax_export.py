# tax_export.py
"""
Tax-ready report generation — deductible expense summaries,
category breakdowns, annual reports in CSV/Excel.
"""
import io
import pandas as pd
import streamlit as st
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from config import Columns
from security_utils import sanitize_df_for_export


# ============================================================
# TAX CATEGORIES (customizable)
# ============================================================
TAX_DEDUCTIBLE_CATEGORIES = [
    "Office Supplies", "Travel", "Transport", "Professional Development",
    "Books", "Software", "Equipment", "Phone", "Internet", "Meals (Business)",
    "Healthcare", "Home Office", "Subscriptions",
]


def mark_deductible(df: pd.DataFrame, deductible_cats: Optional[list] = None) -> pd.DataFrame:
    """Add a 'TaxDeductible' column based on category."""
    cats = deductible_cats or TAX_DEDUCTIBLE_CATEGORIES
    df = df.copy()
    df["TaxDeductible"] = df[Columns.CATEGORY].isin(cats)
    return df


# ============================================================
# REPORT GENERATION
# ============================================================
def generate_annual_report(df: pd.DataFrame, year: int, deductible_cats: Optional[list] = None) -> dict:
    """Generate an annual tax report dictionary."""
    df2 = df.copy()
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    df2 = df2[df2[Columns.DATE].dt.year == year]
    df2 = mark_deductible(df2, deductible_cats)

    if df2.empty:
        return {"year": year, "total": 0, "deductible": 0, "non_deductible": 0, "categories": {}, "monthly": {}}

    total = df2[Columns.PRICE_PAID].sum()
    deductible_df = df2[df2["TaxDeductible"] == True]
    deductible = deductible_df[Columns.PRICE_PAID].sum()

    # Category breakdown
    cat_summary = (
        df2.groupby([Columns.CATEGORY, "TaxDeductible"])[Columns.PRICE_PAID]
        .sum()
        .reset_index()
        .rename(columns={Columns.PRICE_PAID: "Total"})
    )

    # Monthly breakdown
    df2["Month"] = df2[Columns.DATE].dt.strftime("%B")
    df2["MonthNum"] = df2[Columns.DATE].dt.month
    monthly = (
        df2.groupby(["MonthNum", "Month"])[Columns.PRICE_PAID]
        .sum()
        .reset_index()
        .sort_values("MonthNum")
    )

    return {
        "year": year,
        "total": round(total, 2),
        "deductible": round(deductible, 2),
        "non_deductible": round(total - deductible, 2),
        "num_transactions": len(df2),
        "categories_df": cat_summary,
        "monthly_df": monthly,
        "deductible_df": deductible_df,
        "full_df": df2,
    }


def build_excel_report(report: dict) -> bytes:
    """Build a multi-sheet Excel tax report."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Summary sheet
        summary_data = {
            "Metric": ["Year", "Total Expenses (SEK)", "Tax-Deductible (SEK)", "Non-Deductible (SEK)", "# Transactions"],
            "Value": [report["year"], report["total"], report["deductible"], report["non_deductible"], report["num_transactions"]],
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Summary", index=False)

        # All expenses
        if "full_df" in report and not report["full_df"].empty:
            sanitize_df_for_export(report["full_df"]).to_excel(writer, sheet_name="All Expenses", index=False)

        # Deductible expenses
        if "deductible_df" in report and not report["deductible_df"].empty:
            sanitize_df_for_export(report["deductible_df"]).to_excel(writer, sheet_name="Deductible Expenses", index=False)

        # Category breakdown
        if "categories_df" in report and not report["categories_df"].empty:
            sanitize_df_for_export(report["categories_df"]).to_excel(writer, sheet_name="By Category", index=False)

        # Monthly breakdown
        if "monthly_df" in report and not report["monthly_df"].empty:
            sanitize_df_for_export(report["monthly_df"]).to_excel(writer, sheet_name="Monthly Summary", index=False)

    return output.getvalue()


def build_csv_report(report: dict) -> str:
    """Build a simple CSV of deductible expenses."""
    if "deductible_df" in report and not report["deductible_df"].empty:
        return sanitize_df_for_export(report["deductible_df"]).to_csv(index=False)
    return ""


# ============================================================
# UI
# ============================================================
def tax_export_ui(df: pd.DataFrame):
    st.markdown("## 🧾 Tax Report Generator")

    if df.empty:
        st.info("No expense data available to generate reports.")
        return

    df2 = df.copy()
    df2[Columns.DATE] = pd.to_datetime(df2[Columns.DATE], errors="coerce")
    available_years = sorted(df2[Columns.DATE].dt.year.dropna().unique().astype(int).tolist(), reverse=True)
    if not available_years:
        st.warning("No valid dates in data.")
        return

    c1, c2 = st.columns(2)
    year = c1.selectbox("Tax Year", available_years)

    # Deductible category selection
    all_cats = sorted(df[Columns.CATEGORY].dropna().unique().tolist())
    deductible_cats = c2.multiselect(
        "Tax-Deductible Categories",
        all_cats,
        default=[c for c in all_cats if c in TAX_DEDUCTIBLE_CATEGORIES],
        help="Select which categories count as deductible expenses"
    )

    report = generate_annual_report(df, year, deductible_cats)

    # Summary metrics
    st.markdown("---")
    cols = st.columns(4)
    cols[0].metric("📋 Total Expenses", f"{report['total']:,.0f} SEK")
    cols[1].metric("✅ Tax-Deductible", f"{report['deductible']:,.0f} SEK")
    cols[2].metric("❌ Non-Deductible", f"{report['non_deductible']:,.0f} SEK")
    cols[3].metric("📝 Transactions", str(report.get("num_transactions", 0)))

    # Category breakdown table
    if "categories_df" in report and not report["categories_df"].empty:
        st.markdown("### 📊 Category Breakdown")
        cats_df = report["categories_df"].copy()
        cats_df["TaxDeductible"] = cats_df["TaxDeductible"].map({True: "✅ Yes", False: "❌ No"})
        st.dataframe(cats_df.rename(columns={"TaxDeductible": "Deductible?"}), width="stretch", hide_index=True)

    # Monthly chart
    if "monthly_df" in report and not report["monthly_df"].empty:
        st.markdown("### 📅 Monthly Spending")
        st.bar_chart(report["monthly_df"].set_index("Month")[Columns.PRICE_PAID])

    # Download buttons
    st.markdown("---")
    st.markdown("### 💾 Download Reports")
    col1, col2 = st.columns(2)

    with col1:
        excel_data = build_excel_report(report)
        st.download_button(
            "📘 Download Excel Report",
            data=excel_data,
            file_name=f"tax_report_{year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

    with col2:
        csv_data = build_csv_report(report)
        if csv_data:
            st.download_button(
                "📄 Download Deductible CSV",
                data=csv_data.encode("utf-8"),
                file_name=f"deductible_expenses_{year}.csv",
                mime="text/csv",
                width="stretch",
            )
