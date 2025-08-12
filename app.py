# NOTE: Requires: streamlit, plotly, scikit-learn, streamlit-lottie, pandas, numpy
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wf_market_analyzer import run_analysis_ui, run_analysis_in_process
from config import DB_PATH
import sqlite3
import time
import sys
from multiprocessing import Process, Queue
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh
from sklearn.linear_model import LinearRegression
import numpy as np

# Optional: Lottie animation
try:
    from streamlit_lottie import st_lottie
    import requests
    def load_lottieurl(url):
        r = requests.get(url)
        if r.status_code != 200:
            return None
        return r.json()
    lottie_loading = load_lottieurl("https://assets2.lottiefiles.com/packages/lf20_j1adxtyb.json")
except ImportError:
    st_lottie = None
    lottie_loading = None

st.set_page_config(page_title="Warframe Market Profit Analyzer", layout="wide", page_icon="💠")

# Custom CSS for Warframe theme, button hover, progress bar glow
st.markdown('''
    <style>
    body { background: #181c2f; }
    .stButton>button {
        background: linear-gradient(90deg, #4e54c8 0%, #8f94fb 100%);
        color: white;
        font-weight: bold;
        border-radius: 8px;
        box-shadow: 0 0 0px #8f94fb;
        transition: transform 0.3s, box-shadow 0.3s;
    }
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 0 16px #8f94fb;
    }
    .stProgress > div > div > div > div {
        background-image: linear-gradient(90deg, #4e54c8, #8f94fb);
        animation: glow 1.5s infinite alternate;
    }
    @keyframes glow {
        from { box-shadow: 0 0 10px #4e54c8; }
        to { box-shadow: 0 0 30px #8f94fb; }
    }
    </style>
''', unsafe_allow_html=True)

st.title("💠 Warframe Market Profit Analyzer")
st.markdown("<h4>Analyze sets and uncover profits interactively!</h4>", unsafe_allow_html=True)

def get_last_volume_update_time():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # Check if the table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='volume_cache'")
        if cur.fetchone() is None:
            conn.close()
            return None
        cur.execute("SELECT MAX(last_updated) FROM volume_cache")
        result = cur.fetchone()
        conn.close()
        if result and result[0]:
            return datetime.fromisoformat(result[0])
        return None
    except Exception as e:
        # st.warning(f"Could not read volume cache timestamp: {e}")
        return None

volume_update_placeholder = st.empty()
last_update = get_last_volume_update_time()

if last_update:
    next_update_time = last_update + timedelta(hours=1)
    # Explicitly use UTC for current time to ensure correct comparison
    now_utc = datetime.now(timezone.utc)

    if now_utc < next_update_time:
        st_autorefresh(interval=1000, limit=None, key="volume_countdown_refresh")
        remaining = next_update_time - now_utc
        minutes, seconds = divmod(int(remaining.total_seconds()), 60)
        volume_update_placeholder.info(f"New volume data available in {minutes}m {seconds}s.")
    else:
        volume_update_placeholder.warning("OLD VOLUME DATA. You should run analysis.")
else:
    volume_update_placeholder.info("Run analysis to get initial volume data.")

# Sidebar config
def sidebar_config():
    st.sidebar.header("Configuration")
    # Platform is fixed to 'pc' via headers; hiding from UI to reduce confusion
    profit_weight = st.sidebar.slider("Profit Weight", 0.0, 3.0, 1.0, 0.1)
    volume_weight = st.sidebar.slider("Volume Weight", 0.0, 3.0, 1.2, 0.1)
    profit_margin_weight = st.sidebar.slider("Profit Margin Weight", 0.0, 3.0, 0.0, 0.1)
    price_sample_size = st.sidebar.slider("Minimum Online Sell Orders (Sample Size)", 1, 10, 2, 1,
                                          help="Minimum number of online sell orders required to include a set/part")
    # Removed median pricing and statistics toggle – statistics is always used
    analyze_trends = False
    trend_days = 30
    debug = st.sidebar.checkbox("Debug Mode", False)
    # Explicitly cast all values to correct types
    return dict(
        platform='pc',
        profit_weight=float(profit_weight),
        volume_weight=float(volume_weight),
        profit_margin_weight=float(profit_margin_weight),
        price_sample_size=int(price_sample_size),
        use_median_pricing=False,
        use_statistics_for_pricing=True,
        analyze_trends=bool(analyze_trends),
        trend_days=int(trend_days),
        debug=bool(debug),
    )

config = sidebar_config()

st.sidebar.subheader("24/7 Mode")
enable_247 = st.sidebar.checkbox("Enable 24/7 Mode Controls")

if enable_247:
    current_interval = st.session_state.get('continuous_interval_minutes', 60)
    new_interval = st.sidebar.number_input(
        "Interval (minutes)", min_value=0, value=current_interval, step=5,
        help="Set to 0 for instant, continuous analysis."
    )
    st.session_state.continuous_interval_minutes = new_interval

    if st.session_state.get('run_247_enabled', False):
        if st.sidebar.button("Stop 24/7 Mode"):
            st.session_state.run_247_enabled = False
            st.rerun()
    else:
        if st.sidebar.button("Start 24/7 Mode"):
            st.session_state.run_247_enabled = True
            st.rerun()

if st.session_state.get('run_247_enabled', False):
    st.sidebar.success(f"✅ 24/7 Mode is ACTIVE (interval: {st.session_state.continuous_interval_minutes} min)")


# Main UI
if 'data' not in st.session_state:
    st.session_state['data'] = None
    st.session_state['results'] = None
    st.session_state['continuous'] = False # Deprecated but kept for safety
    st.session_state['interval_minutes'] = 60 # Deprecated
    st.session_state['last_run'] = None

# Re-implement 24/7 mode logic
if st.session_state.get('run_247_enabled', False):
    st_autorefresh(interval=2000, limit=None, key="continuous_refresh")
    if not st.session_state.analysis_process:
        interval_minutes = st.session_state.get('continuous_interval_minutes', 60)
        should_run = False
        if st.session_state.get('last_run') is None:
            should_run = True
        else:
            last_ts = datetime.fromisoformat(st.session_state['last_run'])
            elapsed_seconds = (datetime.utcnow() - last_ts).total_seconds()
            if elapsed_seconds / 60 >= interval_minutes:
                should_run = True

        if should_run:
            st.session_state['run_analysis_on_rerun'] = True
            st.rerun()

st.markdown("""
Run a full market analysis and get a ranked table of profitable sets. 
Click below to start! 🚀
""")

if 'analysis_process' not in st.session_state:
    st.session_state.analysis_process = None
    st.session_state.result_queue = None

run_btn = st.button("Run Analysis", type="primary")
stop_btn = st.button("Stop")
quit_btn = st.button("Quit")

if st.session_state.get('run_analysis_on_rerun', False):
    st.session_state['run_analysis_on_rerun'] = False
    run_btn = True

if run_btn and st.session_state.analysis_process is None:
    st.session_state.result_queue = Queue()
    # Note: cancel_token is no longer used with multiprocessing
    config_for_process = config.copy()

    st.session_state.analysis_process = Process(
        target=run_analysis_in_process,
        args=(st.session_state.result_queue,),
        kwargs=config_for_process
    )
    st.session_state.analysis_process.start()
    st.info("Analysis started in a separate process.")

if stop_btn and st.session_state.analysis_process is not None:
    st.session_state.analysis_process.terminate()
    st.session_state.analysis_process.join() # Wait for termination
    st.session_state.analysis_process = None
    st.session_state.result_queue = None
    st.info("Analysis process terminated.")

if quit_btn:
    if st.session_state.analysis_process is not None:
        st.session_state.analysis_process.terminate()
        st.session_state.analysis_process.join()
        st.session_state.analysis_process = None
        st.session_state.result_queue = None

    st.success("Application has been stopped. You can now close this window.")
    st.stop()

if st.session_state.analysis_process:
    if st.session_state.analysis_process.is_alive():
        st.info("Analysis is running in the background...")
        if st_lottie and lottie_loading:
            st_lottie(lottie_loading, height=120, key="loading_process")
        # Auto-refresh to check for process completion
        st_autorefresh(interval=2000, limit=None, key="analysis_refresh")
    else:
        # Process is finished, but results might not be in the queue yet.
        st.session_state.analysis_process.join()
        result = st.session_state.result_queue.get() if not st.session_state.result_queue.empty() else None

        if result is not None:
            # Result is retrieved, process it and clean up state.
            st.session_state.analysis_process = None
            st.session_state.result_queue = None

            if isinstance(result, Exception):
                st.error(f"Analysis failed: {result}")
            else:
                df, results = result
                st.session_state['data'] = df
                st.session_state['results'] = results
                st.session_state['last_run'] = datetime.utcnow().isoformat()
                st.success("Analysis complete! 🎉")
                st.balloons()

            # Trigger a rerun to clear the autorefresh and show final state
            if st.session_state.get('run_247_enabled', False):
                 st.rerun()
        else:
            # Result not yet in queue, wait and refresh.
            st.info("Analysis process finished. Waiting for results...")
            st_autorefresh(interval=1000, limit=None, key="result_wait_refresh")

if st.session_state['data'] is not None:
    df = st.session_state['data']
    st.subheader("Results Table")
    st.dataframe(df, use_container_width=True, hide_index=True)

    if len(df) == 0:
        st.warning("No results to display. Try adjusting filters/weights and rerun.")
    else:
        st.subheader("Profit vs. Volume Scatter Plot")
        fig = px.scatter(
            df,
            x='Volume (48h)',
            y='Profit',
            hover_name='Set Name',
            color='Score',
            color_continuous_scale=px.colors.sequential.Purples,
            height=500,
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("Show Details for Top Set"):
            try:
                top = df.iloc[0]
                st.markdown(f"**Set Name:** {top['Set Name']}")
                st.markdown(f"**Profit:** {top['Profit']}")
                st.markdown(f"**Profit Margin:** {top['Profit Margin']}")
                st.markdown(f"**Set Selling Price:** {top['Set Selling Price']}")
                st.markdown(f"**Part Costs Total:** {top['Part Costs Total']}")
                st.markdown(f"**Volume (48h):** {top['Volume (48h)']}")
                st.markdown(f"**Score:** {top['Score']}")
                st.markdown(f"**Part Prices:** {top['Part Prices']}")
            except Exception:
                st.info("No top set details available.")

    st.markdown("---")
    st.subheader("📈 Statistical Analysis (Cumulative)")
    col1, col2 = st.columns([1,1])
    with col1:
        # Helper: load cumulative dataset from SQLite
        def load_cumulative_df():
            try:
                conn = sqlite3.connect(DB_PATH)
                query = "SELECT run_ts, platform, set_slug, set_name, profit, profit_margin, set_price, part_cost_total, volume_48h, score FROM set_results"
                hist_df = pd.read_sql_query(query, conn)
                conn.close()
                return hist_df
            except Exception as e:
                st.warning(f"No historical data yet or DB error: {e}")
                return None

        if st.button("Run Linear Regression (Profit vs. Volume) - All Runs"):
            try:
                hist_df = load_cumulative_df()
                if hist_df is None or len(hist_df) < 2:
                    st.warning("Not enough historical data to fit regression.")
                    raise ValueError("insufficient data")
                X = hist_df[['volume_48h']].values.astype(float)
                y = hist_df['profit'].values.astype(float)
                if len(X) < 2 or np.allclose(X, X[0]):
                    st.warning("Not enough variation in Volume to fit a regression.")
                else:
                    model = LinearRegression().fit(X, y)
                    coef = float(model.coef_[0])
                    intercept = float(model.intercept_)
                    r2 = float(model.score(X, y))
                    st.success(f"Profit = {coef:.4f} × Volume + {intercept:.4f}  (R² = {r2:.4f})")

                    # Build regression line using historical volume range
                    x_sorted = np.sort(X.flatten())
                    y_pred = coef * x_sorted + intercept

                    # Plot scatter + regression line without requiring statsmodels
                    fig2 = go.Figure()
                    fig2.add_trace(
                        go.Scatter(
                            x=hist_df['volume_48h'], y=hist_df['profit'], mode='markers',
                            marker=dict(color=hist_df['score'], colorscale='Purples', showscale=True),
                            text=hist_df['set_name'], name='Historical Data'
                        )
                    )
                    fig2.add_trace(
                        go.Scatter(
                            x=x_sorted, y=y_pred, mode='lines', name='Regression Line',
                            line=dict(color='#8f94fb', width=3)
                        )
                    )
                    fig2.update_layout(height=500, xaxis_title='Volume (48h)', yaxis_title='Profit')
                    st.plotly_chart(fig2, use_container_width=True)
                    st.balloons()
            except Exception as ex:
                st.info("Linear regression requires cumulative data from multiple runs. Run analysis a few times first.")
    with col2:
        st.info("24/7 Mode appends data every interval so regression improves over time. Adjust weights or toggles in the sidebar and rerun analysis.")

st.markdown("""
---
<small>Made with ❤️ for Warframe traders. Not affiliated with Digital Extremes.</small>
""", unsafe_allow_html=True) 