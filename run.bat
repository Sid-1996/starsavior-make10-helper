@echo off
chcp 65001 > nul
cd /d "%~dp0"

REM 使用 uv 執行專案（會自動使用 .venv 虛擬環境；尚未安裝依賴時先自動 uv sync）
where uv >nul 2>&1
if errorlevel 1 (
    echo 找不到 uv，請先安裝：https://docs.astral.sh/uv/
    pause
    exit /b 1
)

if not exist .venv (
    echo 首次執行，安裝依賴中...
    uv sync
    if errorlevel 1 (
        echo 依賴安裝失敗。
        pause
        exit /b 1
    )
)

uv run python main.py
if errorlevel 1 (
    echo 啟動過程發生錯誤。
    REM 錯誤時暫停，讓使用者能讀錯誤訊息；正常結束則自動關閉視窗。
    pause
)
