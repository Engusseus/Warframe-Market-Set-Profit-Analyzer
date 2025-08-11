# NOTE: Requires: streamlit, plotly, scikit-learn, streamlit-lottie, pandas, numpy
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wf_market_analyzer import run_analysis_ui
from config import DB_PATH
import sqlite3
from datetime import datetime
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

# Main UI
if 'data' not in st.session_state:
    st.session_state['data'] = None
    st.session_state['results'] = None
    st.session_state['continuous'] = False
    st.session_state['interval_minutes'] = 60
    st.session_state['last_run'] = None

st.markdown("""
Run a full market analysis and get a ranked table of profitable sets. 
Click below to start! 🚀
""")

col_run, col_toggle = st.columns([2, 2])
with col_run:
    run_btn = st.button("Run Analysis", type="primary")
    stop_btn = st.button("Stop")
    quit_btn = st.button("Quit")
with col_toggle:
    st.checkbox("24/7 Mode", key='continuous', help="Continuously fetch and append data.")
    if st.session_state['continuous']:
        st.session_state['interval_minutes'] = st.number_input(
            "Interval (minutes)", min_value=5, max_value=240, value=60, step=5
        )

if stop_btn:
    # Signal stop by setting a flag in session
    st.session_state['cancel'] = True
    st.info("Stopping after current in-flight tasks...")

if quit_btn:
    st.session_state['cancel'] = True
    st.success("Quitting...")
    # Streamlit 1.32+: use st.query_params to avoid deprecation warning
    try:
        st.query_params.update({"app_shutdown": "1"})
    except Exception:
        pass
    # Force terminate the script
    import os, sys
    os._exit(0)

if run_btn:
    st.session_state['data'] = None
    st.session_state['results'] = None
    st.session_state['cancel'] = False
    # Progress UI: live counter + ETA + progress bar
    progress_placeholder = st.empty()
    bar = st.progress(0, text="Preparing...")
    counter = st.empty()
    eta = st.empty()
    start_ts = datetime.utcnow()

    def on_progress(processed: int, total: int):
        pct = int((processed / total) * 100) if total else 0
        bar.progress(min(pct, 100), text=f"Analyzing sets... {pct}%")
        counter.markdown(f"Processed {processed} of {total} sets")
        if processed > 0:
            elapsed = (datetime.utcnow() - start_ts).total_seconds()
            rate = processed / max(elapsed, 1e-6)
            remaining = (total - processed) / max(rate, 1e-6)
            eta.markdown(f"ETA: ~{int(remaining)}s")
        else:
            eta.markdown("ETA: estimating...")

    with st.spinner("Fetching and analyzing sets... this may take a minute!"):
        if st_lottie and lottie_loading:
            st_lottie(lottie_loading, height=120, key="loading")
        try:
            # Explicitly cast all config values to correct types for run_analysis_ui
            df, results = run_analysis_ui(
                platform=str(config['platform']),
                profit_weight=float(config['profit_weight']),
                volume_weight=float(config['volume_weight']),
                profit_margin_weight=float(config['profit_margin_weight']),
                price_sample_size=int(config['price_sample_size']),
                use_median_pricing=bool(config['use_median_pricing']),
                use_statistics_for_pricing=bool(config.get('use_statistics_for_pricing', False)),
                analyze_trends=bool(config['analyze_trends']),
                trend_days=int(config['trend_days']),
                debug=bool(config['debug']),
                persist=True,
                progress_callback=on_progress,
                cancel_token={"stop": st.session_state.get('cancel', False)}
            )
            st.session_state['data'] = df
            st.session_state['results'] = results
            st.session_state['last_run'] = datetime.utcnow().isoformat()
            st.success("Analysis complete! 🎉")
            st.balloons()
        except Exception as e:
            st.error(f"API fetch failed – try again!\n{e}")

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

    # 24/7 Mode: display status and schedule next run
    if st.session_state['continuous']:
        st.markdown("---")
        st.subheader("24/7 Mode Status")
        last = st.session_state['last_run'] or "Never"
        st.markdown(f"Last run (UTC): {last}")
        st.markdown(f"Interval: {int(st.session_state['interval_minutes'])} minutes")
        # Use Streamlit autorefresh to trigger runs
        # Note: The rerun will re-enter the page and the user can click Run Analysis once; for true unattended
        # operation, we trigger programmatic runs as well
        import time
        from streamlit.runtime.scriptrunner import add_script_run_ctx
        # Programmatic auto-run when interval has elapsed
        try:
            if st.session_state['last_run']:
                last_ts = datetime.fromisoformat(st.session_state['last_run'])
                elapsed_min = (datetime.utcnow() - last_ts).total_seconds() / 60.0
                if elapsed_min >= float(st.session_state['interval_minutes']):
                    # Trigger a run automatically
                    st.experimental_rerun()
        except Exception:
            pass

st.markdown("""
---
<small>Made with ❤️ for Warframe traders. Not affiliated with Digital Extremes.</small>
""", unsafe_allow_html=True) 