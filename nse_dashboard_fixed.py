import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from datetime import datetime
import time

st.set_page_config(
    page_title="NSE Sector Intelligence Terminal",
    layout="wide",
)

st.title("📊 NSE Sector Intelligence Terminal")

# ----------------------------------------------------
# HARD CODED NIFTY 100 STOCK LIST
# (Expand if needed)
# ----------------------------------------------------

stocks = {

"RELIANCE.NS":("Energy","Oil & Gas"),
"TCS.NS":("IT","IT Services"),
"HDFCBANK.NS":("Banking","Private Bank"),
"ICICIBANK.NS":("Banking","Private Bank"),
"INFY.NS":("IT","IT Services"),
"HINDUNILVR.NS":("FMCG","Consumer Goods"),
"ITC.NS":("FMCG","Consumer Goods"),
"SBIN.NS":("Banking","PSU Bank"),
"BHARTIARTL.NS":("Telecom","Telecom"),
"LT.NS":("Capital Goods","Engineering"),
"KOTAKBANK.NS":("Banking","Private Bank"),
"AXISBANK.NS":("Banking","Private Bank"),
"ASIANPAINT.NS":("Chemicals","Paints"),
"MARUTI.NS":("Auto","Automobile"),
"TITAN.NS":("Consumer","Jewellery"),
"ULTRACEMCO.NS":("Cement","Cement"),
"BAJFINANCE.NS":("Finance","NBFC"),
"WIPRO.NS":("IT","IT Services"),
"NESTLEIND.NS":("FMCG","Consumer Goods"),
"TATAMOTORS.NS":("Auto","Automobile"),
"SUNPHARMA.NS":("Pharma","Pharmaceuticals"),
"POWERGRID.NS":("Power","Utilities"),
"NTPC.NS":("Power","Utilities"),
"JSWSTEEL.NS":("Metals","Steel"),
"TATASTEEL.NS":("Metals","Steel"),
"GRASIM.NS":("Cement","Cement"),
"HCLTECH.NS":("IT","IT Services"),
"TECHM.NS":("IT","IT Services"),
"ADANIENT.NS":("Conglomerate","Adani Group"),
"ADANIPORTS.NS":("Logistics","Ports"),
"BAJAJFINSV.NS":("Finance","Financial Services"),
"INDUSINDBK.NS":("Banking","Private Bank"),
"ONGC.NS":("Energy","Oil & Gas"),
"COALINDIA.NS":("Energy","Coal"),
"DRREDDY.NS":("Pharma","Pharmaceuticals"),
"CIPLA.NS":("Pharma","Pharmaceuticals"),
"DIVISLAB.NS":("Pharma","Pharmaceuticals"),
"BPCL.NS":("Energy","Oil & Gas"),
"HEROMOTOCO.NS":("Auto","Automobile"),
"EICHERMOT.NS":("Auto","Automobile"),
"APOLLOHOSP.NS":("Healthcare","Hospitals"),
"BRITANNIA.NS":("FMCG","Consumer Goods"),
"DMART.NS":("Retail","Retail"),
"PIDILITIND.NS":("Chemicals","Adhesives"),
"DABUR.NS":("FMCG","Consumer Goods"),
"BERGEPAINT.NS":("Chemicals","Paints"),
"SRF.NS":("Chemicals","Specialty Chemicals"),
"M&M.NS":("Auto","Automobile"),
"SIEMENS.NS":("Capital Goods","Engineering"),
"ABB.NS":("Capital Goods","Engineering")

}

symbols = list(stocks.keys())

# ----------------------------------------------------
# DATA DOWNLOAD
# ----------------------------------------------------

@st.cache_data(ttl=600)
def load_data(symbols):

    data = yf.download(
        tickers=symbols,
        period="6mo",
        interval="1d",
        group_by="ticker",
        auto_adjust=True
    )

    return data

data = load_data(symbols)

# ----------------------------------------------------
# CALCULATE INDICATORS
# ----------------------------------------------------

results = []

for symbol in symbols:

    try:

        df = data[symbol].copy()

        df.dropna(inplace=True)

        if len(df) < 50:
            continue

        rsi = RSIIndicator(df["Close"], window=14, fillna=True).rsi()

        df["RSI"] = rsi

        df["Range"] = df["High"] - df["Low"]

        sma20 = SMAIndicator(df["Close"],20).sma_indicator()
        sma50 = SMAIndicator(df["Close"],50).sma_indicator()

        last = df.iloc[-1]
        prev = df.iloc[-2]

        change = (last["Close"]-prev["Close"])/prev["Close"]*100

        nr7 = last["Range"] <= df["Range"].tail(7).min()

        momentum = (
            (last["RSI"]/100)*40 +
            (change/5)*30 +
            (last["Close"]/sma20.iloc[-1])*30
        )

        momentum = max(0,min(momentum,100))

        sector,industry = stocks[symbol]

        results.append({

        "Symbol":symbol,
        "Sector":sector,
        "Industry":industry,
        "Price":last["Close"],
        "Change":change,
        "RSI":last["RSI"],
        "NR7":nr7,
        "Momentum":momentum,
        "Above20":last["Close"]>sma20.iloc[-1],
        "Above50":last["Close"]>sma50.iloc[-1]

        })

    except Exception as e:
        st.warning(f"⚠️ Skipped {symbol}: {e}")

df = pd.DataFrame(results)

# ----------------------------------------------------
# SECTOR ANALYTICS
# ----------------------------------------------------

sector_table = df.groupby("Sector").agg({

"Change":"mean",
"Momentum":"mean",
"RSI":"mean"

}).reset_index()

# ----------------------------------------------------
# SIDEBAR
# ----------------------------------------------------

st.sidebar.title("Market Filters")

rsi_min = st.sidebar.slider("RSI Minimum",0,100,50)
mom_min = st.sidebar.slider("Momentum Minimum",0,100,40)

filtered = df[(df["RSI"]>rsi_min)&(df["Momentum"]>mom_min)]

# ----------------------------------------------------
# DASHBOARD LAYOUT
# ----------------------------------------------------

col1,col2 = st.columns(2)

with col1:

    st.subheader("Sector Performance")

    fig = px.bar(
        sector_table,
        x="Sector",
        y="Change",
        color="Change",
        color_continuous_scale="RdYlGn"
    )

    st.plotly_chart(fig,use_container_width=True)

with col2:

    st.subheader("Sector Momentum")

    fig2 = px.bar(
        sector_table,
        x="Sector",
        y="Momentum",
        color="Momentum"
    )

    st.plotly_chart(fig2,use_container_width=True)

# ----------------------------------------------------
# HEATMAP
# ----------------------------------------------------

st.subheader("Market Heatmap")

heat = px.treemap(
    df,
    path=["Sector","Symbol"],
    values="Momentum",
    color="Change",
    color_continuous_scale="RdYlGn"
)

st.plotly_chart(heat,use_container_width=True)

# ----------------------------------------------------
# BREADTH INDICATORS
# ----------------------------------------------------

st.subheader("Market Breadth")

breadth1 = (df["Above20"].sum()/len(df))*100
breadth2 = (df["Above50"].sum()/len(df))*100

b1,b2 = st.columns(2)

b1.metric("Above 20 DMA %",round(breadth1,1))
b2.metric("Above 50 DMA %",round(breadth2,1))

# ----------------------------------------------------
# NR7 SCANNER
# ----------------------------------------------------

st.subheader("NR7 Volatility Contraction")

nr7_table = df[df["NR7"]]

st.dataframe(nr7_table,use_container_width=True)

# ----------------------------------------------------
# MOMENTUM LEADERS
# ----------------------------------------------------

st.subheader("Top Momentum Stocks")

leaders = df.sort_values("Momentum",ascending=False).head(10)

fig3 = px.bar(
    leaders,
    x="Symbol",
    y="Momentum",
    color="Momentum"
)

st.plotly_chart(fig3,use_container_width=True)

# ----------------------------------------------------
# FULL STOCK SCREENER
# ----------------------------------------------------

st.subheader("Stock Screener")

st.dataframe(
    filtered.sort_values("Momentum",ascending=False),
    use_container_width=True
)

st.caption("Last Updated : "+str(datetime.now()))