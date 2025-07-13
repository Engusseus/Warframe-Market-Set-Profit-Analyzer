# NOTE: Requires: streamlit, plotly, scikit-learn, streamlit-lottie, pandas, numpy
import streamlit as st
import pandas as pd
import plotly.express as px
from wf_market_analyzer import run_analysis_ui
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

# Custom CSS for Warframe theme, button hover, progress bar glow, confetti
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

st.set_page_config(page_title="Warframe Market Profit Analyzer", layout="wide", page_icon="💠")

st.title("💠 Warframe Market Profit Analyzer")
st.markdown("<h4>Analyze sets and uncover profits interactively!</h4>", unsafe_allow_html=True)

# Sidebar config
def sidebar_config():
    st.sidebar.header("Configuration")
    platform = st.sidebar.selectbox("Platform", ["pc", "ps4", "xbox", "switch"], index=0)
    profit_weight = st.sidebar.slider("Profit Weight", 0.0, 3.0, 1.0, 0.1)
    volume_weight = st.sidebar.slider("Volume Weight", 0.0, 3.0, 1.2, 0.1)
    profit_margin_weight = st.sidebar.slider("Profit Margin Weight", 0.0, 3.0, 0.0, 0.1)
    price_sample_size = st.sidebar.slider("Price Sample Size", 1, 10, 2, 1)
    use_median_pricing = st.sidebar.checkbox("Use Median Pricing", False)
    analyze_trends = st.sidebar.checkbox("Analyze Volume Trends", False)
    trend_days = st.sidebar.slider("Trend Days", 7, 90, 30, 1) if analyze_trends else 30
    debug = st.sidebar.checkbox("Debug Mode", False)
    # Explicitly cast all values to correct types
    return dict(
        platform=str(platform),
        profit_weight=float(profit_weight),
        volume_weight=float(volume_weight),
        profit_margin_weight=float(profit_margin_weight),
        price_sample_size=int(price_sample_size),
        use_median_pricing=bool(use_median_pricing),
        analyze_trends=bool(analyze_trends),
        trend_days=int(trend_days),
        debug=bool(debug),
    )

config = sidebar_config()

# Main UI
if 'data' not in st.session_state:
    st.session_state['data'] = None
    st.session_state['results'] = None

st.markdown("""
Run a full market analysis and get a ranked table of profitable sets. 
Click below to start! 🚀
""")

run_btn = st.button("Run Analysis", type="primary")

if run_btn:
    st.session_state['data'] = None
    st.session_state['results'] = None
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
                analyze_trends=bool(config['analyze_trends']),
                trend_days=int(config['trend_days']),
                debug=bool(config['debug'])
            )
            st.session_state['data'] = df
            st.session_state['results'] = results
            st.success("Analysis complete! 🎉")
            st.balloons()
        except Exception as e:
            st.error(f"API fetch failed – try again!\n{e}")

if st.session_state['data'] is not None:
    df = st.session_state['data']
    st.subheader("Results Table")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Profit vs. Volume Scatter Plot")
    fig = px.scatter(df, x='Volume (48h)', y='Profit', hover_name='Set Name', color='Score',
                     color_continuous_scale=px.colors.sequential.Purples, height=500)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Show Details for Top Set"):
        top = df.iloc[0]
        st.markdown(f"**Set Name:** {top['Set Name']}")
        st.markdown(f"**Profit:** {top['Profit']}")
        st.markdown(f"**Profit Margin:** {top['Profit Margin']}")
        st.markdown(f"**Set Selling Price:** {top['Set Selling Price']}")
        st.markdown(f"**Part Costs Total:** {top['Part Costs Total']}")
        st.markdown(f"**Volume (48h):** {top['Volume (48h)']}")
        st.markdown(f"**Score:** {top['Score']}")
        st.markdown(f"**Part Prices:** {top['Part Prices']}")

    st.markdown("---")
    st.subheader("📈 Statistical Analysis")
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Run Linear Regression (Profit vs. Volume)"):
            X = df[['Volume (48h)']].values
            y = df['Profit'].values
            model = LinearRegression().fit(X, y)
            coef = model.coef_[0]
            intercept = model.intercept_
            st.success(f"Profit = {coef:.2f} × Volume + {intercept:.2f}")
            # Plot with trendline
            fig2 = px.scatter(df, x='Volume (48h)', y='Profit', trendline='ols',
                              color='Score', color_continuous_scale=px.colors.sequential.Purples)
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown("<script>window.confetti && window.confetti();</script>", unsafe_allow_html=True)
    with col2:
        st.info("Try adjusting weights or toggles in the sidebar and rerun analysis for different results!")

st.markdown("""
---
<small>Made with ❤️ for Warframe traders. Not affiliated with Digital Extremes.</small>
""", unsafe_allow_html=True) 