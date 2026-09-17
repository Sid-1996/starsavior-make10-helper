# 後台抓圖採用 Windows.Graphics.Capture

mss 只能拍前景合成畫面（遊戲被瀏覽器蓋住就拍到瀏覽器），Win32 PrintWindow 對 GPU 渲染的遊戲回傳全黑；實測 Windows.Graphics.Capture（windows-capture 套件）在遊戲被完全蓋住時仍拿到即時遊戲表面，因此後台管線用它，mss 只留作備援。

## Considered Options

- **mss 前景**：簡單、跨平台，但被遮擋即失效，且 Overlay 會入鏡需隱藏重試。
- **PrintWindow**：實測全黑（GPU 遊戲不走 GDI），出局。
- **DXGI Output Duplication**：同樣只看得到前景，出局。
- **Windows.Graphics.Capture**：後台活、像素可讀回、不含自家 Overlay；代價是 Windows only 新依賴＋遊戲最小化時幀凍結（以「等待遊戲視窗」狀態處理）。
