# Star Savior 10 消除提示器

![platform](https://img.shields.io/badge/platform-Windows-blue)
![python](https://img.shields.io/badge/python-3.13-blue)
![release](https://img.shields.io/github/v/release/Sid-1996/starsavior-make10-helper)
![downloads](https://img.shields.io/github/downloads/Sid-1996/starsavior-make10-helper/total)
![stars](https://img.shields.io/github/stars/Sid-1996/starsavior-make10-helper)
![license](https://img.shields.io/github/license/Sid-1996/starsavior-make10-helper)

繁體中文 | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

「數字 10 消除遊戲」的視覺輔助提示器。**只分析畫面並提供視覺提示，不操作遊戲**，滑鼠操作完全由使用者自己完成。

## 下載（Windows 免安裝綠色版）

到 [**Releases](../../releases)** 下載 `StarSaviorHelper.exe`，雙擊即用：
免安裝、設定檔（`settings.json`）和日誌都留在 exe 旁邊，刪掉 exe 即乾淨移除。

> 需要 **Windows 10 1803 以上 64-bit**（後台抓圖用；更舊的系統會自動退回前景模式，遊戲需保持可見）。

## 操作示意

**開局**：滿盤時一次顯示前 N 組彩色編號提示，1 號綠框照著打：

![開局滿盤提示](docs/images/demo-early.webp)

**中盤**：消除留下的空格可跨越，提示自動跟著新盤面走：

![中盤提示](docs/images/demo-mid.webp)

**後盤**：剩餘數字稀疏時，提示照樣精準定位：

![後盤提示](docs/images/demo-late.webp)

## 功能亮點

- **打開就緒、按 F8 開工**：自動綁定遊戲視窗＋記住棋盤位置，搬窗／換解析度免重框
- **連續自動偵測**：畫面變化 → 等待穩定 → 重辨識 → 更新提示（消除動畫自動跳過）
- **彩色編號提示**：前 N 組提示各用不同顏色＋編號徽章，重疊也分得清；框住同一組數字的重複框只留最小一個
- **後台抓圖**：遊戲被其他視窗蓋住照常工作；最小化自動等待、關閉自動停止
- **極簡主視窗**：一行狀態＋一顆開關＋提示數，平常碰不到的收進「設定…」

## 開發進度

- [x] **Phase 1**：ROI 框選 + 設定儲存
- [x] **Phase 2**：10×15 Grid + Cell State + Template Matching（含 1~9 完整模板）
- [x] **Phase 3**：Rectangle Solver（純演算法，只吃 BoardState）
- [x] **Phase 4**：Hint Selector（最小 area + 固定掃描順序＋同組數字去重，選前 N 個）
- [x] **Phase 5**：透明 Click-through Overlay（外框 + 起點 + 終點）
- [x] **Phase 6**：畫面變化偵測（穩定等待 + Hint Lock + 穩定後重辨識）
- [x] **Phase 7**：整合測試與 UX 修正（含 F8 全域快捷鍵）

## 使用方式（目標：打開就緒，按 F8 開工）

1. 開啟 StarSavior 遊戲（標題即 `StarSavior` 的視窗），再開本工具
2. 工具自動綁定遊戲視窗＋驗證棋盤位置；若已有上次的框選，直接顯示「就緒」
3. 第一次使用：主視窗只會看到「**框選辨識區域來開始**」→ 以後台遊戲畫面為底
   拖曳框住 10 × 15 棋盤（**Enter 或雙擊＝確認**、**Esc＝取消**；
   存的是視窗相對比例，搬窗／換解析度免重框），框完自動就緒
4. 按「**開始監控 (F8)**」開工；`F8`＝開始／停止監控（監控總開關，只控制提示流程）
5. 「**同時提示數**」（1~10，預設 5）：一次顯示前 N 組提示；
   1 號首選亮綠粗框照著打，2~N 號各用不同顏色＋編號徽章，重疊也分得清；
   框住同一組數字的重複矩形只留最小一個（多的只是空格留白，消下去一樣）；偏好會記住
6. 平常碰不到的東西全在「**設定…**」：ROI 微調／自動校正／預覽、辨識矩陣、主視窗置頂、
   語言（繁中／English／日本語／한국어，預設跟系統語言，系統非此四者時用英文，切換立即生效）

抓圖管線：Windows 後台抓圖（被蓋也活）優先，不可用時退回前景；
遊戲最小化顯示「等待遊戲視窗」，關閉自動停止。

## Phase 1 使用方式（框選細節）

1. 點主視窗引導按鈕或設定裡的「**框選辨識區域**」→ 主視窗暫時隱藏，出現全螢幕選取介面
2. 按住滑鼠左鍵**拖曳**大略框住遊戲的 10 × 15 數字棋盤（任意方向皆可，畫面上會即時顯示 X/Y/W/H）
3. 放開後會**自動對齊**到實際棋盤位置，並顯示 10 × 15 格線供檢查
   - 對齊失敗時自動使用原始選取範圍
   - 按 `A` 可切換自動對齊開/關
4. **Enter 或雙擊＝確認**、**Esc＝取消**、**重新拖曳＝重選**
5. 也可用設定對話框的 X / Y / Width / Height 數值欄手動微調；「**自動校正**」按鈕可用即時畫面重新對齊現有 ROI
6. ROI 會自動儲存在專案根目錄 `settings.json`，下次啟動自動載入
7. 啟動時若遊戲視窗移動了，程式會自動吸附到新位置並更新設定
 （先在舊位置附近找，找不到再全螢幕搜尋＋辨識驗證；都找不到才沿用舊設定）
8. 設定對話框的預覽區會顯示框選結果與 10 × 15 格線，協助確認對齊

## Phase 2 / 3 使用方式

- 監控中的即時 10×15 辨識矩陣可在設定對話框查看（唯讀）
- 重建數字模板：`uv run python tools/build_templates.py <遊戲截圖> <標註JSON>`
 （標註格式 `{"row,col": digit}`；ROI 預設讀 `settings.json`）
- Solver 是純函式 `core/solver.py::find_rectangles(board)`；
  單獨測試：`uv run pytest tests/test_solver.py`

## Phase 5 使用方式

- 監控中棋盤穩定變化且無 UNKNOWN 時，自動計算前 N 個提示並顯示透明 Overlay
 （1 號首選綠框＋綠起點＋青終點，標示建議的滑鼠拖曳起終格中心；
  2~N 號各用不同顏色＋編號徽章，一次全顯示）
- Overlay 不接收滑鼠、不搶焦點；停止監控（或 F8）即隱藏
- 擷取前會自動隱藏 Overlay，避免框線污染辨識

## Phase 6 使用方式

- 按「**開始監控**」（或 F8）：每 300ms 比對 ROI 畫面，連續 3 幀穩定且與基準不同
 才重辨識（消除動畫中間幀會被跳過）；棋盤真正變化才更新 Overlay
 （Hint Lock），否則保持原提示
- 「**停止監控**」：停止迴圈並隱藏提示；變更 ROI 會自動先停止監控
- 監控中狀態列會顯示 `#tick 穩定run/3` 進度與最近事件
 （已更新提示／維持提示／UNKNOWN 等待），卡住時先看這行
- `debug/monitor.log` 記錄每次穩定觸發、重辨識結果與 Overlay 殘留重試，
 回報問題時請附上這段日誌
- `F8`＝開始／停止監控（監控總開關，只控制提示流程，不操作遊戲）

## Phase 7 說明

- `tests/test_integration.py`：用 repo 內真實模板拼出合成棋盤，
  端到端驗證 ROI 畫面 → 辨識 → Solver → Hint → Overlay 幾何，
  以及跨棋盤變化的 monitor 全鏈
- 變化偵測用「明顯變化像素比例」（非全圖平均），單格消除（約佔全 ROI 1%）
  也能觸發；門檻見 `core/monitor.py::MonitorConfig`

## 常見問題

- **顯示「找不到遊戲視窗」**：先開遊戲再按開始監控；確認遊戲視窗標題是 `StarSavior` 且未最小化。
- **按了開始監控但提示不更新**：看狀態列——「等待遊戲視窗」表示最小化了；「維持提示（棋盤未變）」表示畫面真的沒變；卡住先看 `debug/monitor.log`。
- **很多格顯示問號（UNKNOWN）**：通常是遊戲特效／動畫遮住數字，等畫面靜止會自動重辨識；若長期如此，可能是遊戲改版換了字體。
- **框選框不準**：框選放開後會自動對齊，失敗會用原始範圍；到「設定…」按「自動校正」，或直接重框。
- **F8 沒反應**：可能被其他軟體佔用；直接按主視窗的開關鈕效果一樣。

## Roadmap

大功能已完工；後續以修 bug 和小體驗優化為主。歡迎開 Issue（附上 `debug/monitor.log` 會更快釐清）。

## 開發者執行

- Python 3.13＋[uv](https://docs.astral.sh/uv/)
- **開發測試：直接雙擊 `run.bat`**（首次執行會自動安裝依賴；錯誤時視窗會暫停顯示訊息）

或使用命令列：

```powershell
uv sync
uv run python main.py
```

## 測試

```powershell
uv run pytest
```

## CodeGraph（程式碼索引，方便維護查詢）

```powershell
codegraph sync    # 改完程式後同步索引（增量，很快）
codegraph index   # 索引壞掉或大重構時整份重建
```

- 索引檔放 `.codegraph/`（SQLite），只活在本機、不進 git；新 clone 下來跑一次 `codegraph init` 即可
- 日常查碼直接問（MCP `codegraph_explore`）：一次回傳相關符號原文＋呼叫鏈，不用 grep＋Read 繞圈

## 程式架構

```
main.py                     # 進入點（DPI awareness + QApplication）
core/
    roi_model.py            # Roi（絕對）+ RoiFrac（視窗相對比例）+ IoU
    settings_store.py       # 設定 JSON：視窗標題 / roi_frac / ui 偏好（舊 roi 自動遷移）
    game_window.py          # 目標視窗綁定（精確標題＋可見＋最大）與客戶區
    window_capture.py       # WGC 後台擷取會話＋單幀抓取（被蓋也活）
    screen_capture.py       # mss 前景擷取（備援；框選背景、絕對座標 ROI 用）
    board_align.py          # 10×15 棋盤自動對齊（ROI Auto-Align）
    grid.py                 # ROI 固定切成 10×15（CellGeometry 含 center）
    board_state.py          # BoardState + CellState（DIGIT/EMPTY/UNKNOWN 三態分離）
    templates.py            # TemplateStore：1~9 模板讀寫（不管比對）
    recognition.py          # DigitRecognizer：白 tile 缺席 → EMPTY；否則模板比對
    board_builder.py        # ROI 畫面 → 切格 → 辨識 → BoardState
    solver.py               # Rectangle Solver：純演算法，BoardState → 全部合法矩形
    hint_selector.py        # Hint Selector：最小 area + 固定順序＋同組去重，選前 N 個
    monitor.py              # 畫面穩定追蹤 + Hint Lock（不碰 GUI/擷取）
    paths.py                # frozen 路徑相容（資源走解包暫存，可寫走 exe 旁）
    i18n.py                 # UI 字串 zh/en/ja/ko＋系統語言偵測
gui/
    main_window.py          # 主視窗（一行狀態＋監控開關＋提示數＋首次引導；邏輯仍住這裡）
    settings_dialog.py      # 設定對話框（ROI 框選/微調/預覽、辨識矩陣、置頂）
    roi_selector.py         # 全螢幕框選視窗（含自動對齊；背景可為後台幀）
    recognition_panel.py    # 10×15 辨識結果矩陣顯示
    hint_overlay.py         # 透明 Click-through Overlay（10 色外框＋起/終點＋編號徽章，不吃滑鼠）
    global_hotkey.py        # F8 全域快捷鍵（Win32 RegisterHotKey，監控總開關）
    image_utils.py          # QImage ↔ numpy 轉換
docs/
    adr/                    # 架構決策記錄（後台抓圖、相對 ROI…）
CONTEXT.md                  # 專案術語表（唯一推薦用語＋禁用詞）
templates/
    1.png ... 9.png         # 真實遊戲畫面擷取的數字模板（tools/build_templates.py 建立）
tools/
    build_templates.py      # 從遊戲截圖 + 標註 JSON 建立/更新模板
tests/                      # pytest 單元測試（含 solver vs 暴力參考實作比對）
```

### 座標系統

管線全程使用**實體螢幕像素**：`main.py` 設定 Per-Monitor DPI awareness 並關閉 Qt High-DPI 縮放（`QT_ENABLE_HIGHDPI_SCALING=0`），確保 Qt 座標與擷取座標一致，後續 Overlay 也沿用同一座標系。設定檔存的是**視窗相對比例**（`roi_frac`），啟動／每 tick 以當下遊戲客戶區換算成絕對座標，因此搬窗／換解析度免重框。

## 免責聲明

本工具只讀取遊戲畫面並顯示提示，不修改遊戲、不送出任何滑鼠／鍵盤操作。請遵守遊戲的服務條款，使用風險自負（MIT License，不負任何擔保責任）。
