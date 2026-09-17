# Star Savior 10 Match Helper

[繁體中文](README.md) | English | [日本語](README.ja.md) | [한국어](README.ko.md)

A visual assistant for the "make-10" number-matching game. **It only analyzes the screen and shows visual hints — it never touches the game**; all mouse actions are yours.

## Download (portable Windows build, no install)

Download `StarSaviorHelper.exe` from [**Releases**](../../releases) and double-click to run:
no installation; `settings.json` and logs stay next to the exe — delete the exe for a clean removal.

## Screenshots

**Early game**: a full board shows the top-N colored numbered hints at once — follow green No.1:

![Early-game hints](docs/images/demo-early.webp)

**Mid game**: empty cells left by clears can be crossed; hints follow the new board automatically:

![Mid-game hints](docs/images/demo-mid.webp)

**Late game**: hints still pinpoint the remaining sparse digits:

![Late-game hints](docs/images/demo-late.webp)

## Highlights

- **Ready on launch, press F8 to work**: auto-binds the game window and remembers the board area; moving the window or changing resolution needs no reselect
- **Continuous auto detection**: frame change → wait for stability → re-recognize → update hints (clearing animations auto-skipped)
- **Colored numbered hints**: each of the top-N hints gets its own color plus a number badge — distinguishable even when overlapping; duplicate boxes around the same digits keep only the smallest one
- **Background capture**: works even when the game is covered by other windows; auto-waits on minimize, auto-stops on close
- **Minimal main window**: one status line + one toggle + hint count; everything else lives under "Settings…"
- **4 UI languages**: Traditional Chinese / English / 日本語 / 한국어, follows the system language (English fallback), switches apply instantly

## Development progress

- [x] **Phase 1**: ROI selection + settings persistence
- [x] **Phase 2**: 10×15 Grid + Cell State + Template Matching (complete 1~9 templates)
- [x] **Phase 3**: Rectangle Solver (pure algorithm, consumes BoardState only)
- [x] **Phase 4**: Hint Selector (min area + fixed scan order + same-digits dedupe, top N)
- [x] **Phase 5**: transparent click-through Overlay (border + start/end points + number badges)
- [x] **Phase 6**: frame-change detection (stability wait + Hint Lock + re-recognize when stable)
- [x] **Phase 7**: integration tests and UX fixes (incl. F8 global hotkey)

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/)

## Install & Run

**Quick start: double-click `run.bat`** (installs dependencies on first run; pauses with the error message on failure)

Or from the command line:

```powershell
uv sync
uv run python main.py
```

## Usage (goal: ready on launch, press F8 to work)

1. Open the StarSavior game (the window titled `StarSavior`), then open this tool
2. The tool auto-binds the game window and verifies the board position; if a previous selection exists it shows "Ready" right away
3. First run only: the main window shows just "**Select the Board Area to Start**" → drag a box around the 10 × 15 board over the live game frame
   (**Enter or double-click = confirm**, **Esc = cancel**;
   stored as a window-relative ratio, so moving the window or changing resolution needs no reselect); ready as soon as you confirm
4. Press "**Start Monitoring (F8)**" to work; `F8` = start/stop monitoring (master switch, hint flow only)
5. "**Hints**" (1~10, default 5): show the top-N hint groups at once;
   green No.1 is the primary move, No.2~N each get their own color + number badge;
   duplicate boxes around the same digits keep only the smallest one (the rest is just empty padding, clears the same); remembered
6. Everything rarely touched lives under "**Settings…**": ROI fine-tune / auto-align / preview, board matrix, always-on-top,
   language (中文 / English / 日本語 / 한국어; follows system by default, English fallback, applies instantly)

Capture pipeline: Windows background capture first (works covered), foreground fallback;
minimized game shows "waiting for game window", closing the game stops automatically.

## Phase 1 details (selection)

1. Click the guide button (or "Select Board Area" in Settings) → the main window hides and a fullscreen selector appears
2. Hold left mouse and **drag** roughly around the game's 10 × 15 number board (any direction; live X/Y/W/H readout)
3. On release it **auto-aligns** to the real board and shows a 10 × 15 grid for checking
   - Falls back to the raw selection if alignment fails
   - Press `A` to toggle auto-align on/off
4. **Enter or double-click = confirm**, **Esc = cancel**, **drag again = reselect**
5. Fine-tune with the X / Y / Width / Height fields in Settings; "**Auto Align**" re-aligns the current ROI from a live frame
6. ROI auto-saves to `settings.json` in the project root, loaded next launch
7. If the game window moved, the ROI auto-snaps to the new position at startup and saves
   (searches near the old position first, then fullscreen search + recognition check; keeps the old setting if all fail)
8. The Settings preview pane shows the selection with the 10 × 15 grid to verify alignment

## Phase 2 / 3

- The live 10×15 board matrix during monitoring is viewable in Settings (read-only)
- Rebuild digit templates: `uv run python tools/build_templates.py <screenshot> <labelsJSON>`
  (label format `{"row,col": digit}`; ROI defaults to `settings.json`)
- The Solver is the pure function `core/solver.py::find_rectangles(board)`;
  test it alone: `uv run pytest tests/test_solver.py`

## Phase 5

- When the board changes stably with no UNKNOWN, the top-N hints are computed and shown on the transparent Overlay
  (No.1 green box + green start + cyan end marking the suggested drag endpoints;
  No.2~N each in their own color + number badge, all shown at once)
- The Overlay takes no mouse and steals no focus; stopping monitoring (or F8) hides it
- The Overlay auto-hides before capture so box lines never pollute recognition

## Phase 6

- Press "**Start Monitoring**" (or F8): compares ROI frames every 300ms; re-recognizes only after 3 stable frames
  that differ from baseline (mid-animation frames are skipped); the Overlay updates only on real board changes
  (Hint Lock), otherwise keeps the current hints
- "**Stop Monitoring**": stops the loop and hides hints; changing ROI auto-stops first
- While monitoring, the status line shows `#tick stable run/3` progress and the latest event
  (hints updated / kept / UNKNOWN wait) — check this line first when stuck
- `debug/monitor.log` records every stable trigger, re-recognition result and overlay-residue retries;
  attach it when reporting issues
- `F8` = start/stop monitoring (master switch, hint flow only, never touches the game)

## Phase 7 notes

- `tests/test_integration.py`: builds synthetic boards from the repo's real templates,
  end-to-end ROI frame → recognition → Solver → Hint → Overlay geometry,
  plus the full monitor chain across board changes
- Change detection uses the "changed-pixel ratio" (not whole-frame average), so a 1~2-cell clear
  (~1% of ROI) still triggers; thresholds: `core/monitor.py::MonitorConfig`

## Tests

```powershell
uv run pytest
```

## CodeGraph (code index for maintenance)

```powershell
codegraph sync    # sync index after edits (incremental, fast)
codegraph index   # full rebuild when the index breaks or after big refactors
```

- The index lives in `.codegraph/` (SQLite), local-only, never committed; fresh clones run `codegraph init` once
- Ask via MCP `codegraph_explore` for day-to-day code questions: relevant symbols + call paths in one shot, no grep+Read loops

## Architecture

```
main.py                     # entry point (DPI awareness + QApplication)
core/
    roi_model.py            # Roi (absolute) + RoiFrac (window-relative ratio) + IoU
    settings_store.py       # settings JSON: window title / roi_frac / ui prefs (legacy roi auto-migrates)
    game_window.py          # target window binding (exact title + visible + largest) and client area
    window_capture.py       # WGC background capture session + one-shot grab (works covered)
    screen_capture.py       # mss foreground capture (fallback; selection bg, absolute-coord ROI)
    board_align.py          # 10×15 board auto-align (ROI Auto-Align)
    grid.py                 # ROI sliced into fixed 10×15 (CellGeometry with center)
    board_state.py          # BoardState + CellState (DIGIT/EMPTY/UNKNOWN split)
    templates.py            # TemplateStore: 1~9 template files (no matching)
    recognition.py          # DigitRecognizer: missing white tile → EMPTY; else template match
    board_builder.py        # ROI frame → slice → recognize → BoardState
    solver.py               # Rectangle Solver: pure algorithm, BoardState → all legal rectangles
    hint_selector.py        # Hint Selector: min area + fixed order + same-digits dedupe, top N
    monitor.py              # frame-stability tracking + Hint Lock (no GUI/capture)
    i18n.py                 # UI strings zh/en/ja/ko + system-language detection
gui/
    main_window.py          # main window (one status line + monitor toggle + hint count + first-run guide)
    settings_dialog.py      # settings dialog (ROI select/tune/preview, board matrix, topmost, language)
    roi_selector.py         # fullscreen selector (with auto-align; background can be a bg frame)
    recognition_panel.py    # 10×15 recognition matrix display
    hint_overlay.py         # transparent click-through Overlay (10-color borders + endpoints + badges, no mouse)
    global_hotkey.py        # F8 global hotkey (Win32 RegisterHotKey, master monitor switch)
    image_utils.py          # QImage ↔ numpy conversion
docs/
    adr/                    # architecture decision records (background capture, relative ROI…)
CONTEXT.md                  # project glossary (canonical terms + banned words, zh-TW)
templates/
    1.png ... 9.png         # digit templates captured from the real game (built by tools/build_templates.py)
tools/
    build_templates.py      # build/update templates from screenshot + labels JSON
tests/                      # pytest unit tests (incl. solver vs brute-force reference)
```

### Coordinate system

The whole pipeline uses **physical screen pixels**: `main.py` sets Per-Monitor DPI awareness and disables Qt High-DPI scaling (`QT_ENABLE_HIGHDPI_SCALING=0`) so Qt coordinates match capture coordinates, and the Overlay uses the same system. Settings store a **window-relative ratio** (`roi_frac`), converted to absolute coordinates from the live game client area at startup and every tick — moving the window or changing resolution needs no reselect.
