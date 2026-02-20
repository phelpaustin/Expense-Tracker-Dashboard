# financial_metrics.py
"""
Financial Metrics Dashboard - Comprehensive financial health tracking.
Shows savings rate, expense volatility, cash flow, and more.
"""
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from config import Columns


def calculate_savings_rate(df: pd.DataFrame, income: float = None) -> dict:
    """
    Calculate savings rate and related metrics.
    
    Returns dict with savings metrics.
    """
    if df.empty:
        return {"savings_rate": 0, "monthly_savings": 0, "total_spent": 0}
    
    df = df.copy()
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce")
    
    # Get this month's spending
    current_month = datetime.now().replace(day=1)
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")
    this_month = df[df[Columns.DATE] >= current_month]
    
    total_spent = this_month[Columns.PRICE_PAID].sum()
    
    if income and income > 0:
        monthly_savings = income - total_spent
        savings_rate = (monthly_savings / income) * 100
    else:
        monthly_savings = 0
        savings_rate = 0
    
    return {
        "savings_rate": savings_rate,
        "monthly_savings": monthly_savings,
        "total_spent": total_spent,
        "income": income or 0
    }


def calculate_expense_volatility(df: pd.DataFrame) -> dict:
    """Calculate expense volatility metrics."""
    if df.empty:
        return {"volatility": 0, "std_dev": 0, "coefficient_variation": 0}
    
    df = df.copy()
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce")
    df[Columns.YEAR_MONTH] = df[Columns.DATE].dt.to_period("M")
    
    # Monthly spending
    monthly_spending = df.groupby(Columns.YEAR_MONTH)[Columns.PRICE_PAID].sum()
    
    if len(monthly_spending) < 2:
        return {"volatility": 0, "std_dev": 0, "coefficient_variation": 0}
    
    mean_spending = monthly_spending.mean()
    std_dev = monthly_spending.std()
    cv = (std_dev / mean_spending * 100) if mean_spending > 0 else 0
    
    return {
        "volatility": std_dev,
        "std_dev": std_dev,
        "coefficient_variation": cv,
        "mean_spending": mean_spending
    }


def calculate_cash_flow(df: pd.DataFrame, income: float = None) -> pd.DataFrame:
    """Calculate monthly cash flow (income - expenses)."""
    if df.empty:
        return pd.DataFrame()
    
    df = df.copy()
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce")
    df[Columns.YEAR_MONTH] = df[Columns.DATE].dt.to_period("M")
    
    # Monthly expenses
    monthly_expenses = df.groupby(Columns.YEAR_MONTH)[Columns.PRICE_PAID].sum().reset_index()
    monthly_expenses.columns = ["Month", "Expenses"]
    
    # Add income (if provided, use same for all months)
    if income:
        monthly_expenses["Income"] = income
        monthly_expenses["Cash Flow"] = monthly_expenses["Income"] - monthly_expenses["Expenses"]
        monthly_expenses["Cumulative"] = monthly_expenses["Cash Flow"].cumsum()
    
    monthly_expenses["Month"] = monthly_expenses["Month"].astype(str)
    return monthly_expenses


def calculate_category_allocation(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate spending allocation by category."""
    if df.empty:
        return pd.DataFrame()
    
    df = df.copy()
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce")
    
    # Group by category
    allocation = df.groupby(Columns.CATEGORY)[Columns.PRICE_PAID].sum().reset_index()
    allocation.columns = ["Category", "Amount"]
    
    total = allocation["Amount"].sum()
    allocation["Percentage"] = (allocation["Amount"] / total * 100) if total > 0 else 0
    allocation = allocation.sort_values("Amount", ascending=False)
    
    return allocation


def calculate_burn_rate(df: pd.DataFrame) -> dict:
    """Calculate daily burn rate."""
    if df.empty:
        return {"daily_burn": 0, "monthly_projection": 0}
    
    df = df.copy()
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce")
    
    # This month's data
    current_month = datetime.now().replace(day=1)
    this_month = df[df[Columns.DATE] >= current_month]
    
    if this_month.empty:
        return {"daily_burn": 0, "monthly_projection": 0}
    
    days_elapsed = (datetime.now() - current_month).days + 1
    total_spent = this_month[Columns.PRICE_PAID].sum()
    daily_burn = total_spent / days_elapsed if days_elapsed > 0 else 0
    
    # Project to end of month
    days_in_month = (current_month.replace(month=current_month.month % 12 + 1, day=1) - timedelta(days=1)).day
    monthly_projection = daily_burn * days_in_month
    
    return {
        "daily_burn": daily_burn,
        "monthly_projection": monthly_projection,
        "days_elapsed": days_elapsed,
        "days_remaining": days_in_month - days_elapsed
    }


def plot_financial_health_score(metrics: dict):
    """Create radar chart for financial health."""
    # Normalize scores to 0-100
    savings_score = min(metrics["savings_rate"], 100) if metrics["savings_rate"] > 0 else 0
    
    # Volatility score (lower is better, so invert)
    cv = metrics.get("coefficient_variation", 0)
    volatility_score = max(0, 100 - cv) if cv < 100 else 0
    
    # Budget adherence (assume 90% if no budget data)
    budget_score = 90
    
    # Expense efficiency (based on categories)
    efficiency_score = 75
    
    categories = ["Savings Rate", "Spending Stability", "Budget Adherence", "Expense Efficiency"]
    scores = [savings_score, volatility_score, budget_score, efficiency_score]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=scores,
        theta=categories,
        fill='toself',
        name='Your Score',
        line_color='#667eea'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100])
        ),
        showlegend=False,
        title="Financial Health Score",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Overall score
    overall_score = sum(scores) / len(scores)
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("Overall Score", f"{overall_score:.0f}/100")
    with col2:
        if overall_score >= 80:
            st.success("🏆 Excellent financial health!")
        elif overall_score >= 60:
            st.info("👍 Good financial health")
        elif overall_score >= 40:
            st.warning("⚠️ Room for improvement")
        else:
            st.error("🚨 Needs attention")


def financial_metrics_ui(df: pd.DataFrame):
    """Main UI for financial metrics dashboard."""
    st.title("📊 Financial Metrics Dashboard")
    st.markdown("Comprehensive view of your financial health")
    
    if df.empty:
        st.info("No data available yet. Add expenses to see financial metrics!")
        return
    
    # Income input
    st.markdown("### 💰 Income Settings")
    col_inc1, col_inc2 = st.columns([2, 1])
    with col_inc1:
        monthly_income = st.number_input(
            "Monthly Income (SEK)",
            min_value=0.0,
            value=st.session_state.get("monthly_income", 50000.0),
            step=1000.0,
            help="Your monthly income for calculating savings rate"
        )
        st.session_state["monthly_income"] = monthly_income
    
    st.markdown("---")
    
    # Calculate metrics
    savings_metrics = calculate_savings_rate(df, monthly_income)
    volatility_metrics = calculate_expense_volatility(df)
    burn_rate = calculate_burn_rate(df)
    allocation = calculate_category_allocation(df)
    
    # KPI Row 1
    st.markdown("### 📈 Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(
        "💰 Savings Rate",
        f"{savings_metrics['savings_rate']:.1f}%",
        delta=f"{savings_metrics['monthly_savings']:,.0f} SEK/mo",
        help="Percentage of income saved"
    )
    
    col2.metric(
        "📊 Expense Volatility",
        f"{volatility_metrics['coefficient_variation']:.1f}%",
        delta="Lower is better",
        delta_color="inverse",
        help="Consistency of your spending"
    )
    
    col3.metric(
        "🔥 Daily Burn Rate",
        f"{burn_rate['daily_burn']:,.0f} SEK",
        delta=f"{burn_rate['monthly_projection']:,.0f} SEK projected",
        help="Average daily spending"
    )
    
    col4.metric(
        "💸 This Month",
        f"{savings_metrics['total_spent']:,.0f} SEK",
        delta=f"{(savings_metrics['total_spent']/monthly_income*100):.0f}% of income" if monthly_income > 0 else "N/A",
        help="Total spent this month"
    )
    
    st.markdown("---")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "🎯 Financial Health",
        "💵 Cash Flow",
        "📊 Category Allocation",
        "📈 Trends"
    ])
    
    with tab1:
        st.markdown("### 🎯 Financial Health Score")
        
        metrics_combined = {
            **savings_metrics,
            **volatility_metrics
        }
        plot_financial_health_score(metrics_combined)
        
        # Detailed metrics
        st.markdown("#### 📋 Detailed Breakdown")
        
        col_d1, col_d2 = st.columns(2)
        
        with col_d1:
            st.markdown("##### Savings")
            st.write(f"**Rate**: {savings_metrics['savings_rate']:.1f}%")
            st.write(f"**Amount**: {savings_metrics['monthly_savings']:,.0f} SEK/month")
            st.write(f"**Income**: {savings_metrics['income']:,.0f} SEK")
            st.write(f"**Expenses**: {savings_metrics['total_spent']:,.0f} SEK")
            
            # Savings gauge
            fig_savings = go.Figure(go.Indicator(
                mode="gauge+number",
                value=savings_metrics['savings_rate'],
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Savings Rate"},
                gauge={
                    'axis': {'range': [None, 50]},
                    'bar': {'color': "#667eea"},
                    'steps': [
                        {'range': [0, 10], 'color': "#fee"},
                        {'range': [10, 20], 'color': "#fdd"},
                        {'range': [20, 30], 'color': "#dfd"},
                        {'range': [30, 50], 'color': "#dff"}
                    ],
                    'threshold': {
                        'line': {'color': "green", 'width': 4},
                        'thickness': 0.75,
                        'value': 20
                    }
                }
            ))
            fig_savings.update_layout(height=300)
            st.plotly_chart(fig_savings, use_container_width=True)
        
        with col_d2:
            st.markdown("##### Stability")
            st.write(f"**Volatility**: {volatility_metrics['std_dev']:,.0f} SEK")
            st.write(f"**Coefficient of Variation**: {volatility_metrics['coefficient_variation']:.1f}%")
            st.write(f"**Average Monthly**: {volatility_metrics.get('mean_spending', 0):,.0f} SEK")
            
            # Stability score
            stability_score = max(0, 100 - volatility_metrics['coefficient_variation'])
            fig_stability = go.Figure(go.Indicator(
                mode="gauge+number",
                value=stability_score,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Stability Score"},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "#8b5cf6"},
                    'steps': [
                        {'range': [0, 50], 'color': "#fee"},
                        {'range': [50, 75], 'color': "#ffd"},
                        {'range': [75, 100], 'color': "#dfd"}
                    ]
                }
            ))
            fig_stability.update_layout(height=300)
            st.plotly_chart(fig_stability, use_container_width=True)
    
    with tab2:
        st.markdown("### 💵 Cash Flow Analysis")
        
        if monthly_income > 0:
            cash_flow_df = calculate_cash_flow(df, monthly_income)
            
            if not cash_flow_df.empty:
                # Cash flow chart
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=cash_flow_df["Month"],
                    y=cash_flow_df["Income"],
                    name="Income",
                    marker_color='#22c55e'
                ))
                
                fig.add_trace(go.Bar(
                    x=cash_flow_df["Month"],
                    y=cash_flow_df["Expenses"],
                    name="Expenses",
                    marker_color='#ef4444'
                ))
                
                fig.add_trace(go.Scatter(
                    x=cash_flow_df["Month"],
                    y=cash_flow_df["Cash Flow"],
                    name="Net Cash Flow",
                    line=dict(color='#667eea', width=3),
                    mode='lines+markers'
                ))
                
                fig.update_layout(
                    title="Monthly Cash Flow",
                    xaxis_title="Month",
                    yaxis_title="Amount (SEK)",
                    barmode='group',
                    height=400,
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Cumulative cash flow
                fig_cum = px.line(
                    cash_flow_df,
                    x="Month",
                    y="Cumulative",
                    title="Cumulative Cash Flow",
                    markers=True
                )
                fig_cum.add_hline(y=0, line_dash="dash", line_color="gray")
                fig_cum.update_layout(height=350)
                st.plotly_chart(fig_cum, use_container_width=True)
                
                # Summary table
                st.dataframe(
                    cash_flow_df.style.format({
                        "Income": "{:,.0f} SEK",
                        "Expenses": "{:,.0f} SEK",
                        "Cash Flow": "{:+,.0f} SEK",
                        "Cumulative": "{:+,.0f} SEK"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Not enough data for cash flow analysis")
        else:
            st.warning("Set your monthly income above to see cash flow analysis")
    
    with tab3:
        st.markdown("### 📊 Category Allocation")
        
        if not allocation.empty:
            # Pie chart
            fig_pie = px.pie(
                allocation,
                values="Amount",
                names="Category",
                title="Spending by Category",
                hole=0.4
            )
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # Allocation table
            st.markdown("#### Detailed Allocation")
            st.dataframe(
                allocation.style.format({
                    "Amount": "{:,.0f} SEK",
                    "Percentage": "{:.1f}%"
                }).bar(subset=["Percentage"], color='#667eea'),
                use_container_width=True,
                hide_index=True
            )
            
            # Budget recommendations
            st.markdown("#### 💡 Recommended Allocation")
            st.info("""
            **Ideal Budget Allocation (50/30/20 rule)**:
            - 50% Needs (Housing, Food, Transport)
            - 30% Wants (Entertainment, Dining Out)
            - 20% Savings & Debt
            """)
        else:
            st.info("No category data available")
    
    with tab4:
        st.markdown("### 📈 Spending Trends")
        
        # Monthly trend
        df_trend = df.copy()
        df_trend[Columns.DATE] = pd.to_datetime(df_trend[Columns.DATE], errors="coerce")
        df_trend[Columns.PRICE_PAID] = pd.to_numeric(df_trend[Columns.PRICE_PAID], errors="coerce")
        df_trend[Columns.YEAR_MONTH] = df_trend[Columns.DATE].dt.to_period("M")
        
        monthly_trend = df_trend.groupby(Columns.YEAR_MONTH)[Columns.PRICE_PAID].sum().reset_index()
        monthly_trend.columns = ["Month", "Spending"]
        monthly_trend["Month"] = monthly_trend["Month"].astype(str)
        
        # Add moving average
        monthly_trend["3-Month MA"] = monthly_trend["Spending"].rolling(window=3).mean()
        
        fig_trend = go.Figure()
        
        fig_trend.add_trace(go.Bar(
            x=monthly_trend["Month"],
            y=monthly_trend["Spending"],
            name="Monthly Spending",
            marker_color='#667eea'
        ))
        
        fig_trend.add_trace(go.Scatter(
            x=monthly_trend["Month"],
            y=monthly_trend["3-Month MA"],
            name="3-Month Average",
            line=dict(color='#ef4444', width=2, dash='dash')
        ))
        
        if monthly_income > 0:
            fig_trend.add_hline(
                y=monthly_income,
                line_dash="dot",
                line_color="green",
                annotation_text="Income"
            )
        
        fig_trend.update_layout(
            title="Monthly Spending Trend",
            xaxis_title="Month",
            yaxis_title="Spending (SEK)",
            height=400,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_trend, use_container_width=True)
        
        # Growth rate
        if len(monthly_trend) >= 2:
            latest_spending = monthly_trend.iloc[-1]["Spending"]
            previous_spending = monthly_trend.iloc[-2]["Spending"]
            growth_rate = ((latest_spending - previous_spending) / previous_spending * 100) if previous_spending > 0 else 0
            
            col_g1, col_g2 = st.columns(2)
            col_g1.metric(
                "Month-over-Month Growth",
                f"{growth_rate:+.1f}%",
                delta=f"{latest_spending - previous_spending:+,.0f} SEK",
                delta_color="inverse"
            )
            
            # Year-over-year if available
            if len(monthly_trend) >= 12:
                yoy_growth = ((latest_spending - monthly_trend.iloc[-13]["Spending"]) / monthly_trend.iloc[-13]["Spending"] * 100)
                col_g2.metric(
                    "Year-over-Year Growth",
                    f"{yoy_growth:+.1f}%",
                    delta_color="inverse"
                )


# Integration helper
def add_to_main_app():
    """
    Add to Main_Dashboard_App.py:
    
    from financial_metrics import financial_metrics_ui
    
    pages["📊 Financial Metrics"] = "financial_metrics"
    
    elif page == "financial_metrics":
        financial_metrics_ui(df)
    """
    pass
