param(
    [Parameter(Mandatory=$true)][string]$ConfigId,
    [string]$Operator = $env:USERNAME,
    [string]$PreviousReport = "",
    [ValidateSet('DeepSeek','OpenAI','DashScope')][string]$Provider = 'DashScope'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) { throw '项目Python环境不存在，请先恢复统一运行版' }
$secretNames = @{DeepSeek='DEEPSEEK_API_KEY';OpenAI='OPENAI_API_KEY';DashScope='DASHSCOPE_API_KEY'}
$secretName = $secretNames[$Provider]
if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($secretName,'Process'))) {
    $secret = Read-Host "请输入 $Provider API Key（输入不回显）" -AsSecureString
    if ($secret.Length -eq 0) { throw 'API Key不能为空' }
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try { [Environment]::SetEnvironmentVariable($secretName,[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer),'Process') }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer); $secret.Dispose() }
}
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
if (!$env:ZHIXING_DATA) { $env:ZHIXING_DATA = Join-Path $projectRoot 'backend/data' }
$env:PYTHONUTF8 = '1'
$reportPath = Join-Path $env:ZHIXING_DATA ('model-quality-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
Write-Host '当前teaching-v4共60场景，每例失败最多2次模型修复，会额外消耗额度；仅同判据、同提示词、同输入可复用旧响应，跨版本将重新调用并产生费用。'
$extraArgs = @()
if ($PreviousReport) { $extraArgs = @('--previous-report', $PreviousReport) }
& $pythonPath -m app.cli evaluate-cloud $reportPath --config-id $ConfigId --operator $Operator @extraArgs
if ($LASTEXITCODE -ne 0) { throw '质量评估失败，请查看上方错误' }
Write-Host "报告已保存：$reportPath"
