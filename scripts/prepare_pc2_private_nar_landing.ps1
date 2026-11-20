# Prepare one strictly private PC2 D landing for operator-approved NAR ZIP files.
# Never downloads, reads ZIP content, crawls drives, changes existing files,
# touches JRA-VAN, 2023+ holdouts, or shares credentials/source rows.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if ($env:COMPUTERNAME -cne 'DESKTOP-MVV1FD4') {
    throw 'NAR_LANDING_PC2_MACHINE_REQUIRED'
}
if ($env:RUNNER_NAME -notlike '*HorseRacingPredictions*') {
    throw 'NAR_LANDING_HORSERACING_RUNNER_REQUIRED'
}
$parent='D:\Development\HorseRacingPredictions'
$target=Join-Path $parent 'nar-personal'
function Require-PhysicalFolder([string]$path) {
    $i=Get-Item -LiteralPath $path -Force -ErrorAction Stop
    if (-not $i.PSIsContainer -or
        (($i.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
        throw 'NAR_LANDING_REPARSE_OR_NON_DIRECTORY_BLOCKED'
    }
}
Require-PhysicalFolder $parent
if(-not (Test-Path -LiteralPath (Join-Path $parent '.git') -PathType Container)){
    throw 'NAR_LANDING_PARENT_REPO_MISSING'
}
$git=Get-Item -LiteralPath (Join-Path $parent '.git') -Force -ErrorAction Stop
if($git.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'NAR_LANDING_PARENT_REPO_LINK_BLOCKED'
}
$created=$false
if(Test-Path -LiteralPath $target) {
    Require-PhysicalFolder $target
} else {
    $new=New-Item -ItemType Directory -Path $target -ErrorAction Stop
    $created=$true
    Require-PhysicalFolder $target
    # Prevent inherited Everyone/Users access and permit runner's account,
    # SYSTEM and local Administrators only.
    $acl=Get-Acl -LiteralPath $target -ErrorAction Stop
    $acl.SetAccessRuleProtection($true,$false)
    $inherit=[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit'
    $prop=[Security.AccessControl.PropagationFlags]::None
    $allow=[Security.AccessControl.AccessControlType]::Allow
    $full=[Security.AccessControl.FileSystemRights]::FullControl
    $ids=@(
        [Security.Principal.WindowsIdentity]::GetCurrent().User,
        (New-Object System.Security.Principal.SecurityIdentifier 'S-1-5-18'),
        (New-Object System.Security.Principal.SecurityIdentifier 'S-1-5-32-544')
    )
    foreach($identity in $ids) {
        $rule=New-Object System.Security.AccessControl.FileSystemAccessRule(
            $identity,$full,$inherit,$prop,$allow
        )
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $target -AclObject $acl -ErrorAction Stop
}
$after=Get-Acl -LiteralPath $target -ErrorAction Stop
if($created -and -not $after.AreAccessRulesProtected) {
    throw 'NAR_LANDING_PRIVATE_ACL_NOT_APPLIED'
}
# ONLY immediate metadata. Never inspect contents or print filenames.
$items=@(Get-ChildItem -LiteralPath $target -Force -ErrorAction Stop)
$unexpected=@($items | Where-Object { $_.PSIsContainer -or
   (($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) })
if($unexpected.Count -gt 0) {
    throw 'NAR_LANDING_NESTED_OR_REPARSE_ITEM_REQUIRES_REVIEW'
}
$zip=@($items | Where-Object {
    $_.Name -cmatch '^(?:19|20)[0-9]{4}_[0-9]{8,13}_race\.zip$'
})
$present=@{}
foreach($z in $zip) {
    $m=$z.Name.Substring(0,6)
    if($m -ge '201701' -and $m -le '202212') { $present[$m]=$true }
}
[pscustomobject]@{
    Schema='NAR.PC2.PrivateLocalLanding.v1'
    Status='LOCAL_LANDING_READY_OPERATOR_DATA_NOT_IMPORTED'
    MachineVerified=$true
    FolderCreatedNow=$created
    PrivacyACLAppliedOnCreation=$created
    MatchingTrainingMonthNames=$present.Count
    RequiredTrainingMonths=72
    SourceContentsRead=$false
    SourcesDownloaded=$false
    ExistingFileContentModified=$false
    GitRepositoryModified=$false
    ProviderContacted=$false
    ModelFitExecuted=$false
    PositiveExpectedValueDemonstrated=$false
    PublicationAuthorized=$false
} | ConvertTo-Json -Depth 3
