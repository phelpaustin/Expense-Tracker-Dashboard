# price_tracker.py
"""
Track price changes of items over time.
Shows how much prices have increased/decreased for the same items at different shops.
"""
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from config import Columns
from security_utils import escape_html as esc


def analyze_price_changes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analyze price changes for items over time.
    
    Returns DataFrame with price change information.
    """
    if df.empty:
        return pd.DataFrame()
    
    df = df.copy()
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce")
    
    # Remove null values
    df = df.dropna(subset=[Columns.DATE, Columns.PRICE_PAID, Columns.ITEM])
    
    # Compute per-unit price if columns are available
    if Columns.PRICE_PER_UNIT in df.columns:
        df[Columns.PRICE_PER_UNIT] = pd.to_numeric(df[Columns.PRICE_PER_UNIT], errors="coerce")
        price_col = Columns.PRICE_PER_UNIT
    else:
        price_col = Columns.PRICE_PAID

    # Group by item, calculate price statistics. Using groupby (rather than
    # filtering the full frame per unique item) keeps this O(n) instead of
    # O(n²) and is clearer.
    price_analysis = []

    for item, item_df in df.groupby(Columns.ITEM, sort=False):
        if len(item_df) < 2:
            continue  # Need at least 2 purchases to see change

        item_df = item_df.sort_values(Columns.DATE)

        # Determine unit label (e.g. "kg", "L", "Count")
        unit_label = "unit"
        if Columns.QUANTITY_UNIT in item_df.columns:
            unit_vals = item_df[Columns.QUANTITY_UNIT].dropna()
            if not unit_vals.empty:
                unit_label = unit_vals.mode().iloc[0]
        
        # Overall price change (per unit)
        first_price = item_df.iloc[0][price_col]
        last_price = item_df.iloc[-1][price_col]
        price_change = last_price - first_price
        price_change_pct = (price_change / first_price * 100) if first_price > 0 else 0
        
        # Calculate trend
        avg_price = item_df[price_col].mean()
        min_price = item_df[price_col].min()
        max_price = item_df[price_col].max()
        std_price = item_df[price_col].std()
        
        # Determine if price is increasing or decreasing
        recent_avg = item_df.tail(3)[price_col].mean()
        old_avg = item_df.head(3)[price_col].mean()
        trend = "Increasing" if recent_avg > old_avg else "Decreasing" if recent_avg < old_avg else "Stable"
        
        price_analysis.append({
            "Item": item,
            "Unit": unit_label,
            "Category": item_df.iloc[0][Columns.CATEGORY],
            "First Purchase": item_df.iloc[0][Columns.DATE].date(),
            "Last Purchase": item_df.iloc[-1][Columns.DATE].date(),
            "First Price": first_price,
            "Last Price": last_price,
            "Price Change": price_change,
            "Change %": price_change_pct,
            "Avg Price": avg_price,
            "Min Price": min_price,
            "Max Price": max_price,
            "Volatility": std_price,
            "Trend": trend,
            "Purchases": len(item_df)
        })
    
    return pd.DataFrame(price_analysis).sort_values("Change %", ascending=False)


def get_shop_price_comparison(df: pd.DataFrame, item: str) -> pd.DataFrame:
    """Compare per-unit prices of same item across different shops."""
    if df.empty or not item:
        return pd.DataFrame()
    
    df = df.copy()
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce")

    # Use per-unit price when available
    if Columns.PRICE_PER_UNIT in df.columns:
        df[Columns.PRICE_PER_UNIT] = pd.to_numeric(df[Columns.PRICE_PER_UNIT], errors="coerce")
        price_col = Columns.PRICE_PER_UNIT
    else:
        price_col = Columns.PRICE_PAID
    
    item_df = df[df[Columns.ITEM] == item]
    
    if item_df.empty:
        return pd.DataFrame()

    # Determine unit label
    unit_label = "unit"
    if Columns.QUANTITY_UNIT in item_df.columns:
        unit_vals = item_df[Columns.QUANTITY_UNIT].dropna()
        if not unit_vals.empty:
            unit_label = unit_vals.mode().iloc[0]
    
    # Group by shop using per-unit price
    shop_comparison = item_df.groupby(Columns.SHOP).agg({
        price_col: ['mean', 'min', 'max', 'count']
    }).reset_index()
    
    shop_comparison.columns = ['Shop', f'Avg Price/{unit_label}', f'Min Price/{unit_label}', f'Max Price/{unit_label}', 'Times Bought']
    return shop_comparison.sort_values(f'Avg Price/{unit_label}')


def plot_price_history(df: pd.DataFrame, item: str):
    """Plot per-unit price history timeline for an item."""
    df = df.copy()
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce")

    # Use per-unit price when available
    if Columns.PRICE_PER_UNIT in df.columns:
        df[Columns.PRICE_PER_UNIT] = pd.to_numeric(df[Columns.PRICE_PER_UNIT], errors="coerce")
        price_col = Columns.PRICE_PER_UNIT
    else:
        price_col = Columns.PRICE_PAID
    
    item_df = df[df[Columns.ITEM] == item].sort_values(Columns.DATE)
    
    if item_df.empty:
        st.warning(f"No price history found for {item}")
        return

    # Determine unit label
    unit_label = "unit"
    if Columns.QUANTITY_UNIT in item_df.columns:
        unit_vals = item_df[Columns.QUANTITY_UNIT].dropna()
        if not unit_vals.empty:
            unit_label = unit_vals.mode().iloc[0]

    y_axis_title = f"Price per {unit_label} (SEK)"
    chart_title = f"Price History: {item}  (per {unit_label})"
    
    # Create line chart with markers
    fig = go.Figure()
    
    # Per-unit price line
    fig.add_trace(go.Scatter(
        x=item_df[Columns.DATE],
        y=item_df[price_col],
        mode='lines+markers',
        name=f'Price / {unit_label}',
        line=dict(color='#667eea', width=2),
        marker=dict(size=8, color=item_df[Columns.SHOP].astype('category').cat.codes, 
                   colorscale='Viridis', showscale=True,
                   colorbar=dict(title="Shop")),
        hovertemplate=f"%{{x|%Y-%m-%d}}<br>%{{y:.2f}} SEK/{unit_label}<extra></extra>"
    ))
    
    # Add average line
    avg_price = item_df[price_col].mean()
    fig.add_hline(y=avg_price, line_dash="dash", line_color="gray",
                  annotation_text=f"Avg: {avg_price:.2f} SEK/{unit_label}")
    
    fig.update_layout(
        title=chart_title,
        xaxis_title="Date",
        yaxis_title=y_axis_title,
        hovermode='x unified',
        height=400
    )
    
    st.plotly_chart(fig)
    
    # Show shop breakdown (per-unit)
    st.markdown(f"#### Price per {unit_label} by Shop")
    shop_prices = item_df.groupby(Columns.SHOP)[price_col].agg(['mean', 'min', 'max', 'count'])
    shop_prices.columns = [f'Average/{unit_label}', f'Lowest/{unit_label}', f'Highest/{unit_label}', 'Times Bought']
    st.dataframe(shop_prices.style.format({
        f'Average/{unit_label}': "{:.2f}",
        f'Lowest/{unit_label}': "{:.2f}",
        f'Highest/{unit_label}': "{:.2f}",
    }), width="stretch")


def show_biggest_price_increases(df: pd.DataFrame, n: int = 10):
    """Show items with biggest price increases."""
    price_analysis = analyze_price_changes(df)
    
    if price_analysis.empty:
        st.info("Not enough data to analyze price changes. Need at least 2 purchases of same items.")
        return
    
    # Filter for items with actual increases
    increases = price_analysis[price_analysis["Change %"] > 0].head(n)
    
    if increases.empty:
        st.info("No items with price increases found.")
        return
    
    st.markdown(f"### 📈 Top {n} Items with Biggest Price Increases")
    
    # Create bar chart
    fig = px.bar(
        increases,
        x="Item",
        y="Change %",
        color="Change %",
        color_continuous_scale="Reds",
        hover_data=["Unit", "First Price", "Last Price", "Purchases"],
        title="Items with Largest Per-Unit Price Increases"
    )
    
    fig.update_layout(
        xaxis_title="Item",
        yaxis_title="Price Increase (%)",
        height=400
    )
    
    st.plotly_chart(fig)
    
    # Show detailed table
    st.markdown("#### Detailed Price Changes (Per Unit)")
    display_cols = ["Item", "Unit", "First Price", "Last Price", "Price Change", "Change %", "Trend", "Purchases"]
    styled_df = increases[display_cols].style.format({
        "First Price": "{:.2f} SEK",
        "Last Price": "{:.2f} SEK",
        "Price Change": "{:+.2f} SEK",
        "Change %": "{:+.1f}%"
    })
    st.dataframe(styled_df, width="stretch", hide_index=True)


def show_best_deals(df: pd.DataFrame, category: str = None):
    """Find items currently at lowest historical per-unit price."""
    df = df.copy()
    df[Columns.DATE] = pd.to_datetime(df[Columns.DATE], errors="coerce")
    df[Columns.PRICE_PAID] = pd.to_numeric(df[Columns.PRICE_PAID], errors="coerce")

    # Use per-unit price when available
    if Columns.PRICE_PER_UNIT in df.columns:
        df[Columns.PRICE_PER_UNIT] = pd.to_numeric(df[Columns.PRICE_PER_UNIT], errors="coerce")
        price_col = Columns.PRICE_PER_UNIT
    else:
        price_col = Columns.PRICE_PAID
    
    if category:
        df = df[df[Columns.CATEGORY] == category]
    
    # Get items bought in last 30 days
    recent_cutoff = datetime.now() - timedelta(days=30)
    recent_df = df[df[Columns.DATE] >= recent_cutoff]
    
    deals = []
    for item in recent_df[Columns.ITEM].unique():
        item_history = df[df[Columns.ITEM] == item]
        if len(item_history) < 2:
            continue

        # Unit label
        unit_label = "unit"
        if Columns.QUANTITY_UNIT in item_history.columns:
            unit_vals = item_history[Columns.QUANTITY_UNIT].dropna()
            if not unit_vals.empty:
                unit_label = unit_vals.mode().iloc[0]
        
        current_price = recent_df[recent_df[Columns.ITEM] == item][price_col].iloc[-1]
        historical_min = item_history[price_col].min()
        historical_avg = item_history[price_col].mean()
        
        if current_price <= historical_min:
            deals.append({
                "Item": item,
                "Unit": unit_label,
                f"Current Price/Unit": current_price,
                f"Historical Avg/Unit": historical_avg,
                "Savings/Unit": historical_avg - current_price,
                "Savings %": (historical_avg - current_price) / historical_avg * 100
            })
    
    if deals:
        deals_df = pd.DataFrame(deals).sort_values("Savings %", ascending=False)
        st.markdown("### 💰 Current Best Deals (At or Below Historical Low Per Unit)")
        st.dataframe(deals_df.style.format({
            "Current Price/Unit": "{:.2f} SEK",
            "Historical Avg/Unit": "{:.2f} SEK",
            "Savings/Unit": "{:.2f} SEK",
            "Savings %": "{:.1f}%"
        }), width="stretch", hide_index=True)
    else:
        st.info("No items currently at historical low prices.")


def price_tracker_ui(df: pd.DataFrame):
    """Main UI for price tracking feature."""
    st.title("💰 Price Tracker & Trends")
    st.markdown("Track how prices of items change over time and find the best deals")
    
    if df.empty:
        st.info("No data available yet. Start tracking expenses to see price trends!")
        return
    
    # Quick stats
    price_analysis = analyze_price_changes(df)
    
    if not price_analysis.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric(
            "Items Tracked",
            len(price_analysis),
            help="Items purchased multiple times"
        )
        
        avg_increase = price_analysis[price_analysis["Change %"] > 0]["Change %"].mean()
        col2.metric(
            "Avg Price Increase",
            f"{avg_increase:.1f}%" if pd.notna(avg_increase) else "N/A",
            delta=f"{avg_increase:.1f}%" if pd.notna(avg_increase) else None,
            delta_color="inverse"
        )
        
        increasing_items = len(price_analysis[price_analysis["Trend"] == "Increasing"])
        col3.metric(
            "Items Getting Expensive",
            increasing_items,
            delta=f"{increasing_items}/{len(price_analysis)}",
            delta_color="inverse"
        )
        
        volatile_items = len(price_analysis[price_analysis["Volatility"] > 10])
        col4.metric(
            "Volatile Prices",
            volatile_items,
            help="Items with high price variation"
        )
        
        st.markdown("---")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Price Increases",
        "🔍 Item Lookup",
        "💰 Best Deals",
        "📊 Full Analysis"
    ])
    
    with tab1:
        show_biggest_price_increases(df, n=15)
    
    with tab2:
        st.markdown("### 🔍 Search Item Price History")
        
        # Get all items
        all_items = sorted(df[Columns.ITEM].dropna().unique().tolist())
        
        selected_item = st.selectbox(
            "Select an item to see price history",
            all_items,
            help="Choose an item you've purchased multiple times"
        )
        
        if selected_item:
            plot_price_history(df, selected_item)
            
            # Shop comparison
            st.markdown("#### 🏪 Shop Price Comparison (Per Unit)")
            shop_comp = get_shop_price_comparison(df, selected_item)
            if not shop_comp.empty:
                # Format all numeric columns to 2 decimal places
                numeric_cols = shop_comp.select_dtypes(include='number').columns
                fmt = {col: "{:.2f} SEK" for col in numeric_cols}
                st.dataframe(shop_comp.style.format(fmt), width="stretch", hide_index=True)
                
                # Highlight cheapest shop (first column after 'Shop' is the avg price)
                avg_col = shop_comp.columns[1]
                cheapest = shop_comp.iloc[0]
                st.success(f"💡 **Best Deal**: {cheapest['Shop']} at avg {cheapest[avg_col]:.2f} SEK/{avg_col.split('/')[-1]}")
            else:
                st.info("Only bought from one shop")
    
    with tab3:
        st.markdown("### 💰 Current Best Deals")
        st.caption("Items currently at or below their historical lowest price")
        
        # Category filter
        categories = ["All"] + sorted(df[Columns.CATEGORY].dropna().unique().tolist())
        selected_category = st.selectbox("Filter by category", categories)
        
        show_best_deals(df, None if selected_category == "All" else selected_category)
    
    with tab4:
        st.markdown("### 📊 Complete Price Analysis")
        st.caption("All prices shown are per unit (e.g. per kg, per L, per item) for accurate comparison.")
        
        if not price_analysis.empty:
            # Filters
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                min_purchases = st.slider("Min purchases", 2, 20, 2)
            with col_f2:
                trend_filter = st.multiselect(
                    "Filter by trend",
                    ["Increasing", "Decreasing", "Stable"],
                    default=["Increasing", "Decreasing", "Stable"]
                )
            
            # Apply filters
            filtered = price_analysis[
                (price_analysis["Purchases"] >= min_purchases) &
                (price_analysis["Trend"].isin(trend_filter))
            ]
            
            if not filtered.empty:
                st.dataframe(
                    filtered.style.format({
                        "First Price": "{:.2f} SEK",
                        "Last Price": "{:.2f} SEK",
                        "Price Change": "{:+.2f} SEK",
                        "Change %": "{:+.1f}%",
                        "Avg Price": "{:.2f} SEK",
                        "Min Price": "{:.2f} SEK",
                        "Max Price": "{:.2f} SEK",
                        "Volatility": "{:.2f}"
                    }).background_gradient(subset=["Change %"], cmap="RdYlGn_r"),
                    width="stretch",
                    hide_index=True
                )
                
                # Export
                csv = filtered.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Download Full Analysis",
                    csv,
                    "price_analysis.csv",
                    "text/csv"
                )
            else:
                st.info("No items match your filters")
        else:
            st.info("Not enough data for analysis. Buy the same items multiple times to track price changes!")

    # ── AI price analysis ─────────────────────────────────────────────────────
    st.markdown("---")
    _ai_price_analysis(df)


def _ai_price_analysis(df: pd.DataFrame) -> None:
    """AI analysis of price trends — flags items getting expensive, suggests substitutions."""
    import json
    try:
        from ai_insights import _get_keys, _call_ai
    except ImportError:
        return

    keys = _get_keys()
    if not any(keys.values()):
        return

    st.markdown("### 🤖 AI Price Analysis")
    st.caption("AI identifies concerning price trends and suggests where to save.")

    cache_key = f"ai_prices_{pd.Timestamp.now().strftime('%Y-%m')}"
    if cache_key not in st.session_state:
        if not st.button("✨ Analyse My Price Trends", key="ai_price_btn"):
            return

        price_analysis = analyze_price_changes(df)
        if price_analysis.empty:
            st.info("Not enough price history yet.")
            return

        rising   = price_analysis[price_analysis["Change %"] > 10].nlargest(8, "Change %")
        falling  = price_analysis[price_analysis["Change %"] < -5].nsmallest(5, "Change %")

        payload = {
            "items_getting_expensive": rising[["Item", "Avg Price", "Change %", "Trend"]].round(2).to_dict("records") if not rising.empty else [],
            "items_getting_cheaper":   falling[["Item", "Avg Price", "Change %"]].round(2).to_dict("records") if not falling.empty else [],
            "total_items_tracked":     int(len(price_analysis)),
            "pct_items_rising":        round(len(price_analysis[price_analysis["Change %"] > 0]) / len(price_analysis) * 100, 1),
        }

        system = (
            "You are a personal shopping advisor. "
            "The user will share which items are getting more or less expensive in their expense tracker. "
            "Give 3-5 specific tips: which items to buy in bulk before prices rise further, "
            "which categories to shop around for better prices, "
            "and whether overall inflation in their basket looks concerning. "
            "Be specific with item names and percentages. Currency is SEK."
        )
        user = (
            f"Here are my item price trends:\n{json.dumps(payload, indent=2)}\n\n"
            "Give me specific shopping advice based on these price trends."
        )
        with st.spinner("AI is reviewing your price trends…"):
            text, provider = _call_ai(system, user, keys)

        if text:
            st.session_state[cache_key] = (text, provider)
        else:
            st.error("No AI provider responded.")
            return

    if cache_key not in st.session_state:
        return

    text, provider = st.session_state[cache_key]
    bullets = [b.strip().lstrip("•-0123456789.)").strip()
               for b in text.split("\n") if b.strip()]
    bullets = [b for b in bullets if len(b) > 15]

    items_html = "".join(
        f"<li style='margin-bottom:0.45rem;'>{esc(b)}</li>" for b in bullets
    ) or f"<li>{esc(text)}</li>"

    body = (
        f"<ul style='margin:0;padding-left:1.2rem;font-size:0.9rem;"
        f"line-height:1.75;color:#0f172a;'>{items_html}</ul>"
    )
    from page_helpers import render_ai_card
    render_ai_card(
        body, provider, cache_key=cache_key,
        refresh_key="refresh_price_ai", accent="#f59e0b",
    )
