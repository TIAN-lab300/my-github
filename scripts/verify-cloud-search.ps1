$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
$pythonPath=Join-Path $projectRoot '.venv\Scripts\python.exe'
if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
    $secret = Read-Host '请在本机输入阿里云百炼 API Key（输入不回显）' -AsSecureString
    if ($secret.Length -eq 0) { throw 'API Key不能为空' }
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try { $env:DASHSCOPE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer); $secret.Dispose() }
}
$env:PYTHONUTF8='1'
Write-Host '将执行一次真实联网搜索，结果保留为待核实来源；会产生API费用。'
& $pythonPath (Join-Path $PSScriptRoot 'verify-cloud-search.py')
if ($LASTEXITCODE -ne 0) { Write-Host '本次未通过，请查看上方具体原因及报告；无需重新进行60场景评估。' -ForegroundColor Yellow; exit 1 }
