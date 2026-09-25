# Roadmap

## Phase 1 — Research Core
- [x] EV engine
- [x] Fractional Kelly
- [x] PaperBroker
- [x] SQLite ledger
- [x] Dashboard baseline
- [x] Champion/Challenger gate
- [x] Free CSV adapter baseline
- [ ] Real historical dataset ingestion validation
- [ ] Baseline probability model
- [ ] Walk-forward backtest

## Phase 2 — Feature Store
過去成績、コース、距離、芝/ダート、馬体重差、騎手/調教師rolling stats、脚質、pace pressure、血統、天候、馬場。

## Phase 3 — Probability Models
LightGBM / CatBoost / ranking / calibration / ensemble。

## Phase 4 — Ticket Probability
Plackett-LuceまたはMonte Carloで単複、馬連、馬単、ワイド、三連複、三連単を評価。

## Phase 5 — Daily Selection
許諾済みProvider、オッズスナップショット、EV decay、race skip、daily risk budget。

## Phase 6 — Learning Loop
post-race attribution、calibration drift、feature drift、challenger retraining、OOS promotion。

## Phase 7 — Real Execution
Paper基準通過後のみ。tiny capital、kill switch、max daily loss、order reconciliation、manual confirmation first、full automation last。
