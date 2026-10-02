$ErrorActionPreference = 'Stop'
$teamRoot = Split-Path -Parent $PSScriptRoot
$teamStage = Join-Path $teamRoot 'exports\reports\team-midterm-template-20261002'
$teamDocx = Join-Path $teamStage 'team-report-template.docx'
$teamHwpPath = Join-Path $teamStage '(버스태워줘)2026-2학기_중간팀보고서_기본틀.hwp'
$teamPdf = Join-Path $teamStage 'team-report-template-hancom.pdf'
$teamText = Join-Path $teamStage 'native-extracted.txt'
$teamLog = Join-Path $teamStage 'native-conversion.log'
$teamHwpObject = $null
function ReportStage([string]$message) {
    $line = (Get-Date -Format 'o') + ' ' + $message
    [System.IO.File]::AppendAllText($teamLog, $line + [Environment]::NewLine, [System.Text.Encoding]::UTF8)
    Write-Output $line
}
try {
    ReportStage 'Creating independent Hancom automation instance'
    $teamHwpObject = New-Object -ComObject HWPFrame.HwpObject
    $teamHwpObject.XHwpWindows.Item(0).Visible = $true
    ReportStage ('Hancom version: ' + $teamHwpObject.Version)
    ReportStage 'Opening authored DOCX'
    if (-not $teamHwpObject.Open($teamDocx, 'OOXML', '')) { throw 'DOCX import failed' }
    ReportStage 'Saving native HWP'
    if (-not $teamHwpObject.SaveAs($teamHwpPath, 'HWP', '')) { throw 'HWP save failed' }
    ReportStage 'Extracting imported text'
    [System.IO.File]::WriteAllText($teamText, $teamHwpObject.GetTextFile('TEXT', ''), [System.Text.Encoding]::UTF8)
    ReportStage 'Exporting PDF for visual verification'
    if (-not $teamHwpObject.SaveAs($teamPdf, 'PDF', '')) { throw 'PDF export failed' }
    ReportStage 'Conversion complete'
} finally {
    if ($null -ne $teamHwpObject) {
        $teamHwpObject.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($teamHwpObject)
    }
}
