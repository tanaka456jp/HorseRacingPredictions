# PC② JRA-VAN `JVOpen -301` 解消手順とRunner復旧（2026-10-24）

この手順書は個人利用のJRA-VAN無料範囲・GitHub Draft PR内の研究データ診断に限定する。
**利用キーをGitHub、チャット、ログ、画像に表示・保存しない。**
有料契約、利用キー自動再発行、JRA-VANキャッシュ削除、JV-Linkの再インストール、
32/64bit版のアンインストール、2025–2026年の保護データ取得を自動実行しない。

## 直接確認した過去ログ

- 成功した実機診断 [Run 38318741836](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/38318741836) の `jravan-sanitized-environment-probe` を2026-10-24に検査。
- 実PC名は **DESKTOP-MVV1FD4**（PC②）。Horse runner表示名は `Office-PC-01-HorseRacingPredictions`。表示名の「PC-01」で実マシンを推定しない。
- Runner実フォルダ（GitHub実機ログ確認）：
  `C:\actions-runner-HorseRacingPredictions\actions-runner`
- 64bit Python 3.14.2。JV-Linkは**32bitと64bitのCOM登録が双方存在**。両方の利用キーが同じか、実際のサービス認証が有効かは未知。
- 公式キャッシュ `C:\ProgramData\JRA-VAN\Data Lab\data` 約2.22GiB。既存Dドライブ保存アーカイブ約5.32GiB。**いずれも変更不要・削除禁止**。
- RACE収集の過去判定 [Run 38390982174](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/38390982174)：`records_written=0`, `JVOpen -301`, RACEの合法な保存データは存在しない。BLDN約8万件はRACEデータではない。

## まずPC②のRunnerをオンラインにする（管理者権限不要で状態確認）

PC②のPowerShell（**PC①ではない**）で実行：

~~~powershell
$runner = 'C:\actions-runner-HorseRacingPredictions\actions-runner'
$listener = @(Get-CimInstance Win32_Process -Filter "Name='Runner.Listener.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.ExecutablePath -like "$runner*" })
$services = @(Get-CimInstance Win32_Service |
  Where-Object { $_.PathName -like '*actions-runner-HorseRacingPredictions*' } |
  Select-Object Name, State, StartMode)
[pscustomobject]@{
    RunnerPathExists = (Test-Path -LiteralPath (Join-Path $runner 'run.cmd') -PathType Leaf)
    HorseListenerCount = $listener.Count
    HorseServices = $services
}
~~~

- Listenerがすでに動作していれば二重起動しない。GitHubでジョブが配車されない場合はサービス・ラベル・利用可能権限を確認する。
- リスナーが**0**でサービスが稼働中なら、まずサービスログ等で診断する。二重起動しない。
- リスナーが**0**かつHorse専用サービスが存在しない場合に限り、ユーザーがローカルの対話セッションで以下を実行できる：

~~~powershell
Set-Location 'C:\actions-runner-HorseRacingPredictions\actions-runner'
.\run.cmd
~~~

- サービスが登録され停止中なら、サービス設定を確認のうえ本人が管理者PowerShellからサービスを起動する。安全チェックや承認画面を自動クリックしない。
- 待機中の検証ワークフロー [Sunday local readiness](https://github.com/tanaka456jp/HorseRacingPredictions/actions/workflows/sunday-20261025-readiness-self-hosted.yml) が起動すると、生データ・利用キーなしのJSON診断をArtifactsへ出力する。

## JRA-VAN公式の `-301` を切り分ける（人間による公式画面のみ）

JRA-VAN公式の[エラー -301/-303](https://support.jra-van.jp/jravan/detail?hot_list=true&id=32&site=SVKNEGBV)は、有効な利用キー未設定または複数PCで同じ利用キー使用による認証失敗を説明している。

また[2026年8月の開発者向けJV-Link v5.0情報](https://developer.jra-van.jp/t/topic/959)は、**32bit/64bit版で同一利用キーを使用しても -301になる**と明記している。

1. PC②上で公式の「JV-Link設定」を開き、32bit・64bit双方の利用キーが**同一か・異なるか・未設定か**を画面上で確認（キーの文字列は撮影・書き出し・送信しない）。
2. JRA-VAN公式の各種手続き画面で**無料利用資格が現在も有効か**を人間が確認する。無効なら購入・更新せず停止。
3. 同一キー／無効キーの場合、公式サポート案内に従う。再発行・再インストールはデータバックアップと契約状態を確認したうえで、本人が実施するまで着手しない。
4. 利用資格が有効で適法な研究取得権限がある場合にのみ、PC②の公式**64bit版**データラボ検証ツールで事前に限定された**2017～2024年だけ**のRACEセットアップ可否を調べる。境界条件がツールで保証できない場合は実行しない。
5. 公式ツール成功／独自Python失敗なら、Python 64bit環境と使用するJV-LinkのCOM登録先、`JVInit`のアプリSIDの違いを確認する。公式ツールも失敗なら、プロジェクトのPython/CSVロジックではなく認証環境の問題を先に解決する。

## 次段階に進む条件

- 【Runner】ジョブがWindows PC②で開始され、ローカルJSONの最新診断が確認される。
- 【RACE】公式検証で `-301` の原因が判明し、無課金・指定期間内・適法な研究利用だけが可能だと確認できる。
- 【予測】別途、2026-10-25時点の全36レース出走馬・直近履歴・厳密にオッズ非依存で学習した**本物の**モデルが必要。2017～2024年のRACEが回復してもこれらは自動的にはそろわない。
- 【公開】本人の無料noteマガジン掲載と、元データを再配布しない独立した公開利用権限を確認する。検証できなければ投稿しない。

## 2026-10-26 runnerで実証したPC② Python 64bit復旧（正式な引継ぎ）

**旧来の `JVOpen -301` がすべて解消されたと断定しないこと。** 2026-10-25の二種類の実機診断結果を厳密に区別する。

1. [32/64初期化ジョブ #40204873519](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/40204873519)：32bit版・64bit版ともCOM生成成功、`JVInit("UNKNOWN")=0`。**JVOpenは未実行**。
2. [32/64今週のRACE認証ジョブ #40204953445](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/40204953445)：**64bit** `JVOpen("RACE", "00000000000000", option=2)=0`、`JVClose`成功。**32bit**は45秒タイムアウト、返却コードは得られず、`-301`と同一視できない。
3. [Agent／Python環境ジョブ #40241907419](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/40241907419)：JV-Link関連プロセス2件・実行中の関連サービス2件・停止中0件。一般の`py -3`は**64bit**だが、`pywin32`未導入。これがPythonからCOMを初期化できなかった具体的な障害。
4. [専用Dドライブ復旧・認証ジョブ #40242482654](https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/40242482654)：PC②のみを対象に、システムPythonを変更せず、**新規D仮想環境** `D:\HorseRacingPredictions\runtime\pc2-jvlink64-py314-312` を作成。公式PyPIの**無料** `pywin32==312` CPython3.14 x64バイナリを**SHA256固定**で導入。結果 `dependencyVerified=true`・`pythonBits=64`、研究プログラムが使う**実Python JvLinkClient**で `JVInit=0`、`JVOpen(RACE,option=2)=0`、`JVClose`成功。

すべて**既存のself-hosted runnerを利用しGitHub Draft PR内のみ**を変更した。Pythonシステム全体の置換・32/64bit JV-Linkアンインストール・利用キー閲覧／再発行・エージェント停止／再設定・有料契約は行っていない。JVOpen自身の標準キャッシュ処理は発生し得るが、JVGet/JVRead・2025–2026保護holdoutのレコード取得・馬名アップロード・note投稿は実施していない。

### これから守る起動経路

- **PC②でのHorse研究用JV-Linkは64bit専用**。32bit版は正常初期化まで確認されているが認証応答待ちの原因は**未解決**。無理に32bit版を再試行せず、既存Agentを強制停止しない。
- 64bit研究時は、systemの`py -3`と混同せず、`D:\HorseRacingPredictions\runtime\pc2-jvlink64-py314-312\Scripts\python.exe`を明示する。既存の`run_jravan_trial.ps1`等は一般Pythonへ依存パッケージを導入し得るため、新環境に適用する前に研究依存関係を確認する。
- 既に導入済みの`pywin32`を**毎回インストールし直さない**。更新する場合も公式ハッシュ照合した無料版を選び、既存アーカイブや一般Pythonに干渉しない。専用環境の所有マーカーが存在しない場合は既存フォルダを上書きしない。
- **今週分RACE `option=2`の認証成功≠過去2017～2024年 `option=3/4` セットアップ成功**。RACE履歴はDの承認済みCSVとして未確認。過去セットアップを無断で開始しない。将来実施する場合、取得契約・利用可能期間・利用目的・キャッシュ容量と転用許可の確認が必要。
- 予想公開については[JRA-VAN公式](https://jra-van.jp/info/post_guide.html)に従い、生JV-Linkデータの投稿を禁止。独立した適法なデータソースと予想文章の公開許諾、研究用モデルの正確性が別に必要。AIモデルの実馬期待値や11月1日の記事投稿は**まだ実証・実行されていない**。

