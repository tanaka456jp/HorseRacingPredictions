# JRA 日曜予想の継続的な安全診断 — 2026-10-25以降

## 完了したものと、していないもの

2026-10-25の36Rをレース後に「事前予想」として生成・公開することはできない。
過去日専用の `sunday_auto_post_readiness` は **2026-10-25 08:00 JST以降**
`HISTORIC_PRE_RACE_CUTOFF_EXPIRED` で即停止する。レース後の出馬表や結果で
過去の時点の予測を作り直さず、モデルやPrivateデータにもアクセスしない。

次の日曜 2026-11-01 の[JRA開催予定](https://jra.jp/keiba/calendar2026/2026/11/1101.html)
は **東京12R + 京都12R = 合計24R**。36R固定前提は適用できない。
公式日程は事前予定であり、確定出馬表・発走時刻・取消は再確認が必要。

## 実装した予測「前」の診断とフォーマット

- `future_sunday_readiness.diagnose_future_sunday_bundle` は日曜開催日を受け取り、
  **12/24/36件、開催場ごと1〜12R、重複なし** の既存ローカル・マニフェストだけを確認する。
  マニフェストの自己申告はJRAによる独立検証ではない。
- 有効な診断時間は金曜0:00 JSTから対象日曜 **07:59:59 JST** まで。
  08:00以降はモデル・履歴ファイルを開かず遮断する。
  日曜のすべての発走時刻を独立に把握しない限り公開ゲートの緩和はしない。
- ローカル入力（利用と保存が合法か独立に確認したもののみ）：
  `model/model.cbm`、`model/manifest.json`、
  `race_history.csv`、`sunday_entries.csv`、
  `race_manifest.json`。
- `race_manifest.json` の一般形式：
  `{"raceDate":"2026-11-01","sourceKind":"jra-official-pre-race-card","expectedRaceIds":["JRA-20261101-TOKYO-01", "..."]}`。
  実運用では各開催場の **全12R** を正規IDで列挙する必要がある。
  文字列 `sourceKind` の自己申告だけでは公式取得・許可を証明できない。
- PC② Dドライブに置く場合の **未存在の予定配置先**：
  `D:\HorseRacingPredictions\approved-sunday-20261101`。
  このフォルダへのコピーや自動ダウンロードはしていない。
- 研究上の本物の推論は既存 `private_sunday_ai_preview` を呼び出す場合のみ
  `modelComputed:true` と匿名 SHA256 を出す。人工スコア、Champion v7、
  オッズ・人気、2025-2026最終holdoutでの再学習は不可。
  独立した凍結穴馬モデルの証明は別途必須。
- `scripts/inspect_future_sunday_local.py` は **端末の現在時刻のみ** 利用。
  `--as-of` などの時刻偽装パラメータはない。
  Windows runner ワークフロー `future-sunday-readiness-pc2.yml` はPC②判定後
  Dの候補フォルダに対して読み取り専用実行し、秘匿データでなく状態JSONのみ保存。
  workflowがSUCCESSでも `status: BLOCKED` は**公開可を意味しない**。

手動の読み取り専用実行例：

```powershell
$env:PYTHONPATH = "src"
py -3 scripts/inspect_future_sunday_local.py `
  --race-date 2026-11-01 `
  --bundle-dir "D:\HorseRacingPredictions\approved-sunday-20261101"
```

## JRA-VAN認証 -301 と合法なデータ調達

- [JRA-VANの公式エラーコード](https://developer.jra-van.jp/t/topic/822):
  -301 は不正な利用キー、あるいは同じ利用キーの複数環境使用で起こり得る。
  -302は期限切れ、-303は未設定。ログから原因を勝手に一意に決めない。
- [JV-Link 5.0告知](https://developer.jra-van.jp/t/topic/959):
  **32bit/64bit双方の同一利用キー利用は-301**。
- 無料試用は[公式説明](https://support.jra-van.jp/jravan/detail?hot_list=true&id=431&site=SVKNEGBV)
  によると原則インストール日から1か月（1回限り）。
  [有料継続料金](https://jra-van.jp/dlb/)は月額2,090円。
  無償・現行契約条件が確認できない場合は購入・キー再発行を実行しない。
- 利用者はPC②の**公式JV-Link設定画面**で32/64bitのキーが
  「未設定/同じ/別」なのかと無料資格の有効性だけを確認する。
  キー文字列は画面キャプチャ・チャット・GitHub・Actionsに出さない。
  認証状態が不明なら公式サポートで適法な是正を確認し、
  他PCのキーと兼用しない。既存DアーカイブとCキャッシュは削除しない。
- [JRA-VAN投稿ガイドライン](https://jra-van.jp/info/post_guide.html)
  は **JV-Linkから取得したデータの投稿不可** としている。
  JRA公開出馬表も二次利用許諾を一般的に保証するものではない。
  データ利用権限と予想本文の公開権限は独立に記録する。

## 実公開は未許可

プライベートのモデル実行に成功しても、予測品質・期待値・校正された
正確な1〜3着着順確率・独立穴馬モデル・レース出走馬独立照合・出典・
ソースの公開許諾・署名証跡・noteログイン実行は別々に必要。

Business Platform の通常金曜preflightとマガジン
`m18cae5764be3` の `active:false` は変更せず、署名や権限が揃うまで
**note投稿、main統合、runner設定変更、利用キー読取・再発行、課金しない**。

## 非市場型 CatBoost 勝率モデル＋独立穴馬モデルの実学習（新規）

- `strict_dual_catboost_candidate.fit_strict_dual_catboost_candidate` は無料OSS CatBoostを**2個独立にfit**する。勝率用の `is_winner` と、穴馬用の学習期間内 `finish_position<=3` は別目標。
- **2024-12-31以前のみ** 学習・事後に区切った独立評価。評価期間の正解着順列をモデル入力から完全に取り除く。勝率モデルの上位3頭を除き、独立穴馬モデルの相対スコア最高馬を選ぶ。従来の勝率4位を比較対象にする。
- 本物のCatBoostソフトをインストールする専用 **無料オープンソースCI** は架空馬・架空レースだけで `fit -> score -> 2つのCBM保存 -> SHA256照合` を実行する。これは実馬の性能や、+EVを証明しない。
- `scripts/train_strict_dual_pre2025_local.py` は明示された**合法取得済み・2024年以前だけ**のCSVを開き、実モデル候補を新規のローカル絶対パスに凍結する。未存在CSV、2025–2026年混入、期間重複、既存ディレクトリ上書きは拒否。
- 出力は `win.cbm`、`outsider.cbm`、`candidate_manifest.json`。
  各モデルのSHA256、実測の日時分離指標、特徴量を記録する。権利・元データの市場独立性・モデル署名・note許可は**常にfalse**。
- 以下は**パスの例示のみ**で、CSVやモデルがPC②に実在することを確認したものではない。PC②では承認済みCSVと作成済みの親フォルダを用意してから実行する。既存JRA-VANアーカイブや保護済みholdoutへは触れない。

```powershell
$env:PYTHONPATH = "src"
py -3 scripts/train_strict_dual_pre2025_local.py `
  --approved-pre2025-csv "D:\HorseRacingPredictions\approved-history\pre2025.csv" `
  --source-ref "operator-reviewed-pre2025-source" `
  --output-dir "D:\HorseRacingPredictions\research-candidates\dual-20261025" `
  --train-start 2017-01-01 --train-end 2024-12-31 `
  --fit-through 2023-12-31 `
  --validation-from 2024-01-01 --validation-through 2024-12-31 `
  --iterations 100
```

**重要：この研究用CBMはそのまま公開用モデルではない。** 学習原資そのものの適法性・サンプル抽出の完全なオッズ非依存、実馬に対する期間外検証、確率校正、2026年出馬表・近走情報、別個の凍結穴馬モデルの外部証明、JRA-VANの認証、noteへの公開許諾・署名済み検証を経る必要がある。
