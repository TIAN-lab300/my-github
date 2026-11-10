param([string]$Target = 'C:\Users\ASUS\Documents\ChatGPT\卓越工程实践')
$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot
if (-not (Test-Path -LiteralPath $Target -PathType Container)) {
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
}
$targetFull = (Resolve-Path -LiteralPath $Target).Path
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $targetFull "_更新备份\$stamp"
$map = @{
 '01-2026-09-30-smart-learning-planner-design.md' = '2026-09-30-smart-learning-planner-design.md'
 '02-2026-09-30-smart-learning-planner-requirements-spec.md' = '2026-09-30-smart-learning-planner-requirements-spec.md'
 '03-2026-09-30-smart-learning-planner-srs-questions.md' = '2026-09-30-smart-learning-planner-srs-questions.md'
 '04-2026-10-20-smart-learning-planner-class-report-design.md' = '2026-10-20-smart-learning-planner-class-report-design.md'
 '05-2026-10-20-smart-learning-planner-technical-design.md' = '2026-10-20-smart-learning-planner-technical-design.md'
 '06-2026-10-21-smart-learning-planner-class-report-speech.md' = '2026-10-21-smart-learning-planner-class-report-speech.md'
}
$files = Get-ChildItem -LiteralPath $source -File | Where-Object { $_.Extension -in @('.md', '.pptx') }
foreach ($file in $files) {
    $names = @($file.Name)
    if ($map.ContainsKey($file.Name)) { $names += $map[$file.Name] }
    $matches = @(Get-ChildItem -LiteralPath $targetFull -Recurse -File | Where-Object {
        $_.Name -in $names -and $_.FullName -notlike "$(Join-Path $targetFull '_更新备份')*"
    })
    if ($matches.Count -gt 1) {
        Write-Warning "找到多个同名候选，跳过 $($file.Name)：$($matches.FullName -join '; ')"
        continue
    }
    if ($matches.Count -eq 1) {
        $destination = $matches[0].FullName
        $relative = $destination.Substring($targetFull.Length).TrimStart('\')
        $backup = Join-Path $backupRoot $relative
        New-Item -ItemType Directory -Path (Split-Path $backup) -Force | Out-Null
        Copy-Item -LiteralPath $destination -Destination $backup -Force
        Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
        Write-Host "已更新：$relative（旧版已备份）"
    } else {
        $destination = Join-Path $targetFull $file.Name
        Copy-Item -LiteralPath $file.FullName -Destination $destination
        Write-Host "已新增：$($file.Name)"
    }
}
Write-Host "完成。备份位置：$backupRoot"
