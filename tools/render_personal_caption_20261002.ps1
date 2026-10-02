param([string]$InputName = 'personal-caption-edited.hwpx', [string]$OutputStem = 'edited')
$ErrorActionPreference = 'Stop'
$reportStage = Join-Path (Split-Path -Parent $PSScriptRoot) 'exports\reports\personal-caption-20261002'
$hwp = $null
try {
    $hwp = New-Object -ComObject HWPFrame.HwpObject
    $hwp.XHwpWindows.Item(0).Visible = $true
    Write-Output 'Independent Hancom instance created'
    if (-not $hwp.Open((Join-Path $reportStage $InputName), 'HWPX', '')) { throw 'Open failed' }
    Write-Output 'Report opened'
    if (-not $hwp.SaveAs((Join-Path $reportStage ($OutputStem + '.pdf')), 'PDF', '')) { throw 'PDF export failed' }
    Write-Output 'PDF saved'
} finally {
    if ($null -ne $hwp) { $hwp.Quit() }
}
