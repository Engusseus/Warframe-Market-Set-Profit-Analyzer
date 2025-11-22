import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import market_analyzer as logic
from database import get_database_instance
import requests
import time

# Page config
st.set_page_config(
    page_title="Warframe Market Analyzer",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'data' not in st.session_state:
    st.session_state.data = None
if 'weights' not in st.session_state:
    st.session_state.weights = (1.0, 1.2)  # Profit, Volume

def load_data(refresh=False):
    """Load data using market_analyzer logic."""
    requests_module = requests
    rate_limiter = logic.RateLimiter(max_requests=3, time_window=1.0)
    cache = logic.load_cache()

    progress_bar = st.progress(0)
    status_text = st.empty()

    def progress_callback(i, total, msg):
        progress = i / total
        progress_bar.progress(progress)
        status_text.text(f"{msg} ({i}/{total})")

    try:
        if refresh:
            st.toast("Fetching fresh data from API...", icon="🔄")
            cache = logic.refresh_cache_data(requests_module, rate_limiter, progress_callback)
        else:
             # Check if we need to refresh anyway (basic check)
             prime_sets = logic.fetch_prime_sets_list(requests_module)
             current_hash = logic.calculate_hash(prime_sets)
             cached_hash = cache.get('prime_sets_hash', '')

             if current_hash != cached_hash or 'detailed_sets' not in cache:
                 st.toast("Cache outdated, fetching fresh data...", icon="⚠️")
                 cache = logic.refresh_cache_data(requests_module, rate_limiter, progress_callback)
             else:
                 st.toast("Using cached set definitions...", icon="💾")

        # Now fetch prices and volume
        st.toast("Fetching prices and volumes...", icon="💰")
        set_prices = logic.fetch_set_lowest_prices(cache, requests_module, rate_limiter, progress_callback)
        part_prices = logic.fetch_part_lowest_prices(cache, requests_module, rate_limiter, progress_callback)
        volume_result = logic.fetch_set_volume(cache, requests_module, rate_limiter, progress_callback)

        detailed_sets = cache['detailed_sets']
        profit_data = logic.calculate_profit_margins(set_prices, part_prices, detailed_sets)

        # Calculate scores with current weights
        profit_weight, volume_weight = st.session_state.weights
        scored_data = logic.calculate_profitability_scores(profit_data, volume_result, profit_weight, volume_weight)

        # Save to DB
        try:
            if profit_data and set_prices:
                db = get_database_instance()
                run_id = db.save_market_run(profit_data, set_prices)
                st.toast(f"Run saved to database (ID: {run_id})", icon="✅")
        except Exception as e:
            st.error(f"Failed to save to database: {e}")

        progress_bar.empty()
        status_text.empty()
        return scored_data

    except Exception as e:
        st.error(f"Error loading data: {e}")
        progress_bar.empty()
        status_text.empty()
        return None

# Sidebar
with st.sidebar:
    st.title("Configuration")

    st.subheader("Scoring Weights")
    p_weight = st.slider("Profit Weight", 0.0, 5.0, 1.0, 0.1, help="Importance of profit margin")
    v_weight = st.slider("Volume Weight", 0.0, 5.0, 1.2, 0.1, help="Importance of trading volume")

    if (p_weight, v_weight) != st.session_state.weights:
        st.session_state.weights = (p_weight, v_weight)
        if st.session_state.data:
            # Recalculate scores if weights change
             # We need to access the raw data to re-score.
             # Since logic.calculate_profitability_scores takes profit_data,
             # and we stored the result which has normalized values but we want to re-normalize/re-weight.
             # Actually, the function takes profit_data and volume_data.
             # To avoid re-fetching, we might want to store raw profit_data in session state too.
             # For now, we will just warn the user or let them click "Refresh Analysis" which is fast if cached.
             st.info("Weights changed. Refresh analysis to update scores.")

    st.divider()

    if st.button("Run Analysis", type="primary", use_container_width=True):
        with st.spinner("Analyzing market..."):
            st.session_state.data = load_data(refresh=False)

    if st.button("Force Refresh Cache", use_container_width=True):
        with st.spinner("Refreshing cache and analyzing..."):
            st.session_state.data = load_data(refresh=True)

# Main Content
st.title("Warframe Market Analyzer 🚀")

if st.session_state.data:
    df = pd.DataFrame(st.session_state.data)

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Analysis", "📈 Visualizations", "📜 History"])

    with tab1:
        st.header("Market Analysis")

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        avg_profit = df['profit_margin'].mean()
        total_vol = df['volume'].sum()
        top_set = df.iloc[0]

        col1.metric("Sets Analyzed", len(df))
        col2.metric("Avg Profit", f"{avg_profit:.0f} pl")
        col3.metric("Total Volume (48h)", f"{total_vol:,.0f}")
        col4.metric("Best Opportunity", top_set['set_name'], f"{top_set['total_score']:.2f} Score")

        st.divider()

        # Filters
        col1, col2 = st.columns(2)
        with col1:
            min_profit = st.number_input("Min Profit (plat)", value=0)
        with col2:
            min_volume = st.number_input("Min Volume", value=0)

        filtered_df = df[(df['profit_margin'] >= min_profit) & (df['volume'] >= min_volume)]

        # Display Dataframe
        st.dataframe(
            filtered_df[[
                'set_name', 'set_price', 'part_cost', 'profit_margin',
                'profit_percentage', 'volume', 'total_score'
            ]].style.format({
                'set_price': '{:.0f}',
                'part_cost': '{:.0f}',
                'profit_margin': '{:.0f}',
                'profit_percentage': '{:.1f}%',
                'volume': '{:,.0f}',
                'total_score': '{:.2f}'
            }),
            use_container_width=True,
            height=600
        )

        # Details view
        st.subheader("Set Details")
        selected_set_name = st.selectbox("Select Set to View Details", filtered_df['set_name'].tolist())

        if selected_set_name:
            set_details = filtered_df[filtered_df['set_name'] == selected_set_name].iloc[0]

            c1, c2, c3 = st.columns(3)
            with c1:
                 st.info(f"**Set Price:** {set_details['set_price']:.0f} pl")
            with c2:
                 st.success(f"**Profit:** {set_details['profit_margin']:.0f} pl")
            with c3:
                 st.warning(f"**ROI:** {set_details['profit_percentage']:.1f}%")

            st.write("**Part Breakdown:**")
            parts_df = pd.DataFrame(set_details['part_details'])
            st.dataframe(
                parts_df[['name', 'unit_price', 'quantity', 'total_cost']].style.format({
                    'unit_price': '{:.0f}',
                    'total_cost': '{:.0f}'
                }),
                use_container_width=True
            )

    with tab2:
        st.header("Market Visualizations")

        # Scatter Plot: Profit vs Volume
        fig = px.scatter(
            df,
            x="volume",
            y="profit_margin",
            size="profit_percentage",
            color="total_score",
            hover_name="set_name",
            log_x=True,
            title="Profit vs Volume (Size = ROI, Color = Score)",
            labels={"volume": "Volume (48h)", "profit_margin": "Profit (plat)", "total_score": "Score"}
        )
        st.plotly_chart(fig, use_container_width=True)

        # Bar Chart: Top 10 by Score
        top_10 = df.head(10)
        fig2 = px.bar(
            top_10,
            x="set_name",
            y="total_score",
            color="profit_margin",
            title="Top 10 Sets by Score",
            labels={"set_name": "Set", "total_score": "Score"}
        )
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        st.header("Historical Data")

        db = get_database_instance()
        stats = db.get_database_stats()

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Runs", stats['total_runs'])
        col2.metric("Records Stored", stats['total_profit_records'])
        col3.metric("Last Run", stats.get('last_run', 'N/A'))

        runs = db.get_run_summary(limit=20)
        if runs:
            st.subheader("Recent Runs")
            runs_df = pd.DataFrame(runs)
            st.dataframe(runs_df, use_container_width=True)
        else:
            st.info("No historical data available.")

else:
    st.info("👈 Click 'Run Analysis' in the sidebar to start!")

    st.markdown("""
    ### What is this?
    This tool analyzes Warframe Market data to find the most profitable Prime sets to flip or farm.

    **Features:**
    *   **Real-time Data:** Fetches live prices and volume.
    *   **Smart Scoring:** Balances profit margin with trading volume.
    *   **Visualizations:** Identify opportunities at a glance.
    *   **History:** Track market trends over time.
    """)
