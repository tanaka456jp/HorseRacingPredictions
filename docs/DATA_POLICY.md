# Data Policy

## Free-first

有料データ・有料予想・有料APIを初期システムへ組み込まない。

## Provenance

各Providerで source / URL / 取得時刻 / 利用条件 / 再配布可否 / 営利利用可否 / schema version を記録する。

## No future leakage

学習時点より後に確定する情報を特徴量へ混入させない。特に確定オッズ、レース後人気、着順派生値、未来の馬場情報を監査する。

## Paid data gate

有料情報は以下を全て満たした場合だけ検討する。

1. 無料構成でPaper Tradingから少額実運用まで安定
2. 有料情報あり/なしを過去データでA/B可能
3. OOSで予測品質が改善
4. 控除後ROIと利益が改善
5. 追加費用を十分回収
6. 複数期間・複数競馬場で再現
