param(
    [int]$StartBook = 1,
    [double]$BudgetRmb = 150,
    [ValidateSet('siliconflow', 'ark', 'bailian')]
    [string]$Provider = 'siliconflow'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$pipeline = Join-Path $PSScriptRoot 'v3_pipeline.py'
$providerSettings = @{
    siliconflow = @{
        KeyEnvironment = 'SILICONFLOW_API_KEY'
        RouteConfig = $null
    }
    ark = @{
        KeyEnvironment = 'ARK_API_KEY'
        RouteConfig = 'volcengine_ark_routes.json'
    }
    bailian = @{
        KeyEnvironment = 'DASHSCOPE_API_KEY'
        RouteConfig = 'aliyun_bailian_routes.json'
    }
}
$providerSetting = $providerSettings[$Provider]
$routeConfigPath = if ($providerSetting.RouteConfig) {
    Join-Path $PSScriptRoot $providerSetting.RouteConfig
} else {
    $null
}
$reportDir = Join-Path $projectRoot 'Md\V3\_reports'
$stdout = Join-Path $reportDir 'V3后台运行.log'
$stderr = Join-Path $reportDir 'V3后台错误.log'
$processFile = Join-Path $reportDir 'V3后台进程.json'

$providerKey = [Environment]::GetEnvironmentVariable($providerSetting.KeyEnvironment, 'User')
if ([string]::IsNullOrWhiteSpace($providerKey)) {
    throw "当前 Windows 用户环境变量中缺少 $($providerSetting.KeyEnvironment)。"
}
if ($routeConfigPath -and -not (Test-Path -LiteralPath $routeConfigPath)) {
    throw "缺少模型路由配置：$routeConfigPath"
}

try {
    # Persisted only in the user's environment; this child process receives it
    # without putting a key in the command line, a project file, or the logs.
    Set-Item -Path "Env:$($providerSetting.KeyEnvironment)" -Value $providerKey
    $env:V3_MAX_BUDGET_RMB = [string]$BudgetRmb
    if ($routeConfigPath) {
        $routeConfig = Get-Content -LiteralPath $routeConfigPath -Raw | ConvertFrom-Json
        $env:V3_WRITER_MODEL = [string]$routeConfig.writer_model
        $env:V3_REPAIR_MODEL = [string]$routeConfig.repair_model
        $env:V3_ESCALATION_MODEL = [string]$routeConfig.escalation_model
        $env:V3_JUDGE_MODEL = [string]$routeConfig.judge_model
        $env:V3_MAX_CONCURRENT_API_REQUESTS = [string]$routeConfig.max_concurrent_api_requests
        $env:V3_MODEL_ROUTES_JSON = ($routeConfig.routes | ConvertTo-Json -Compress -Depth 8)
    }
    $proc = Start-Process -FilePath 'python' `
        -ArgumentList @($pipeline, 'run-all', '--start-book', [string]$StartBook) `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -WindowStyle Hidden `
        -PassThru
    [pscustomobject]@{
        pid = $proc.Id
        started_at = [DateTime]::UtcNow.ToString('o')
        start_book = $StartBook
        provider = $Provider
        max_budget_rmb = $BudgetRmb
        command = 'python v3_pipeline.py run-all'
        note = 'API key inherited through process environment only; it is not stored here.'
    } | ConvertTo-Json | Set-Content -LiteralPath $processFile -Encoding utf8
    Write-Output "V3 后台进程已启动，PID=$($proc.Id)"
}
finally {
    Remove-Item -Path "Env:$($providerSetting.KeyEnvironment)" -ErrorAction SilentlyContinue
    $providerKey = $null
}
