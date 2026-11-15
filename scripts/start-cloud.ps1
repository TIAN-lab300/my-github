param([ValidateSet('DeepSeek','OpenAI','DashScope')][string]$Provider = 'DashScope', [int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$names = @{DeepSeek='DEEPSEEK_API_KEY'; OpenAI='OPENAI_API_KEY'; DashScope='DASHSCOPE_API_KEY'}
$secretName = $names[$Provider]
if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($secretName,'Process'))) {
    $secret = Read-Host "请在本机输入 $Provider API Key（输入不回显）" -AsSecureString
    if ($secret.Length -eq 0) { throw '模型密钥不能为空' }
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try { [Environment]::SetEnvironmentVariable($secretName,[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer),'Process') }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer); $secret.Dispose() }
}
& (Join-Path $PSScriptRoot 'start.ps1') -Port $Port
if ($LASTEXITCODE -ne 0) { throw "服务启动失败：$LASTEXITCODE" }

