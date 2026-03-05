import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, EMAIndicator
from datetime import datetime

st.set_page_config(
    page_title="NSE Sector Intelligence Terminal",
    layout="wide",
)

st.title("📊 NSE Sector Intelligence Terminal")

# ─────────────────────────────────────────────────────────────────
# STOCK LIST
# ─────────────────────────────────────────────────────────────────
stocks = {
    "RELIANCE.NS":  ("Energy",        "Oil & Gas"),
    "TCS.NS":       ("IT",            "IT Services"),
    "HDFCBANK.NS":  ("Banking",       "Private Bank"),
    "ICICIBANK.NS": ("Banking",       "Private Bank"),
    "INFY.NS":      ("IT",            "IT Services"),
    "HINDUNILVR.NS":("FMCG",         "Consumer Goods"),
    "ITC.NS":       ("FMCG",         "Consumer Goods"),
    "SBIN.NS":      ("Banking",       "PSU Bank"),
    "BHARTIARTL.NS":("Telecom",       "Telecom"),
    "LT.NS":        ("Capital Goods", "Engineering"),
    "KOTAKBANK.NS": ("Banking",       "Private Bank"),
    "AXISBANK.NS":  ("Banking",       "Private Bank"),
    "ASIANPAINT.NS":("Chemicals",     "Paints"),
    "MARUTI.NS":    ("Auto",          "Automobile"),
    "TITAN.NS":     ("Consumer",      "Jewellery"),
    "ULTRACEMCO.NS":("Cement",        "Cement"),
    "BAJFINANCE.NS":("Finance",       "NBFC"),
    "WIPRO.NS":     ("IT",            "IT Services"),
    "NESTLEIND.NS": ("FMCG",         "Consumer Goods"),
    "TATAMOTORS.NS":("Auto",          "Automobile"),
    "SUNPHARMA.NS": ("Pharma",        "Pharmaceuticals"),
    "POWERGRID.NS": ("Power",         "Utilities"),
    "NTPC.NS":      ("Power",         "Utilities"),
    "JSWSTEEL.NS":  ("Metals",        "Steel"),
    "TATASTEEL.NS": ("Metals",        "Steel"),
    "GRASIM.NS":    ("Cement",        "Cement"),
    "HCLTECH.NS":   ("IT",            "IT Services"),
    "TECHM.NS":     ("IT",            "IT Services"),
    "ADANIENT.NS":  ("Conglomerate",  "Adani Group"),
    "ADANIPORTS.NS":("Logistics",     "Ports"),
    "BAJAJFINSV.NS":("Finance",       "Financial Services"),
    "INDUSINDBK.NS":("Banking",       "Private Bank"),
    "ONGC.NS":      ("Energy",        "Oil & Gas"),
    "COALINDIA.NS": ("Energy",        "Coal"),
    "DRREDDY.NS":   ("Pharma",        "Pharmaceuticals"),
    "CIPLA.NS":     ("Pharma",        "Pharmaceuticals"),
    "DIVISLAB.NS":  ("Pharma",        "Pharmaceuticals"),
    "BPCL.NS":      ("Energy",        "Oil & Gas"),
    "HEROMOTOCO.NS":("Auto",          "Automobile"),
    "EICHERMOT.NS": ("Auto",          "Automobile"),
    "APOLLOHOSP.NS":("Healthcare",    "Hospitals"),
    "BRITANNIA.NS": ("FMCG",         "Consumer Goods"),
    "DMART.NS":     ("Retail",        "Retail"),
    "PIDILITIND.NS":("Chemicals",     "Adhesives"),
    "DABUR.NS":     ("FMCG",         "Consumer Goods"),
    "BERGEPAINT.NS":("Chemicals",     "Paints"),
    "SRF.NS":       ("Chemicals",     "Specialty Chemicals"),
    "M&M.NS":       ("Auto",          "Automobile"),
    "SIEMENS.NS":   ("Capital Goods", "Engineering"),
    "ABB.NS":       ("Capital Goods", "Engineering"),
}

symbols     = list(stocks.keys())
BENCHMARK   = "^NSEI"   # Nifty 50 – RS line denominator

# ─────────────────────────────────────────────────────────────────
# DATA DOWNLOAD  (1 year so RS-new-high lookback has enough data)
# ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_data(syms):
    all_syms = syms + [BENCHMARK]
    data = yf.download(
        tickers=all_syms,
        period="1y",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
    )
    return data

data = load_data(symbols)

# ─────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────

def ema(series, window):
    return EMAIndicator(series, window=window, fillna=True).ema_indicator()


def detect_pocket_pivot(df):
    """
    Classic Pocket Pivot:
      • Up-day  (Close > prev Close)
      • Today's Volume > highest down-volume day in prior 10 sessions
    Returns a boolean Series.
    """
    df = df.copy()
    up_day   = df["Close"] > df["Close"].shift(1)
    down_vol = np.where(df["Close"] < df["Close"].shift(1), df["Volume"], 0)
    down_vol_series       = pd.Series(down_vol, index=df.index)
    max_down_vol_prior_10 = down_vol_series.shift(1).rolling(10, min_periods=1).max()
    return up_day & (df["Volume"] > max_down_vol_prior_10)


def detect_rs_new_high(close_series, bench_series):
    """
    RS Line  = stock_close / nifty_close  (both index-aligned)
    RS-New-High-Before-Price:
      RS line is at / near a new 52-week high  BUT
      the stock price has NOT yet reached its 52-week high.
    Returns: rs_line (Series), signal (boolean Series)
    """
    aligned         = pd.concat([close_series, bench_series], axis=1).dropna()
    aligned.columns = ["close", "bench"]
    aligned["rs"]   = aligned["close"] / aligned["bench"]

    lookback            = min(len(aligned), 252)          # up to 1 year
    aligned["rs_high"]  = aligned["rs"].rolling(lookback, min_periods=30).max()
    aligned["px_high"]  = aligned["close"].rolling(lookback, min_periods=30).max()

    rs_at_high    = aligned["rs"]     >= aligned["rs_high"] * 0.99
    price_at_high = aligned["close"]  >= aligned["px_high"] * 0.99

    signal = rs_at_high & ~price_at_high
    return aligned["rs"].reindex(close_series.index), signal.reindex(close_series.index, fill_value=False)


# ─────────────────────────────────────────────────────────────────
# BENCHMARK CLOSE  (extract from multi-level download)
# ─────────────────────────────────────────────────────────────────
try:
    benchmark_close = data[BENCHMARK]["Close"].dropna()
except Exception:
    benchmark_close = None

# ─────────────────────────────────────────────────────────────────
# INDICATOR CALCULATION LOOP
# ─────────────────────────────────────────────────────────────────
results   = []
stock_dfs = {}   # full per-symbol DataFrame kept for charting

for symbol in symbols:
    try:
        df = data[symbol].copy()
        df.dropna(inplace=True)

        if len(df) < 50:
            continue

        # Core indicators
        df["RSI"]   = RSIIndicator(df["Close"], window=14, fillna=True).rsi()
        df["Range"] = df["High"] - df["Low"]

        sma20 = SMAIndicator(df["Close"], 20).sma_indicator()
        sma50 = SMAIndicator(df["Close"], 50).sma_indicator()

        # EMAs
        df["EMA5"]  = ema(df["Close"],  5)
        df["EMA10"] = ema(df["Close"], 10)
        df["EMA21"] = ema(df["Close"], 21)
        df["EMA50"] = ema(df["Close"], 50)

        # Pocket Pivot
        df["PocketPivot"] = detect_pocket_pivot(df)

        # RS Line & RS-New-High-Before-Price
        if benchmark_close is not None:
            df["RS_Line"], df["RS_NewHigh"] = detect_rs_new_high(
                df["Close"], benchmark_close
            )
        else:
            df["RS_Line"]   = np.nan
            df["RS_NewHigh"] = False

        last = df.iloc[-1]
        prev = df.iloc[-2]

        change   = (last["Close"] - prev["Close"]) / prev["Close"] * 100
        nr7      = last["Range"] <= df["Range"].tail(7).min()

        momentum = (
            (last["RSI"] / 100) * 40 +
            (change / 5)        * 30 +
            (last["Close"] / sma20.iloc[-1]) * 30
        )
        momentum = max(0, min(momentum, 100))

        sector, industry = stocks[symbol]
        stock_dfs[symbol] = df

        results.append({
            "Symbol":       symbol,
            "Sector":       sector,
            "Industry":     industry,
            "Price":        round(float(last["Close"]),  2),
            "Change%":      round(float(change),         2),
            "RSI":          round(float(last["RSI"]),    1),
            "Momentum":     round(float(momentum),       1),
            "NR7":          bool(nr7),
            "PocketPivot":  bool(last["PocketPivot"]),
            "RS_NewHigh":   bool(last["RS_NewHigh"]),
            "Above20DMA":   bool(last["Close"] > sma20.iloc[-1]),
            "Above50DMA":   bool(last["Close"] > sma50.iloc[-1]),
        })

    except Exception as e:
        st.warning(f"⚠️ Skipped {symbol}: {e}")

df_main = pd.DataFrame(results)

# ─────────────────────────────────────────────────────────────────
# SECTOR AGGREGATE
# ─────────────────────────────────────────────────────────────────
sector_table = df_main.groupby("Sector").agg({
    "Change%":  "mean",
    "Momentum": "mean",
    "RSI":      "mean",
}).reset_index()

# ─────────────────────────────────────────────────────────────────
# SIDEBAR – FILTERS
# ─────────────────────────────────────────────────────────────────
st.sidebar.title("Market Filters")

rsi_min    = st.sidebar.slider("RSI Minimum",        0, 100, 50)
mom_min    = st.sidebar.slider("Momentum Minimum",   0, 100, 40)
show_pp    = st.sidebar.checkbox("Pocket Pivot only",          False)
show_rsnh  = st.sidebar.checkbox("RS New High (before price)", False)

filtered = df_main[
    (df_main["RSI"]      > rsi_min) &
    (df_main["Momentum"] > mom_min)
]
if show_pp:
    filtered = filtered[filtered["PocketPivot"]]
if show_rsnh:
    filtered = filtered[filtered["RS_NewHigh"]]

# ─────────────────────────────────────────────────────────────────
# CANDLESTICK CHART BUILDER
# ─────────────────────────────────────────────────────────────────
def build_chart(symbol, df, ema_sel):
    ema_colors = {5: "#00FFFF", 10: "#FF8C00", 21: "#FFFF00", 50: "#FF00FF"}

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.58, 0.18, 0.24],
        vertical_spacing=0.03,
        subplot_titles=[
            f"{symbol}  —  Candlestick + EMA",
            "Volume",
            "RS Line vs Nifty 50  (⭐ = RS New High Before Price High)"
        ],
    )

    # ── Candlestick ──────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        increasing_line_color="#26A69A",
        decreasing_line_color="#EF5350",
        name="Price",
    ), row=1, col=1)

    # ── EMA overlays ─────────────────────────────────────────────
    for e in ema_sel:
        col = f"EMA{e}"
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col],
                name=f"EMA {e}",
                line=dict(color=ema_colors[e], width=1.4),
                hovertemplate=f"EMA{e}: %{{y:.2f}}<extra></extra>",
            ), row=1, col=1)

    # ── Pocket Pivot markers (▲ below candle) ────────────────────
    pp_days = df[df["PocketPivot"] == True]
    if not pp_days.empty:
        fig.add_trace(go.Scatter(
            x=pp_days.index,
            y=pp_days["Low"] * 0.988,
            mode="markers",
            marker=dict(symbol="triangle-up", size=11, color="lime",
                        line=dict(color="darkgreen", width=1)),
            name="Pocket Pivot 🟢",
            hovertemplate="Pocket Pivot<br>%{x}<extra></extra>",
        ), row=1, col=1)

    # ── Volume bars ──────────────────────────────────────────────
    vol_colors = [
        "#26A69A" if c >= o else "#EF5350"
        for c, o in zip(df["Close"], df["Open"])
    ]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        marker_color=vol_colors,
        name="Volume", showlegend=False,
        hovertemplate="Vol: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    # ── RS Line ──────────────────────────────────────────────────
    if "RS_Line" in df.columns and df["RS_Line"].notna().any():
        rs_vals = df["RS_Line"]
        # Normalise to 100 at start for readability
        rs_norm = (rs_vals / rs_vals.dropna().iloc[0]) * 100

        fig.add_trace(go.Scatter(
            x=df.index, y=rs_norm,
            name="RS Line",
            line=dict(color="#64B5F6", width=1.8),
            hovertemplate="RS: %{y:.2f}<extra></extra>",
        ), row=3, col=1)

        # ⭐ RS New High Before Price High
        nh_days = df[df["RS_NewHigh"] == True]
        if not nh_days.empty:
            nh_rs_norm = (nh_days["RS_Line"] / rs_vals.dropna().iloc[0]) * 100
            fig.add_trace(go.Scatter(
                x=nh_days.index,
                y=nh_rs_norm,
                mode="markers",
                marker=dict(symbol="star", size=14, color="gold",
                            line=dict(color="darkorange", width=1)),
                name="RS New High ⭐",
                hovertemplate="RS New High Before Price<br>%{x}<extra></extra>",
            ), row=3, col=1)

    # ── Layout ───────────────────────────────────────────────────
    fig.update_layout(
        height=820,
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h", yanchor="bottom",
            y=1.01, xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
        margin=dict(l=50, r=30, t=60, b=30),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#1E2130", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#1E2130", zeroline=False)

    return fig


# ═════════════════════════════════════════════════════════════════
# DASHBOARD LAYOUT
# ═════════════════════════════════════════════════════════════════

# ── 1. Sector charts ─────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("Sector Performance")
    fig_sp = px.bar(
        sector_table, x="Sector", y="Change%",
        color="Change%", color_continuous_scale="RdYlGn",
        template="plotly_dark",
    )
    st.plotly_chart(fig_sp, use_container_width=True)

with col2:
    st.subheader("Sector Momentum")
    fig_sm = px.bar(
        sector_table, x="Sector", y="Momentum",
        color="Momentum", color_continuous_scale="Blues",
        template="plotly_dark",
    )
    st.plotly_chart(fig_sm, use_container_width=True)

# ── 2. Heatmap ───────────────────────────────────────────────────
st.subheader("Market Heatmap")
heat = px.treemap(
    df_main,
    path=["Sector", "Symbol"],
    values="Momentum",
    color="Change%",
    color_continuous_scale="RdYlGn",
    template="plotly_dark",
    hover_data={"RSI": True, "PocketPivot": True, "RS_NewHigh": True},
)
st.plotly_chart(heat, use_container_width=True)

# ── 3. Market Breadth ────────────────────────────────────────────
st.subheader("Market Breadth")
breadth20 = (df_main["Above20DMA"].sum() / len(df_main)) * 100
breadth50 = (df_main["Above50DMA"].sum() / len(df_main)) * 100
pp_count  = int(df_main["PocketPivot"].sum())
rs_count  = int(df_main["RS_NewHigh"].sum())

b1, b2, b3, b4 = st.columns(4)
b1.metric("Above 20 DMA",      f"{round(breadth20, 1)}%")
b2.metric("Above 50 DMA",      f"{round(breadth50, 1)}%")
b3.metric("Pocket Pivots Today", pp_count)
b4.metric("RS New High (Before Price)", rs_count)

st.divider()

# ── 4. Candlestick Chart ─────────────────────────────────────────
st.subheader("📈 Candlestick Chart with EMA / Pocket Pivot / RS Line")

chart_col1, chart_col2 = st.columns([2, 1])

with chart_col1:
    chart_sym = st.selectbox(
        "Select Stock",
        options=list(stock_dfs.keys()),
        index=0,
    )

with chart_col2:
    ema_choices = st.multiselect(
        "EMA Overlays",
        options=[5, 10, 21, 50],
        default=[21, 50],
    )

if chart_sym and chart_sym in stock_dfs:
    fig_chart = build_chart(chart_sym, stock_dfs[chart_sym], ema_choices)
    st.plotly_chart(fig_chart, use_container_width=True)

    # Legend guide
    lc1, lc2, lc3 = st.columns(3)
    lc1.info("🟢 **Pocket Pivot** — Up-day volume exceeds highest down-volume of prior 10 sessions")
    lc2.warning("⭐ **RS New High** — RS Line (Stock/Nifty) at new high while price has NOT made new high yet → early strength signal")
    lc3.success("**EMA colours** — Cyan=5 · Orange=10 · Yellow=21 · Magenta=50")

st.divider()

# ── 5. NR7 Scanner ───────────────────────────────────────────────
st.subheader("NR7 — Volatility Contraction")
nr7_table = df_main[df_main["NR7"]]
if nr7_table.empty:
    st.info("No NR7 stocks today.")
else:
    st.dataframe(nr7_table, use_container_width=True)

# ── 6. Pocket Pivot Scanner ──────────────────────────────────────
st.subheader("🟢 Pocket Pivot Scanner")
pp_table = df_main[df_main["PocketPivot"]].sort_values("Momentum", ascending=False)
if pp_table.empty:
    st.info("No Pocket Pivots detected today.")
else:
    st.dataframe(pp_table, use_container_width=True)

# ── 7. RS New High Scanner ───────────────────────────────────────
st.subheader("⭐ RS New High Before Price High")
st.caption(
    "These stocks show **relative strength** vs Nifty 50 at a new high "
    "while their own price has NOT yet broken out — a classic early-entry signal."
)
rs_table = df_main[df_main["RS_NewHigh"]].sort_values("Momentum", ascending=False)
if rs_table.empty:
    st.info("No RS New High signals today.")
else:
    st.dataframe(rs_table, use_container_width=True)

# ── 8. Top Momentum ──────────────────────────────────────────────
st.subheader("Top Momentum Stocks")
leaders = df_main.sort_values("Momentum", ascending=False).head(10)
fig_mom = px.bar(
    leaders, x="Symbol", y="Momentum",
    color="Momentum", color_continuous_scale="Teal",
    template="plotly_dark",
)
st.plotly_chart(fig_mom, use_container_width=True)

# ── 9. Full Screener ─────────────────────────────────────────────
st.subheader("📋 Stock Screener")

# Emoji flags for boolean columns
display_df = filtered.copy()
for col in ["NR7", "PocketPivot", "RS_NewHigh", "Above20DMA", "Above50DMA"]:
    display_df[col] = display_df[col].map({True: "✅", False: ""})

st.dataframe(
    display_df.sort_values("Momentum", ascending=False),
    use_container_width=True,
)

st.caption(f"Last Updated : {datetime.now().strftime('%d %b %Y  %H:%M:%S')}")
