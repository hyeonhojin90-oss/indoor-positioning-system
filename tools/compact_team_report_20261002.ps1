$ErrorActionPreference = 'Stop'
$stage = Join-Path (Split-Path -Parent $PSScriptRoot) 'exports\reports\team-midterm-template-20261002'
$source = Get-ChildItem -LiteralPath $stage -Filter '*.hwp' | Select-Object -First 1
$hwp = $null
try {
    $hwp = New-Object -ComObject HWPFrame.HwpObject
    $hwp.XHwpWindows.Item(0).Visible = $true
    Write-Output 'Independent Hancom instance created'
    if (-not $hwp.Open($source.FullName, 'HWP', '')) { throw 'Open failed' }
    Write-Output 'Native document opened'
    $hwp.HAction.Run('SelectAll') | Out-Null
    $hwp.HAction.GetDefault('ParagraphShape', $hwp.HParameterSet.HParaShape.HSet) | Out-Null
    $hwp.HParameterSet.HParaShape.PrevSpacing = 0
    $hwp.HParameterSet.HParaShape.NextSpacing = 0
    $hwp.HParameterSet.HParaShape.LineSpacingType = 0
    $hwp.HParameterSet.HParaShape.LineSpacing = 120
    $hwp.HAction.Execute('ParagraphShape', $hwp.HParameterSet.HParaShape.HSet) | Out-Null
    if (-not $hwp.SaveAs((Join-Path $stage 'team-report-compact.hwp'), 'HWP', '')) { throw 'Save failed' }
    if (-not $hwp.SaveAs((Join-Path $stage 'team-report-compact.pdf'), 'PDF', '')) { throw 'PDF failed' }
    Write-Output 'Compact native document and PDF saved'
} finally {
    if ($null -ne $hwp) { $hwp.Quit() }
}
