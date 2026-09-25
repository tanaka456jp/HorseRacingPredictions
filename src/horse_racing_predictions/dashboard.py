import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="HorseRacingPredictions", layout="wide")
st.title("HorseRacingPredictions")
st.caption("EV中心・無料データ優先・Paper Trading")

db_path = st.text_input("SQLite DB", "demo_racing.sqlite3")
path = Path(db_path)

if not path.exists():
    st.info("DBがまだありません。まず python -m horse_racing_predictions.demo を実行してください。")
    st.stop()

conn = sqlite3.connect(path)
bets = pd.read_sql_query("SELECT * FROM bets ORDER BY id", conn)
pred = pd.read_sql_query("SELECT * FROM predictions ORDER BY id", conn)

stake = int(bets.loc[bets["stake_yen"] > 0, "stake_yen"].sum()) if not bets.empty else 0
payout = int(bets["payout_yen"].fillna(0).sum()) if not bets.empty else 0
profit = payout - stake
roi = ((payout / stake) - 1) if stake else 0.0

c1,c2,c3,c4 = st.columns(4)
c1.metric("購入額", f"¥{stake:,}")
c2.metric("払戻", f"¥{payout:,}")
c3.metric("損益", f"¥{profit:,}")
c4.metric("ROI", f"{roi:.1%}")

st.subheader("予測")
st.dataframe(pred, use_container_width=True)

st.subheader("Paper Bets")
st.dataframe(bets, use_container_width=True)
conn.close()
