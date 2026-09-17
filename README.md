# Star Savior 10 消除提示器

「數字 10 消除遊戲」的視覺輔助提示器。**只分析畫面並提供視覺提示，不操作遊戲**，滑鼠操作完全由使用者自己完成。

## 開發進度

- [x] **Phase 1**：ROI 框選 + 設定儲存
- [ ] Phase 2：10×15 Grid + Cell State + Template Matching
- [ ] Phase 3：Rectangle Solver
- [ ] Phase 4：Hint Selector
- [ ] Phase 5：透明 Click-through Overlay
- [ ] Phase 6：畫面變化偵測
- [ ] Phase 7：整合測試與 UX 修正

## 環境需求

- Python 3.13
- [uv](https://docs.astral.sh/uv/)

## 安裝與執行

**快速啟動：直接雙擊 `run.bat`**（首次執行會自動安裝依賴；錯誤時視窗會暫停顯示訊息）

或使用命令列：

```powershell
uv sync
uv run python main.py
```

## Phase 1 使用方式

1. 點「**框選辨識區域**」→ 主視窗暫時隱藏，出現全螢幕選取介面
2. 按住滑鼠左鍵**拖曳**大略框住遊戲的 10 × 15 數字棋盤（任意方向皆可，畫面上會即時顯示 X/Y/W/H）
3. 放開後會**自動對齊**到實際棋盤位置，並顯示 10 × 15 格線供檢查
   - 對齊失敗時自動使用原始選取範圍
   - 按 `A` 可切換自動對齊開/關
4. **Enter 或雙擊＝確認**、**Esc＝取消**、**重新拖曳＝重選**
5. 也可用主視窗的 X / Y / Width / Height 數值欄手動微調；「**自動校正**」按鈕可用即時畫面重新對齊現有 ROI
6. ROI 會自動儲存在專案根目錄 `settings.json`，下次啟動自動載入
7. 預覽區會顯示框選結果與 10 × 15 格線，協助確認對齊

## 測試

```powershell
uv run pytest
```

## 程式架構

```
main.py                     # 進入點（DPI awareness + QApplication）
core/
    roi_model.py            # Roi 資料模型、驗證、邊界限制
    settings_store.py       # 設定 JSON 儲存 / 載入
    screen_capture.py       # mss 螢幕擷取（實體像素座標）
    board_align.py          # 10×15 棋盤自動對齊（ROI Auto-Align）
gui/
    main_window.py          # 主視窗（ROI 設定 / 自動校正 / 預覽 / 狀態）
    roi_selector.py         # 全螢幕框選視窗（含自動對齊）
    image_utils.py          # QImage ↔ numpy 轉換
tests/                      # pytest 單元測試
```

### 座標系統

全程使用**實體螢幕像素**：`main.py` 設定 Per-Monitor DPI awareness 並關閉 Qt High-DPI 縮放（`QT_ENABLE_HIGHDPI_SCALING=0`），確保 Qt 座標與 mss 擷取座標一致，後續 Overlay 也沿用同一座標系。
