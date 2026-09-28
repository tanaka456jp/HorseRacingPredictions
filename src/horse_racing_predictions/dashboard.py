import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from .residual_paper_evidence import (
    build_residual_v12_paper_evidence_report,
)


st.set_page_config(page_title="HorseRacingPredictions", layout="wide")
st.title("HorseRacingPredictions")
st.caption("EV中心・無料データ優先・Paper Trading")

db_path = st.text_input(
    "SQLite DB",
    "data/paper/paper_trading.sqlite3",
)
path = Path(db_path)

if not path.exists():
    st.info(
        "Paper Trading DBがまだありません。"
        "self-hosted forward workflow実行後に表示されます。"
    )
    st.stop()

evidence = build_residual_v12_paper_evidence_report(path)

st.subheader("Residual v12 Paper v1 Evidence Gate")
e1, e2, e3, e4 = st.columns(4)
e1.metric(
    "Prospective評価レース",
    (
        f"{evidence['prospective_evaluated_races']:,}"
        f" / {evidence['minimum_prospective_evaluated_races']:,}"
    ),
)
e2.metric(
    "決済済みPaper賭け",
    (
        f"{evidence['settled_paper_bets']:,}"
        f" / {evidence['minimum_settled_paper_bets']:,}"
    ),
)
e3.metric(
    "決済済みROI",
    (
        f"{float(evidence['roi']):.1%}"
        if evidence["roi"] is not None
        else "—"
    ),
)
e4.metric(
    "最大ドローダウン",
    f"¥{evidence['max_drawdown_yen']:,}",
)

st.progress(
    float(evidence["evaluated_race_progress"]),
    text=(
        "評価レース進捗 "
        f"{evidence['prospective_evaluated_races']:,}"
        f"/{evidence['minimum_prospective_evaluated_races']:,}"
    ),
)
st.progress(
    float(evidence["settled_bet_progress"]),
    text=(
        "決済済み賭け進捗 "
        f"{evidence['settled_paper_bets']:,}"
        f"/{evidence['minimum_settled_paper_bets']:,}"
    ),
)

if not evidence["sufficient_evidence"]:
    st.info(
        "Evidence Gate: insufficient_evidence。"
        "標本条件を満たすまではROIがプラスでも判定保留です。"
    )
elif evidence["observed_positive_roi"]:
    st.success(
        "Evidence Gate: review_ready。"
        "固定標本条件到達後のPaper ROIは現時点でプラスです。"
        "実賭けへの自動昇格は行いません。"
    )
else:
    st.warning(
        "Evidence Gate: review_ready。"
        "固定標本条件には到達しましたが、"
        "Paper ROIは現時点でプラスではありません。"
    )

st.caption(
    "固定条件: prospective評価500レース以上・"
    "決済済みPaper賭け200件以上。"
    "閾値は結果確認前に固定。Live executionは無効。"
)

r1, r2, r3, r4 = st.columns(4)
r1.metric("Residual選定賭け", f"{evidence['selected_bets']:,}")
r2.metric("勝 / 敗", f"{evidence['wins']:,} / {evidence['losses']:,}")
r3.metric("決済済み損益", f"¥{evidence['profit_yen']:,}")
r4.metric("未決済", f"{evidence['unsettled_bets']:,}")

conn = sqlite3.connect(path)
bets = pd.read_sql_query("SELECT * FROM bets ORDER BY id", conn)
pred = pd.read_sql_query("SELECT * FROM predictions ORDER BY id", conn)

selected = (
    bets.loc[bets["stake_yen"] > 0].copy()
    if not bets.empty
    else bets.copy()
)
settled = (
    selected.loc[selected["result"].notna()].copy()
    if not selected.empty
    else selected.copy()
)

committed_stake = (
    int(selected["stake_yen"].sum())
    if not selected.empty
    else 0
)
settled_stake = (
    int(settled["stake_yen"].sum())
    if not settled.empty
    else 0
)
settled_payout = (
    int(settled["payout_yen"].fillna(0).sum())
    if not settled.empty
    else 0
)
settled_profit = settled_payout - settled_stake
settled_roi = (
    settled_payout / settled_stake - 1.0
    if settled_stake
    else None
)
unsettled_count = (
    int(selected["result"].isna().sum())
    if not selected.empty
    else 0
)

st.subheader("全Paper Trading")
c1, c2, c3, c4 = st.columns(4)
c1.metric("累計購入額", f"¥{committed_stake:,}")
c2.metric("決済済み損益", f"¥{settled_profit:,}")
c3.metric(
    "決済済みROI",
    f"{settled_roi:.1%}" if settled_roi is not None else "—",
)
c4.metric("未決済", f"{unsettled_count:,}")

st.subheader("予測")
st.dataframe(pred, use_container_width=True)

st.subheader("Paper Bets")
st.dataframe(bets, use_container_width=True)
conn.close()
