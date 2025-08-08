# NOTE: Requires: streamlit, plotly, scikit-learn, streamlit-lottie, pandas, numpy
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wf_market_analyzer import run_analysis_ui
from config import DB_PATH
import sqlite3
from datetime import datetime, timedelta
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

# Initialize session state
if 'data' not in st.session_state:
    st.session_state['data'] = None
    st.session_state['results'] = None
    st.session_state['continuous'] = False
    st.session_state['interval_minutes'] = 60
    st.session_state['last_run_iso'] = None
    st.session_state['autorun_pending'] = False
    st.session_state['run_in_progress'] = False
    st.session_state.setdefault('cancel_token', {'stop': False})

# 24/7 autorun check at top of script
if st.session_state.get('continuous'):
    last_run = st.session_state.get('last_run_iso')
    if last_run:
        try:
            last_ts = datetime.fromisoformat(last_run)
            elapsed_min = (datetime.utcnow() - last_ts).total_seconds() / 60.0
            if elapsed_min >= float(st.session_state.get('interval_minutes', 60)):
                st.session_state['autorun_pending'] = True
        except Exception:
            pass
    else:
        # First run in continuous mode
        st.session_state['autorun_pending'] = True

# Reset stuck in-progress after timeout (10 minutes)
if st.session_state.get('run_in_progress') and st.session_state.get('last_run_iso'):
    try:
        last_ts = datetime.fromisoformat(st.session_state['last_run_iso'])
        if (datetime.utcnow() - last_ts).total_seconds() > 600:
            st.session_state['run_in_progress'] = False
    except Exception:
        st.session_state['run_in_progress'] = False

# Sidebar config
@st.cache_data(show_spinner=False)
def _static_constants():
    # Placeholder for any heavy static lookups (e.g., item lists) if needed
    return {"version": "1.0"}


def sidebar_config():
    st.sidebar.header("Configuration")
    platform = st.sidebar.selectbox("Platform", options=["pc", "xbox", "ps4", "switch"], index=0)
    profit_weight = st.sidebar.slider("Profit Weight", 0.0, 3.0, 1.0, 0.1)
    volume_weight = st.sidebar.slider("Volume Weight", 0.0, 3.0, 1.2, 0.1)
    profit_margin_weight = st.sidebar.slider("Profit Margin Weight", 0.0, 3.0, 0.0, 0.1)
    robust_score = st.sidebar.checkbox("Robust score (rank-based)", True)
    conservative_pricing = st.sidebar.checkbox("Conservative pricing (P25 sell / P75 buy)", True)
    price_sample_size = st.sidebar.slider("Minimum Online Sell Orders (Sample Size)", 1, 10, 2, 1,
                                          help="Minimum number of online sell orders required to include a set/part")
    min_profit = st.sidebar.number_input("Min profit", value=0.0, step=1.0)
    min_margin = st.sidebar.number_input("Min margin", value=0.0, step=0.01)
    min_volume = st.sidebar.number_input("Min 48h volume", value=1.0, step=1.0)
    analyze_trends = st.sidebar.checkbox("Analyze trends", False)
    trend_days = st.sidebar.slider("Trend days", 7, 60, 30, 1)
    trade_tax_percent = st.sidebar.number_input("Trade tax %", value=0.0, min_value=0.0, max_value=50.0, step=0.5)
    retention_days = st.sidebar.number_input("Retention (days)", value=90, min_value=7, max_value=365, step=1)
    debug = st.sidebar.checkbox("Debug Mode", False)
    # Explicitly cast all values to correct types
    return dict(
        platform=str(platform),
        profit_weight=float(profit_weight),
        volume_weight=float(volume_weight),
        profit_margin_weight=float(profit_margin_weight),
        robust_score=bool(robust_score),
        conservative_pricing=bool(conservative_pricing),
        price_sample_size=int(price_sample_size),
        use_median_pricing=False,
        use_statistics_for_pricing=True,
        analyze_trends=bool(analyze_trends),
        trend_days=int(trend_days),
        trade_tax_percent=float(trade_tax_percent),
        min_profit=float(min_profit),
        min_margin=float(min_margin),
        min_volume=float(min_volume),
        retention_days=int(retention_days),
        debug=bool(debug),
    )

config = sidebar_config()

# Main UI
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
    st.session_state['cancel_token']['stop'] = True
    st.info("Stopping after current in-flight tasks...")

if quit_btn:
    st.success("Quitting...")
    # Politely stop Streamlit script
    import sys
    raise SystemExit

def _run_analysis_now():
    """Execute a single analysis run with proper state management"""
    st.session_state['data'] = None
    st.session_state['results'] = None
    st.session_state['cancel_token']['stop'] = False
    st.session_state['run_in_progress'] = True
    
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
            df, results = run_analysis_ui(
                platform=str(config['platform']),
                profit_weight=float(config['profit_weight']),
                volume_weight=float(config['volume_weight']),
                profit_margin_weight=float(config['profit_margin_weight']),
                price_sample_size=int(config['price_sample_size']),
                use_median_pricing=bool(config['use_median_pricing']),
                use_statistics_for_pricing=bool(config.get('use_statistics_for_pricing', False)),
                conservative_pricing=bool(config.get('conservative_pricing', True)),
                robust_score=bool(config.get('robust_score', True)),
                analyze_trends=bool(config['analyze_trends']),
                trend_days=int(config['trend_days']),
                trade_tax_percent=float(config.get('trade_tax_percent', 0.0)),
                min_profit_threshold=float(config.get('min_profit', 0.0)),
                min_margin_threshold=float(config.get('min_margin', 0.0)),
                min_volume_threshold=float(config.get('min_volume', 0.0)),
                debug=bool(config['debug']),
                persist=True,
                progress_callback=on_progress,
                cancel_token=st.session_state['cancel_token']
            )
            st.session_state['data'] = df
            st.session_state['results'] = results
            st.session_state['last_run_iso'] = datetime.utcnow().isoformat()
            st.session_state['autorun_pending'] = False
            st.session_state['run_in_progress'] = False
            st.success("Analysis complete! 🎉")
            st.balloons()
        except Exception as e:
            st.session_state['run_in_progress'] = False
            st.error(f"API fetch failed – try again!\n{e}")

# Manual run trigger
if run_btn:
    _run_analysis_now()

# Auto-run trigger (single execution)
if st.session_state.get('autorun_pending') and not st.session_state.get('run_in_progress'):
    st.session_state['autorun_pending'] = False
    _run_analysis_now()
    st.rerun()

# Display results
if st.session_state['data'] is not None:
    df = st.session_state['data']
    st.subheader("Results Table")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Download CSV
    try:
        csv_bytes = df.to_csv(index=False).encode('utf-8') if df is not None else None
        if csv_bytes:
            st.download_button("Download CSV", csv_bytes, file_name="set_profit_analysis.csv", mime="text/csv")
    except Exception:
        pass

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
                st.markdown(f"**Margin:** {top['Margin']}")
                st.markdown(f"**Price (sell):** {top['Price (sell)']}")
                st.markdown(f"**Price (cost):** {top['Price (cost)']}")
                st.markdown(f"**Volume (48h):** {top['Volume (48h)']}")
                if 'ETA (h)' in top:
                    st.markdown(f"**ETA (h):** {top['ETA (h)']}")
                if 'Profit/day' in top:
                    st.markdown(f"**Profit/day:** {top['Profit/day']}")
                if f"Trend % ({int(config['trend_days'])}d)" in df.columns:
                    st.markdown(f"**Trend % ({int(config['trend_days'])}d):** {top[f'Trend % ({int(config['trend_days'])}d)']}")
                st.markdown(f"**Score:** {top['Score']}")
                st.markdown(f"**Part Prices:** {top['Part Prices']}")
                # External link
                import urllib.parse
                slug = top.get('Set Slug') if 'Set Slug' in df.columns else None
                if slug:
                    st.markdown(f"[Open on warframe.market](https://warframe.market/items/{urllib.parse.quote(slug)})")

                # Sparkline for price/volume trend (cached)
                import requests
                @st.cache_data(show_spinner=False)
                def fetch_series(set_slug: str, days: int, platform: str):
                    headers = {"Platform": platform, "Language": "en", "Accept": "application/json"}
                    url = f"https://api.warframe.market/v1/items/{set_slug}/statistics"
                    r = requests.get(url, headers=headers, timeout=30)
                    r.raise_for_status()
                    data = r.json()
                    stats = data.get('payload', {}).get('statistics_closed', {}).get('90days', [])
                    stats = stats[-int(days):]
                    dates = [s.get('datetime') for s in stats]
                    vols = [s.get('volume', 0) for s in stats]
                    meds = [s.get('median') or s.get('avg_price') for s in stats]
                    return dates, vols, meds

                try:
                    dates, vols, meds = fetch_series(slug, int(config['trend_days']), str(config['platform']))
                    if dates and vols:
                        import plotly.graph_objs as go
                        spark = go.Figure()
                        spark.add_trace(go.Scatter(x=dates, y=vols, mode='lines', name='Volume', line=dict(color='#8f94fb')))
                        spark.update_layout(height=200, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
                        st.plotly_chart(spark, use_container_width=True)
                except Exception:
                    pass
            except Exception:
                st.info("No top set details available.")

    st.markdown("---")
    st.subheader("📈 Statistical Analysis (Cumulative)")
    col1, col2 = st.columns([1,1])
    with col1:
        # Helper: load cumulative dataset from normalized schema
        def load_cumulative_df():
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                # Get latest run for current platform
                cur.execute("""
                    SELECT r.run_id, r.ts_utc, r.platform, r.config_json
                    FROM runs r
                    WHERE r.platform = ?
                    ORDER BY r.ts_utc DESC
                    LIMIT 1
                """, (config['platform'],))
                run_row = cur.fetchone()
                if not run_row:
                    st.warning("No historical data yet.")
                    return None
                
                run_id = run_row[0]
                # Get metrics for that run
                cur.execute("""
                    SELECT sm.*
                    FROM set_metrics sm
                    WHERE sm.run_id = ?
                    ORDER BY sm.score DESC
                """, (run_id,))
                rows = cur.fetchall()
                conn.close()
                
                if not rows:
                    st.warning("No metrics found for latest run.")
                    return None
                
                # Convert to DataFrame
                columns = ['run_id', 'set_slug', 'set_name', 'price_sell', 'price_cost', 'profit', 'margin',
                          'volume_48h', 'eta_hours', 'profit_per_day', 'score', 'trend_pct',
                          'conservative_pricing', 'robust_score', 'trade_tax_percent']
                hist_df = pd.DataFrame(rows, columns=columns)
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

    # 24/7 Mode: display status and retention cleanup
    if st.session_state['continuous']:
        st.markdown("---")
        st.subheader("24/7 Mode Status")
        last = st.session_state['last_run_iso'] or "Never"
        st.markdown(f"Last run (UTC): {last}")
        st.markdown(f"Interval: {int(st.session_state['interval_minutes'])} minutes")
        
        # Retention cleanup
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA synchronous=NORMAL;")
            cur.execute("PRAGMA foreign_keys=ON;")
            # Drop runs older than retention_days
            cur.execute("SELECT run_id, ts_utc FROM runs")
            rows = cur.fetchall()
            to_delete = []
            cutoff = datetime.utcnow() - timedelta(days=int(config.get('retention_days', 90)))
            for rid, ts_s in rows:
                try:
                    ts = datetime.fromisoformat(ts_s)
                    if ts < cutoff:
                        to_delete.append(rid)
                except Exception:
                    continue
            if to_delete:
                cur.execute("BEGIN;")
                cur.executemany("DELETE FROM runs WHERE run_id = ?", [(rid,) for rid in to_delete])
                conn.commit()
                st.info(f"Cleaned up {len(to_delete)} old runs (older than {config.get('retention_days', 90)} days)")
            conn.close()
        except Exception:
            pass

st.markdown("""
---
<small>Made with ❤️ for Warframe traders. Not affiliated with Digital Extremes.</small>
""", unsafe_allow_html=True) 