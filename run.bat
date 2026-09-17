@echo off
chcp 65001 > nul
cd /d "%~dp0"

REM 開發測試用：使用 uv 執行專案（優先使用 .venv 虛擬環境；缺少依賴時先自動 uv sync）
REM 一般使用者請到 GitHub Releases 下載打包好的 StarSaviorHelper.exe，免安裝雙擊即用。
where uv >nul 2>&1
if errorlevel 1 (
    echo 找不到 uv，請先安裝 https://docs.astral.sh/uv/
    pause
    exit /b 1
)

if not exist .venv (
    echo 首次執行，安裝依賴中...
    uv sync
    if errorlevel 1 (
        echo 依賴安裝失敗
        pause
        exit /b 1
    )
)

uv run python main.py
if errorlevel 1 (
    echo 程式執行發生錯誤
    REM 錯誤時暫停讓使用者能讀取錯誤訊息；正常結束直接關閉視窗
    pause
)
