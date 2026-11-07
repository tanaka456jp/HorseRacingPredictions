# PC2 offline acquisition dashboard for operator-permitted official NAR months.
# Reads ONLY filenames and filesystem metadata. Does not open archive contents,
# download, access provider URLs, train or publish. Never log paths or filenames.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
try {
    if ($env:COMPUTERNAME -cne 'DESKTOP-MVV1FD4') {
        throw 'NAR_DASHBOARD_WRONG_MACHINE'
    }
    if ($env:GITHUB_ACTIONS -eq 'true' -and (
        $env:GITHUB_REPOSITORY -cne 'tanaka456jp/HorseRacingPredictions' -or
        $env:GITHUB_REF_NAME -cne 'feature/weekly-odds-free-note-20261021'
    )) {
        throw 'NAR_DASHBOARD_UNEXPECTED_BRANCH'
    }
    $landing = 'D:\Development\HorseRacingPredictions\nar-personal'
    $review = 'D:\Development\HorseRacingPredictions-PrivateReview'
    $report = Join-Path $review 'nar-training-72-month-manual-acquisition.html'
    # Reject reparse points in the chain rather than inspecting a different
    # underlying data source through a junction or network share.
    foreach ($path in @('D:\Development', 'D:\Development\HorseRacingPredictions', $landing)) {
        if (-not (Test-Path -LiteralPath $path -PathType Container)) {
            throw 'NAR_DASHBOARD_EXPECTED_PRIVATE_D_FOLDERS_MISSING'
        }
        $item = Get-Item -LiteralPath $path -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'NAR_DASHBOARD_REPARSE_PATH_FORBIDDEN'
        }
    }
    $files = @(Get-ChildItem -LiteralPath $landing -Force -ErrorAction Stop)
    if ($files.Count -gt 1000) {
        throw 'NAR_DASHBOARD_TOO_MANY_SOURCE_ENTRIES'
    }

    $byMonth = @{}
    $unexpectedZipCount = 0
    foreach ($item in $files) {
        # No recursion, archive opening, CSV access or exact filename logging.
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'NAR_DASHBOARD_SOURCE_REPARSE_FORBIDDEN'
        }
        if ($item.PSIsContainer) {
            throw 'NAR_DASHBOARD_UNEXPECTED_SUBDIRECTORY'
        }
        if ($item.Extension -ine '.zip') { continue }
        if ($item.Name -cnotmatch '^(?<year>201[7-9]|202[0-2])(?<month>0[1-9]|1[0-2])_[0-9]{8,13}_race\.zip$') {
            $unexpectedZipCount++
            continue
        }
        $monthId = $Matches['year'] + $Matches['month']
        if (-not $byMonth.ContainsKey($monthId)) { $byMonth[$monthId] = @() }
        $byMonth[$monthId] += $item.Length
    }

    if (Test-Path -LiteralPath $review) {
        $existing = Get-Item -LiteralPath $review -Force
        if (-not $existing.PSIsContainer -or
            (($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw 'NAR_DASHBOARD_UNSAFE_REPORT_DESTINATION'
        }
    }
    $dir = [IO.Directory]::CreateDirectory($review)
    $acl = [Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    $ids = @(
        [Security.Principal.WindowsIdentity]::GetCurrent().User,
        [Security.Principal.SecurityIdentifier]::new('S-1-5-18'),
        [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
    )
    foreach ($sid in $ids) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $sid, [Security.AccessControl.FileSystemRights]::FullControl,
            ([Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
             [Security.AccessControl.InheritanceFlags]::ObjectInherit),
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow
        ))
    }
    $dir.SetAccessControl($acl)

    $rows = [Collections.Generic.List[string]]::new()
    $present = 0
    $missing = 0
    $duplicates = 0
    $oversized = 0
    foreach ($year in 2017..2022) {
        foreach ($month in 1..12) {
            # The month query is explicit; a year-only URL may default to
            # an unrelated month. &amp; keeps the link valid in HTML.
            $url = "https://www.keiba.go.jp/KeibaWeb/MonthlyConveneInfo/MonthlyConveneInfoTop?k_month=$month&amp;k_year=$year"
            $monthId = '{0}{1:D2}' -f $year, $month
            $sizes = if ($byMonth.ContainsKey($monthId)) { @($byMonth[$monthId]) } else { @() }
            if ($sizes.Count -eq 0) {
                $status = '未取得（名前のみ確認）'
                $class = 'missing'
                $missing++
            } elseif ($sizes.Count -gt 1) {
                $status = '同一月候補が重複：確認必要'
                $class = 'warning'
                $duplicates++
            } elseif ($sizes[0] -le 0 -or $sizes[0] -gt 400000000) {
                $status = '候補ファイルサイズ要確認'
                $class = 'warning'
                $oversized++
            } else {
                $status = 'ZIP名候補あり（中身・権利は未確認）'
                $class = 'present'
                $present++
            }
            $rows.Add(('<tr><td>{0}年{1:D2}月</td><td class="{2}">{3}</td><td><a href="{4}" target="_blank" rel="noopener noreferrer">NAR公式の該当月を開く</a></td></tr>' -f $year,$month,$class,$status,$url))
        }
    }
    $timestamp = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    $body = @'
<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><title>NAR研究 2017〜2022年 月次資料確認</title>
<style>
body{font-family:"Yu Gothic","Meiryo",sans-serif;max-width:940px;margin:28px auto;padding:0 22px;color:#17212b;line-height:1.65}
h1{font-size:1.55rem}h2{font-size:1.15rem}
table{border-collapse:collapse;width:100%;margin-top:20px}
th,td{border-bottom:1px solid #ddd;padding:9px 12px;text-align:left}
th{background:#f3f4f6}.missing{color:#8b2d20}.warning{color:#915400}.present{color:#176442}
small{color:#555}a{color:#1357a4}
</style></head><body>
<h1>NAR公式 月次レース情報 — 研究資料取得チェック</h1>
<p>対象：2017〜2021年を学習、2022年をモデル選定。2023〜2024年の独立検証と2025年以降の保護領域は、この画面で探したり開いたりしません。</p>
<p><strong>これはPC②内のZIPファイル名だけを確認した結果です。</strong>
ZIPの中身・利用権限・来歴・事前時刻・モデル学習適格性を証明するものではありません。
取得は権利の許諾範囲を確認した担当者がNAR公式サイトのボタンから手動で行ってください。
自動ダウンロード、スクレイピング、外部への転送は実装していません。</p>
<h2>取得後に行うこと</h2>
<p>担当者が許諾されたオリジナルZIPをPC②の専用保管場所に保存し、
別の既存診断ツールで構造・月度・欠損を確認します。保存後にこのチェックを再実行すると一覧が更新されます。
過去の月次結果は当時の予測時点の出走情報を証明しないため、収益性検証には別途時刻証跡が必要です。</p>
<table><thead><tr><th>対象月</th><th>PC②保管名の状況</th><th>手動取得用公式ページ</th></tr></thead><tbody>
'@
    $body += ($rows -join [Environment]::NewLine)
    $body += @'
</tbody></table>
<p><small>調査は既存の専用Dフォルダ直下のみ。ZIP中身は未読込。個別の例外データは別途照合が必要です。</small></p>
</body></html>
'@
    [IO.File]::WriteAllText($report, $body, [Text.UTF8Encoding]::new($false))
    # Reapply parent ACL to the output file's inherited protection.
    $fileAcl = [Security.AccessControl.FileSecurity]::new()
    $fileAcl.SetAccessRuleProtection($true, $false)
    foreach ($sid in $ids) {
        $fileAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $sid, [Security.AccessControl.FileSystemRights]::FullControl,
            [Security.AccessControl.AccessControlType]::Allow
        ))
    }
    ([IO.FileInfo]::new($report)).SetAccessControl($fileAcl)
    ([ordered]@{
        schema = 'NAR.PC2.OfficialMonthlyOperatorDashboard.v1'
        status = 'PRIVATE_MANUAL_ACQUISITION_DASHBOARD_READY'
        expectedMonths = 72
        candidateFilenameMonths = $present
        missingFilenameMonths = $missing
        duplicateFilenameMonths = $duplicates
        invalidSizeFilenameMonths = $oversized
        unexpectedZipFilenameCount = $unexpectedZipCount
        reportFolder = 'D:\Development\HorseRacingPredictions-PrivateReview'
        reportFileName = 'nar-training-72-month-manual-acquisition.html'
        createdUtc = $timestamp
        providerRequests = 0
        filesDownloaded = 0
        sourceContentsRead = $false
        sourceDataUploaded = $false
        originAndRightsIndependentlyVerified = $false
        protectedHoldoutOpened = $false
        modelTrainingRun = $false
        positiveEvDemonstrated = $false
    } | ConvertTo-Json -Depth 4)
} catch {
    # Do not print exception: it could include an unapproved private filename.
    Write-Host 'NAR_PC2_OPERATOR_DASHBOARD_FAILED_SAFELY'
    exit 2
}
