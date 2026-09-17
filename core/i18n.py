"""UI 多語系（中/英/日/韓）：字串表＋系統語言偵測＋切換。

- 支援語言：zh（繁體中文，預設）/ en / ja / ko；系統語言不在此列一律英文。
- 偵測：QLocale.system().name()（Qt 應用最準；失敗退回 locale 模組）。
- 偏好存在 settings.json（ui.language：auto/zh/en/ja/ko）；切換立即生效。
- 取用：一律經 t(key, **kwargs)；缺 key 退英文再退 key 本身，不丟例外。
- 開發文件/註解維持繁體中文，只翻譯運行時使用者可見字串。
"""

from __future__ import annotations

SUPPORTED_LANGUAGES = ("zh", "en", "ja", "ko")
PREF_AUTO = "auto"
PREF_CHOICES = (PREF_AUTO, *SUPPORTED_LANGUAGES)

_current: str | None = None  # None＝跟系統；set_language 可鎖定


def _zh() -> dict[str, str]:
    return {
        "app.title": "Star Savior 10 消除提示器",
        "main.toggle_start": "開始監控 (F8)",
        "main.toggle_stop": "停止監控 (F8)",
        "main.toggle_tip": "開始／停止監控（F8 全域快捷鍵同義）。",
        "main.toggle_tip_nohotkey": "開始／停止監控（F8 全域快捷鍵註冊失敗，只能用此按鈕）。",
        "main.guide_btn": "框選辨識區域來開始",
        "main.guide_tip": "第一次使用：拖曳框住遊戲的 10 × 15 棋盤（Enter 確認、Esc 取消）。",
        "main.hints_label": "同時提示數：",
        "main.hints_tip": "同時顯示幾組提示（1 號是首選照著打，其餘是備選）；偏好會記住。",
        "main.settings_btn": "設定…",
        "main.settings_tip": "ROI 框選／微調／預覽、辨識矩陣、主視窗置頂、語言。",
        "main.status_starting": "啟動中…",
        "main.status_guide": "歡迎使用：按下方按鈕框選遊戲的 10 × 15 棋盤來開始。",
        "main.status_no_window": "找不到「{title}」視窗，請先開啟遊戲再按開始監控。",
        "main.status_ready": "就緒：按「開始監控」或 F8。",
        "main.status_monitoring": "監控中 #{ticks} 穩定{run}/{required}{note}",
        "note.starting": "啟動，等待穩定畫面",
        "note.wait_window": "等待遊戲視窗（最小化中）",
        "note.wait_bg": "等待後台畫面更新…",
        "note.recognizing": "重辨識中…",
        "note.keep_overlay": "維持提示（Overlay 未消失，跳過本次）",
        "note.hints_updated": "已更新提示 {first}（共 {count} 組）",
        "note.no_rect": "此盤無合法矩形",
        "note.keep_unknown": "維持提示（UNKNOWN，等下次穩定畫面）",
        "note.keep_same": "維持提示（棋盤未變）",
        "note.foreground": "前景模式（遊戲需保持可見）",
        "repair.not_found": "（未在畫面上找到棋盤：若遊戲不在對戰畫面可忽略）",
        "repair.realigned": "（啟動時已自動對齊到新位置）",
        "msg.select_title": "框選失敗",
        "msg.select_body": "建立框選介面時發生錯誤：\n{detail}",
        "msg.align_title": "自動校正",
        "msg.align_failed": "自動校正失敗",
        "msg.align_error": "擷取或處理畫面時發生錯誤：\n{detail}",
        "msg.align_oos": "目前的辨識區域不在螢幕範圍內。",
        "msg.align_miss": "無法偵測 10×15 棋盤位置。\n請確認遊戲畫面完整可見且辨識區域已大致框住棋盤後重試，或到「設定…」重新框選。",
        "msg.start_title": "開始監控",
        "msg.start_no_window": "找不到遊戲視窗，請先開啟遊戲。",
        "msg.start_no_roi": "尚未設定辨識區域，請先框選。",
        "msg.fail_title": "監控失敗",
        "msg.fail_closed": "遊戲視窗已關閉，已停止監控。",
        "msg.fail_capture": "擷取畫面時發生錯誤，已停止監控：\n{detail}",
        "msg.fail_recognize": "重新辨識時發生錯誤，已停止監控：\n{detail}",
        "settings.title": "設定",
        "settings.roi_group": "辨識區域 (ROI)",
        "settings.select": "框選辨識區域",
        "settings.align": "自動校正",
        "settings.align_tip": "以即時畫面偵測 10×15 棋盤位置，自動微調目前的辨識區域。\n使用時請確保遊戲畫面完整可見、未被遮擋。",
        "settings.topmost": "主視窗置頂",
        "settings.topmost_tip": "單螢幕全螢幕遊戲時保持主視窗可操作；偏好會記住。",
        "settings.preview_group": "ROI 預覽（含 10 × 15 格線）",
        "settings.preview_empty": "尚未設定辨識區域",
        "settings.preview_failed": "預覽失敗：{error}",
        "settings.spin_tip": "可直接輸入數值微調，也可用上下鍵調整",
        "settings.language": "語言：",
        "settings.language_tip": "切換後立即生效。",
        "settings.close": "關閉",
        "panel.group": "辨識結果預覽（10 × 15）",
        "panel.initial": "尚未辨識",
        "panel.stats": "數字 {digit} 格 / 空格 {empty} 格 / 未知 {unknown} 格",
        "panel.missing": "\n缺少模板：{missing}（相關格子只能判為 UNKNOWN，請先建立模板）",
        "selector.idle": "按住滑鼠左鍵拖曳，框選 10 × 15 棋盤辨識區域（Esc 取消）",
        "selector.aligned": "✓ 已自動對齊 10×15 棋盤 — Enter／雙擊確認　Esc 取消　拖曳重選　A 切換自動對齊",
        "selector.not_aligned": "⚠ 自動對齊失敗，使用原始選取 — Enter／雙擊確認　Esc 取消　拖曳重選　A 切換自動對齊",
        "selector.align_off": "自動對齊：關 — Enter／雙擊確認　Esc 取消　拖曳重選　A 切換自動對齊",
    }


def _en() -> dict[str, str]:
    return {
        "app.title": "Star Savior 10 Match Helper",
        "main.toggle_start": "Start Monitoring (F8)",
        "main.toggle_stop": "Stop Monitoring (F8)",
        "main.toggle_tip": "Start/stop monitoring (same as the F8 global hotkey).",
        "main.toggle_tip_nohotkey": "Start/stop monitoring (F8 hotkey registration failed; use this button).",
        "main.guide_btn": "Select the Board Area to Start",
        "main.guide_tip": "First run: drag a box around the game's 10 × 15 board (Enter to confirm, Esc to cancel).",
        "main.hints_label": "Hints:",
        "main.hints_tip": "How many hint boxes to show (No.1 is the primary move, the rest are backups); remembered.",
        "main.settings_btn": "Settings…",
        "main.settings_tip": "ROI select / fine-tune / preview, board matrix, always-on-top, language.",
        "main.status_starting": "Starting…",
        "main.status_guide": "Welcome: click the button below and drag a box around the game's 10 × 15 board to start.",
        "main.status_no_window": "Cannot find the “{title}” window. Open the game first, then start monitoring.",
        "main.status_ready": "Ready: press “Start Monitoring” or F8.",
        "main.status_monitoring": "Monitoring #{ticks} stable {run}/{required}{note}",
        "note.starting": "started, waiting for a stable frame",
        "note.wait_window": "waiting for the game window (minimized)",
        "note.wait_bg": "waiting for background frames…",
        "note.recognizing": "recognizing…",
        "note.keep_overlay": "keeping hints (overlay would not go away, skipped)",
        "note.hints_updated": "hints updated {first} ({count} groups)",
        "note.no_rect": "no legal rectangle on this board",
        "note.keep_unknown": "keeping hints (UNKNOWN, waiting for next stable frame)",
        "note.keep_same": "keeping hints (board unchanged)",
        "note.foreground": "foreground mode (keep the game visible)",
        "repair.not_found": "(board not found on screen; ignore if the game is not in a match)",
        "repair.realigned": "(auto-aligned to the new position at startup)",
        "msg.select_title": "Selection Failed",
        "msg.select_body": "Failed to open the selection UI:\n{detail}",
        "msg.align_title": "Auto Align",
        "msg.align_failed": "Auto Align Failed",
        "msg.align_error": "Failed to capture or process the frame:\n{detail}",
        "msg.align_oos": "The current ROI is outside the screen.",
        "msg.align_miss": "Cannot detect the 10×15 board.\nMake sure the game is fully visible and the ROI roughly covers the board, then retry — or reselect via “Settings…”.",
        "msg.start_title": "Start Monitoring",
        "msg.start_no_window": "Cannot find the game window. Open the game first.",
        "msg.start_no_roi": "No board area set yet. Select it first.",
        "msg.fail_title": "Monitoring Failed",
        "msg.fail_closed": "The game window was closed. Monitoring stopped.",
        "msg.fail_capture": "Failed to capture the screen. Monitoring stopped:\n{detail}",
        "msg.fail_recognize": "Failed to re-recognize. Monitoring stopped:\n{detail}",
        "settings.title": "Settings",
        "settings.roi_group": "Board Area (ROI)",
        "settings.select": "Select Board Area",
        "settings.align": "Auto Align",
        "settings.align_tip": "Detect the 10×15 board from the live frame and fine-tune the current ROI.\nKeep the game fully visible and unobstructed.",
        "settings.topmost": "Always on top",
        "settings.topmost_tip": "Keep the main window usable over a fullscreen game; remembered.",
        "settings.preview_group": "ROI Preview (with 10 × 15 grid)",
        "settings.preview_empty": "No board area set",
        "settings.preview_failed": "Preview failed: {error}",
        "settings.spin_tip": "Type a value to fine-tune, or use the arrow keys.",
        "settings.language": "Language:",
        "settings.language_tip": "Applies immediately.",
        "settings.close": "Close",
        "panel.group": "Board Preview (10 × 15)",
        "panel.initial": "Not recognized yet",
        "panel.stats": "{digit} digits / {empty} empty / {unknown} unknown",
        "panel.missing": "\nMissing templates: {missing} (those cells can only be UNKNOWN; build templates first)",
        "selector.idle": "Hold left mouse button and drag a box around the 10 × 15 board (Esc to cancel)",
        "selector.aligned": "✓ Auto-aligned to the 10×15 board — Enter/double-click to confirm　Esc to cancel　drag to reselect　A toggles auto-align",
        "selector.not_aligned": "⚠ Auto-align failed, using raw selection — Enter/double-click to confirm　Esc to cancel　drag to reselect　A toggles auto-align",
        "selector.align_off": "Auto-align: OFF — Enter/double-click to confirm　Esc to cancel　drag to reselect　A toggles auto-align",
    }


def _ja() -> dict[str, str]:
    return {
        "app.title": "Star Savior 10 消去ヘルパー",
        "main.toggle_start": "監視開始 (F8)",
        "main.toggle_stop": "監視停止 (F8)",
        "main.toggle_tip": "監視の開始／停止（F8 グローバルホットキーと同じ）。",
        "main.toggle_tip_nohotkey": "監視の開始／停止（F8 の登録に失敗したため、このボタンで操作）。",
        "main.guide_btn": "盤面領域を選択して開始",
        "main.guide_tip": "初回：ゲームの 10 × 15 盤面をドラッグで囲んでください（Enter で確定、Esc でキャンセル）。",
        "main.hints_label": "ヒント数：",
        "main.hints_tip": "表示するヒントの数（1 番が本命、その他は予備）；記憶します。",
        "main.settings_btn": "設定…",
        "main.settings_tip": "ROI 選択／微調整／プレビュー、盤面表示、常に手前、言語。",
        "main.status_starting": "起動中…",
        "main.status_guide": "ようこそ：下のボタンでゲームの 10 × 15 盤面を囲んで開始してください。",
        "main.status_no_window": "「{title}」ウィンドウが見つかりません。ゲームを起動してから開始してください。",
        "main.status_ready": "準備完了：「監視開始」または F8 を押してください。",
        "main.status_monitoring": "監視中 #{ticks} 安定 {run}/{required}{note}",
        "note.starting": "開始、安定フレーム待ち",
        "note.wait_window": "ゲームウィンドウ待ち（最小化中）",
        "note.wait_bg": "バックグラウンドフレーム待ち…",
        "note.recognizing": "再認識中…",
        "note.keep_overlay": "ヒント維持（オーバーレイが消えないためスキップ）",
        "note.hints_updated": "ヒント更新 {first}（全 {count} 件）",
        "note.no_rect": "有効な矩形なし",
        "note.keep_unknown": "ヒント維持（UNKNOWN、次の安定フレーム待ち）",
        "note.keep_same": "ヒント維持（盤面変化なし）",
        "note.foreground": "フォアグラウンドモード（ゲームを見える状態に）",
        "repair.not_found": "（画面に盤面なし：対戦画面でなければ無視してください）",
        "repair.realigned": "（起動時に新位置へ自動調整済み）",
        "msg.select_title": "選択失敗",
        "msg.select_body": "選択画面を開けませんでした：\n{detail}",
        "msg.align_title": "自動調整",
        "msg.align_failed": "自動調整失敗",
        "msg.align_error": "画面の取得または処理に失敗しました：\n{detail}",
        "msg.align_oos": "現在の認識領域が画面外です。",
        "msg.align_miss": "10×15 盤面を検出できません。\nゲーム全体が見え、領域が盤面を概ね覆っているか確認して再試行するか、「設定…」から選択し直してください。",
        "msg.start_title": "監視開始",
        "msg.start_no_window": "ゲームウィンドウが見つかりません。先にゲームを起動してください。",
        "msg.start_no_roi": "盤面領域が未設定です。先に選択してください。",
        "msg.fail_title": "監視失敗",
        "msg.fail_closed": "ゲームウィンドウが閉じられました。監視を停止しました。",
        "msg.fail_capture": "画面取得に失敗しました。監視を停止しました：\n{detail}",
        "msg.fail_recognize": "再認識に失敗しました。監視を停止しました：\n{detail}",
        "settings.title": "設定",
        "settings.roi_group": "盤面領域 (ROI)",
        "settings.select": "盤面領域を選択",
        "settings.align": "自動調整",
        "settings.align_tip": "リアルタイム画面から 10×15 盤面を検出し、現在の ROI を微調整します。\nゲーム全体が見える状態で使用してください。",
        "settings.topmost": "常に手前に表示",
        "settings.topmost_tip": "フルスクリーンゲーム上でも操作可能に；記憶します。",
        "settings.preview_group": "ROI プレビュー（10 × 15 グリッド付き）",
        "settings.preview_empty": "盤面領域が未設定",
        "settings.preview_failed": "プレビュー失敗：{error}",
        "settings.spin_tip": "数値を直接入力、または上下キーで微調整。",
        "settings.language": "言語：",
        "settings.language_tip": "すぐに反映されます。",
        "settings.close": "閉じる",
        "panel.group": "盤面プレビュー（10 × 15）",
        "panel.initial": "未認識",
        "panel.stats": "数字 {digit}／空白 {empty}／不明 {unknown}",
        "panel.missing": "\nテンプレート不足：{missing}（該当マスは UNKNOWN 扱い；先にテンプレートを作成）",
        "selector.idle": "左ボタンでドラッグし、10 × 15 盤面を囲んでください（Esc でキャンセル）",
        "selector.aligned": "✓ 10×15 盤面に自動調整済み — Enter／ダブルクリックで確定　Esc でキャンセル　ドラッグで再選択　A で自動調整切替",
        "selector.not_aligned": "⚠ 自動調整失敗、元の選択を使用 — Enter／ダブルクリックで確定　Esc でキャンセル　ドラッグで再選択　A で自動調整切替",
        "selector.align_off": "自動調整：オフ — Enter／ダブルクリックで確定　Esc でキャンセル　ドラッグで再選択　A で自動調整切替",
    }


def _ko() -> dict[str, str]:
    return {
        "app.title": "Star Savior 10 제거 도우미",
        "main.toggle_start": "모니터링 시작 (F8)",
        "main.toggle_stop": "모니터링 중지 (F8)",
        "main.toggle_tip": "모니터링 시작/중지(F8 전역 단축키와 동일).",
        "main.toggle_tip_nohotkey": "모니터링 시작/중지(F8 등록 실패, 이 버튼 사용).",
        "main.guide_btn": "보드 영역을 선택하여 시작",
        "main.guide_tip": "최초 실행: 게임의 10 × 15 보드를 드래그로 지정하세요(Enter 확인, Esc 취소).",
        "main.hints_label": "힌트 수:",
        "main.hints_tip": "표시할 힌트 수(1번을 따라 하세요, 나머지는 예비); 기억합니다.",
        "main.settings_btn": "설정…",
        "main.settings_tip": "ROI 선택/미세 조정/미리보기, 보드 표시, 항상 위, 언어.",
        "main.status_starting": "시작 중…",
        "main.status_guide": "환영합니다: 아래 버튼으로 게임의 10 × 15 보드를 지정하여 시작하세요.",
        "main.status_no_window": "“{title}” 창을 찾을 수 없습니다. 게임을 먼저 실행한 뒤 시작하세요.",
        "main.status_ready": "준비 완료: “모니터링 시작” 또는 F8을 누르세요.",
        "main.status_monitoring": "모니터링 중 #{ticks} 안정 {run}/{required}{note}",
        "note.starting": "시작, 안정 프레임 대기",
        "note.wait_window": "게임 창 대기(최소화됨)",
        "note.wait_bg": "백그라운드 프레임 대기…",
        "note.recognizing": "재인식 중…",
        "note.keep_overlay": "힌트 유지(오버레이가 사라지지 않아 건너뜀)",
        "note.hints_updated": "힌트 업데이트 {first}(총 {count}개)",
        "note.no_rect": "유효한 사각형 없음",
        "note.keep_unknown": "힌트 유지(UNKNOWN, 다음 안정 프레임 대기)",
        "note.keep_same": "힌트 유지(보드 변경 없음)",
        "note.foreground": "포그라운드 모드(게임을 보이는 상태로 유지)",
        "repair.not_found": "(화면에서 보드를 찾을 수 없음: 대전 화면이 아니면 무시)",
        "repair.realigned": "(시작 시 새 위치로 자동 조정됨)",
        "msg.select_title": "선택 실패",
        "msg.select_body": "선택 화면을 열 수 없습니다:\n{detail}",
        "msg.align_title": "자동 조정",
        "msg.align_failed": "자동 조정 실패",
        "msg.align_error": "화면 캡처 또는 처리 실패:\n{detail}",
        "msg.align_oos": "현재 인식 영역이 화면 밖에 있습니다.",
        "msg.align_miss": "10×15 보드를 감지할 수 없습니다.\n게임이 완전히 보이고 영역이 보드를 대략 덮고 있는지 확인 후 다시 시도하거나, “설정…”에서 다시 선택하세요.",
        "msg.start_title": "모니터링 시작",
        "msg.start_no_window": "게임 창을 찾을 수 없습니다. 먼저 게임을 실행하세요.",
        "msg.start_no_roi": "보드 영역이 설정되지 않았습니다. 먼저 선택하세요.",
        "msg.fail_title": "모니터링 실패",
        "msg.fail_closed": "게임 창이 닫혔습니다. 모니터링을 중지했습니다.",
        "msg.fail_capture": "화면 캡처 실패. 모니터링을 중지했습니다:\n{detail}",
        "msg.fail_recognize": "재인식 실패. 모니터링을 중지했습니다:\n{detail}",
        "settings.title": "설정",
        "settings.roi_group": "보드 영역 (ROI)",
        "settings.select": "보드 영역 선택",
        "settings.align": "자동 조정",
        "settings.align_tip": "실시간 화면에서 10×15 보드를 감지하여 현재 ROI를 미세 조정합니다.\n게임이 완전히 보이는 상태에서 사용하세요.",
        "settings.topmost": "항상 위에 표시",
        "settings.topmost_tip": "전체 화면 게임 위에서도 조작 가능; 기억합니다.",
        "settings.preview_group": "ROI 미리보기(10 × 15 격자)",
        "settings.preview_empty": "보드 영역 미설정",
        "settings.preview_failed": "미리보기 실패: {error}",
        "settings.spin_tip": "값을 직접 입력하거나 방향키로 미세 조정.",
        "settings.language": "언어:",
        "settings.language_tip": "즉시 적용됩니다.",
        "settings.close": "닫기",
        "panel.group": "보드 미리보기(10 × 15)",
        "panel.initial": "아직 인식되지 않음",
        "panel.stats": "숫자 {digit} / 빈칸 {empty} / 알 수 없음 {unknown}",
        "panel.missing": "\n템플릿 부족: {missing}(해당 칸은 UNKNOWN 처리; 먼저 템플릿 생성)",
        "selector.idle": "왼쪽 버튼을 누른 채 드래그하여 10 × 15 보드를 지정하세요(Esc 취소)",
        "selector.aligned": "✓ 10×15 보드에 자동 조정됨 — Enter/더블클릭 확인　Esc 취소　드래그 재선택　A 자동 조정 전환",
        "selector.not_aligned": "⚠ 자동 조정 실패, 원래 선택 사용 — Enter/더블클릭 확인　Esc 취소　드래그 재선택　A 자동 조정 전환",
        "selector.align_off": "자동 조정: 끔 — Enter/더블클릭 확인　Esc 취소　드래그 재선택　A 자동 조정 전환",
    }


_TABLES: dict[str, dict[str, str]] = {
    "zh": _zh(),
    "en": _en(),
    "ja": _ja(),
    "ko": _ko(),
}


def detect_system_language() -> str:
    """偵測系統語言 → zh/en/ja/ko；以上皆非回傳 en。"""
    name = ""
    try:
        from PyQt6.QtCore import QLocale

        name = QLocale.system().name()  # 例："zh_TW"、"en_US"、"ja_JP"、"ko_KR"
    except Exception:
        pass
    if not name:
        try:
            import locale

            name = locale.getlocale()[0] or ""
        except Exception:
            pass
    prefix = name.split("_")[0].split("-")[0].lower()
    if prefix == "zh":
        return "zh"
    if prefix in SUPPORTED_LANGUAGES:
        return prefix
    return "en"


def set_language(code: str | None) -> str:
    """鎖定語言（非法值視為跟系統）；回傳生效的語言碼。"""
    global _current
    if code in SUPPORTED_LANGUAGES:
        _current = code
    else:
        _current = None
    return get_language()


def get_language() -> str:
    """目前生效的語言（鎖定值或系統偵測）。"""
    if _current in SUPPORTED_LANGUAGES:
        return _current
    return detect_system_language()


def resolve_preference(pref: str | None) -> str:
    """把 settings 偏好（auto/zh/en/ja/ko）解成生效語言並鎖定。"""
    if pref in SUPPORTED_LANGUAGES:
        return set_language(pref)
    return set_language(None)


def t(key: str, **kwargs) -> str:
    """取目前語言字串並套用參數；缺 key 退英文再退 key 本身。"""
    lang = get_language()
    template = _TABLES.get(lang, {}).get(key)
    if template is None:
        template = _TABLES["en"].get(key, key)
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template
