# Django ASGI Server (Daphne) 起動スクリプト
# WebSocketサポートを含むDjangoサーバーを起動します

param(
    [int]$Port = 8000,
    [int]$Verbosity = 1,
    [string]$Host = "127.0.0.1"
)

Write-Host "Django ASGI Server (Daphne) を起動中..." -ForegroundColor Green
Write-Host "ポート: $Port" -ForegroundColor Yellow
Write-Host "ホスト: $Host" -ForegroundColor Yellow
Write-Host "詳細レベル: $Verbosity" -ForegroundColor Yellow
Write-Host "WebSocket通信が有効化されています" -ForegroundColor Cyan
Write-Host ""
Write-Host "サーバーを停止するには Ctrl+C を押してください" -ForegroundColor Red
Write-Host ""

# Djangoプロジェクトのディレクトリに移動
Set-Location -Path (Join-Path $PSScriptRoot "django")

# Daphneサーバーを起動
try {
    uv run python -m daphne -b $Host -p $Port -v $Verbosity carry_out_approval.asgi:application
}
catch {
    Write-Host "エラー: Daphneサーバーの起動に失敗しました" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "以下を確認してください:" -ForegroundColor Yellow
    Write-Host "1. 仮想環境が正しく設定されているか" -ForegroundColor White
    Write-Host "2. daphneがインストールされているか: uv pip install daphne" -ForegroundColor White
    Write-Host "3. Djangoの設定が正しいか" -ForegroundColor White
    exit 1
}
