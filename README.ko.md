# Star Savior 10 제거 도우미

![platform](https://img.shields.io/badge/platform-Windows-blue)
![python](https://img.shields.io/badge/python-3.13-blue)
![release](https://img.shields.io/github/v/release/Sid-1996/starsavior-make10-helper)
![downloads](https://img.shields.io/github/downloads/Sid-1996/starsavior-make10-helper/total)
![stars](https://img.shields.io/github/stars/Sid-1996/starsavior-make10-helper)
![license](https://img.shields.io/github/license/Sid-1996/starsavior-make10-helper)

[繁體中文](README.md) | [English](README.en.md) | [日本語](README.ja.md) | 한국어

"숫자 10 제거 게임"의 시각 보조 도우미. **화면을 분석して 힌트만 보여주고, 게임을 조작하지 않습니다**. 마우스 조작은 전부 사용자가 합니다.

## 다운로드(Windows 무설치 포터블)

[**Releases**](../../releases)에서 `StarSaviorHelper.exe`를 받아 더블클릭으로 실행:
설치 불필요. `settings.json`과 로그는 exe 옆에 남으므로, exe를 지우면 깨끗이 제거됩니다.

## 동작 화면

**초반**: 가득 찬 보드에 상위 N개 컬러＋번호 힌트를 한 번에 표시. 초록 1번을 따라 하세요:

![초반 힌트](docs/images/demo-early.webp)

**중반**: 제거 후 빈칸은 통과 가능. 힌트는 새 보드를 자동 추적:

![중반 힌트](docs/images/demo-mid.webp)

**후반**: 숫자가 듬성듬성 남아도 정확히 위치를 짚어줍니다:

![후반 힌트](docs/images/demo-late.webp)

## 특징

- **열면 준비, F8로 시작**: 게임 창 자동 바인딩＋보드 위치 기억. 창 이동/해상도 변경에도 재선택 불필요
- **연속 자동 감지**: 화면 변화 → 안정 대기 → 재인식 → 힌트 업데이트(제거 애니메이션 자동 스킵)
- **컬러＋번호 힌트**: 상위 N개에 각기 다른 색＋번호 배지. 겹쳐도 구분 가능. 같은 숫자 그룹의 중복 박스는 최소 박스만 유지
- **백그라운드 캡처**: 다른 창에 가려져도 동작. 최소화 시 자동 대기, 게임 종료 시 자동 중지
- **미니멀 메인 창**: 상태 한 줄＋스위치 하나＋힌트 수. 나머지는 "설정…"에 수납
- **4개 언어 UI**: 繁體中文／English／日本語／한국어. 시스템 언어를 따르고(해당 없음→영어), 전환 즉시 적용

## 개발 진행 상황

- [x] **Phase 1**: ROI 선택＋설정 저장
- [x] **Phase 2**: 10×15 Grid＋Cell State＋Template Matching(1~9 템플릿 완비)
- [x] **Phase 3**: Rectangle Solver(순수 알고리즘, BoardState만 입력)
- [x] **Phase 4**: Hint Selector(최소 area＋고정 스캔 순서＋같은 숫자 그룹 중복 제거, 상위 N개)
- [x] **Phase 5**: 투명 클릭스루 Overlay(테두리＋시작/종료점＋번호 배지)
- [x] **Phase 6**: 화면 변화 감지(안정 대기＋Hint Lock＋안정 후 재인식)
- [x] **Phase 7**: 통합 테스트와 UX 수정(F8 전역 단축키 포함)

## 환경 요구 사항

- Python 3.13
- [uv](https://docs.astral.sh/uv/)

## 설치 및 실행

**빠른 시작: `run.bat` 더블클릭**(최초 실행 시 의존성 자동 설치. 실패 시 메시지 표시 후 일시 정지)

명령줄 사용:

```powershell
uv sync
uv run python main.py
```

## 사용법(목표: 열면 준비, F8로 시작)

1. StarSavior 게임(`StarSavior` 제목의 창)을 먼저 열고 본 도구를 여세요
2. 게임 창을 자동 바인딩＋보드 위치 검증. 이전 선택이 있으면 바로 "준비 완료"
3. 최초 1회만: 메인 창에 "**보드 영역을 선택하여 시작**"만 표시 → live 게임 화면에서 10 × 15 보드를 드래그로 지정
   (**Enter 또는 더블클릭＝확인**, **Esc＝취소**.
   창 상대 비율로 저장하므로 창 이동/해상도 변경에도 재선택 불필요). 확인하면 준비 완료
4. "**모니터링 시작 (F8)**"으로 시작. `F8`＝모니터링 시작/중지(마스터 스위치, 힌트 처리만)
5. "**힌트 수**"(1~10, 기본 5): 상위 N개 힌트 그룹을 한 번에 표시.
   초록 1번이 본 힌트, 2~N번은 각기 다른 색＋번호 배지. 같은 숫자 그룹의 중복 사각형은 최소 박스만 유지
   (나머지는 빈칸 여백이라 제거 결과 동일). 설정 기억
6. 평소에 안 만지는 것은 전부 "**설정…**"에: ROI 미세 조정/자동 조정/미리보기, 보드 표시, 항상 위,
   언어(繁中／English／日本語／한국어. 기본은 시스템 언어, 해당 없음→영어, 전환 즉시 적용)

캡처 파이프라인: Windows 백그라운드 캡처 우선(가려져도 동작), 불가 시 포그라운드로 대체.
최소화 시 "게임 창 대기" 표시, 게임 종료 시 자동 중지.

## Phase 1 상세(선택 조작)

1. 가이드 버튼(또는 설정의 "**보드 영역 선택**") → 메인 창이 숨고 전체 화면 선택기가 나타남
2. 왼쪽 버튼을 누른 채 게임의 10 × 15 숫자 보드를 **드래그**로 대략 지정(모든 방향 가능, X/Y/W/H 실시간 표시)
3. 놓으면 실제 보드 위치로 **자동 조정**되고 10 × 15 격자로 확인 표시
   - 조정 실패 시 원래 선택 그대로 사용
   - `A`로 자동 조정 온/오프 전환
4. **Enter 또는 더블클릭＝확인**, **Esc＝취소**, **다시 드래그＝재선택**
5. 설정 대화상자의 X／Y／Width／Height 입력란으로 수동 미세 조정 가능. "**자동 조정**"으로 live 화면에서 현재 ROI 재조정
6. ROI는 프로젝트 루트의 `settings.json`에 자동 저장, 다음 시작 시 로드
7. 게임 창이 이동했으면 시작 시 새 위치로 자동 흡착 후 저장
   (먼저 기존 위치 근처 탐색, 다음 전체 화면 탐색＋인식 검증. 모두 실패 시에만 기존 설정 유지)
8. 설정 대화상자의 미리보기에서 선택 결과＋10 × 15 격자를 확인하여 조정 검증

## Phase 2／3

- 모니터링 중 live 10×15 보드는 설정 대화상자에서 확인 가능(읽기 전용)
- 숫자 템플릿 재구축: `uv run python tools/build_templates.py <스크린샷> <어노테이션JSON>`
  (어노테이션 형식 `{"row,col": digit}`. ROI는 기본적으로 `settings.json`을 읽음)
- Solver는 순수 함수 `core/solver.py::find_rectangles(board)`.
  단독 테스트: `uv run pytest tests/test_solver.py`

## Phase 5

- 보드가 안정적으로 변하고 UNKNOWN이 없으면 상위 N개 힌트를 자동 계산하여 투명 Overlay에 표시
  (1번: 초록 박스＋초록 시작점＋청록 종료점＝권장 드래그 시작/종료 칸 중심.
  2~N번: 각기 다른 색＋번호 배지, 한 번에 전체 표시)
- Overlay는 마우스를 받지 않고 포커스도 뺏지 않음. 모니터링 중지(또는 F8) 시 숨김
- 캡처 전 Overlay를 자동 숨기므로 박스 선이 인식을 오염시키지 않음

## Phase 6

- "**모니터링 시작**"(또는 F8): 300ms마다 ROI 프레임 비교. 기준과 다른 안정 프레임이 3연속이면 재인식
  (애니메이션 중간 프레임은 스킵). 실제 보드 변화 때만 Overlay 업데이트
  (Hint Lock), 그 외에는 현재 힌트 유지
- "**모니터링 중지**": 루프 중지＋힌트 숨김. ROI 변경 시 자동으로 먼저 중지
- 모니터링 중 상태 줄에 `#tick 안정 run/3` 진행 상황과 최근 이벤트 표시
  (힌트 업데이트/유지/UNKNOWN 대기). 막히면 먼저 이 줄 확인
- `debug/monitor.log`에 안정 트리거마다 재인식 결과와 Overlay 잔상 재시도 기록.
  문제 보고 시 이 로그 첨부
- `F8`＝모니터링 시작/중지(마스터 스위치, 힌트 처리만, 게임에 간섭 없음)

## Phase 7 참고

- `tests/test_integration.py`: 리포지토리 내 실제 템플릿으로 합성 보드를 만들고,
  ROI 화면 → 인식 → Solver → Hint → Overlay 기하까지 end-to-end 검증,
  보드 변화를 가로지르는 monitor 전체 체인도 검증
- 변화 감지는 "변화 픽셀 비율"(전체 화면 평균 아님)을 쓰므로 1~2칸 제거
  (전체 ROI의 약 1%)에도 발화. 임계값은 `core/monitor.py::MonitorConfig`

## 테스트

```powershell
uv run pytest
```

## CodeGraph(유지보수용 코드 인덱스)

```powershell
codegraph sync    # 수정 후 인덱스 동기화(증분, 빠름)
codegraph index   # 인덱스 손상 시나 대규모 리팩터 후 전체 재구축
```

- 인덱스는 `.codegraph/`(SQLite), 로컬 전용, git 제외. 새로 clone하면 `codegraph init` 1회
- 일상 코드 질문은 MCP `codegraph_explore`로: 관련 심볼 원문＋호출 체인을 한 번에, grep＋Read 순회 불필요

## 아키텍처

```
main.py                     # 진입점(DPI awareness＋QApplication)
core/
    roi_model.py            # Roi(절대)＋RoiFrac(창 상대 비율)＋IoU
    settings_store.py       # 설정 JSON: 창 제목／roi_frac／ui 설정(구 roi 자동 마이그레이션)
    game_window.py          # 대상 창 바인딩(정확한 제목＋가시＋최대)과 클라이언트 영역
    window_capture.py       # WGC 백그라운드 캡처 세션＋단발 캡처(가려져도 동작)
    screen_capture.py       # mss 포그라운드 캡처(대체용. 선택 배경, 절대 좌표 ROI)
    board_align.py          # 10×15 보드 자동 조정(ROI Auto-Align)
    grid.py                 # ROI를 10×15 고정 분할(CellGeometry는 center 포함)
    board_state.py          # BoardState＋CellState(DIGIT／EMPTY／UNKNOWN 3상태 분리)
    templates.py            # TemplateStore: 1~9 템플릿 읽기쓰기(매칭은 안 함)
    recognition.py          # DigitRecognizer: 흰 타일 부재 → EMPTY, 그 외 템플릿 매칭
    board_builder.py        # ROI 화면 → 분할 → 인식 → BoardState
    solver.py               # Rectangle Solver: 순수 알고리즘, BoardState → 전체 유효 사각형
    hint_selector.py        # Hint Selector: 최소 area＋고정 순서＋같은 숫자 그룹 중복 제거, 상위 N개
    monitor.py              # 프레임 안정 추적＋Hint Lock(GUI／캡처에 간섭 없음)
    i18n.py                 # UI 문자열 zh／en／ja／ko＋시스템 언어 감지
gui/
    main_window.py          # 메인 창(상태 한 줄＋모니터링 스위치＋힌트 수＋최초 가이드)
    settings_dialog.py      # 설정 대화상자(ROI 선택/미세 조정/미리보기, 보드 표시, 항상 위, 언어)
    roi_selector.py         # 전체 화면 선택기(자동 조정 포함. 배경은 백그라운드 프레임 가능)
    recognition_panel.py    # 10×15 인식 결과 표시
    hint_overlay.py         # 투명 클릭스루 Overlay(10색 테두리＋시작/종료점＋번호 배지, 마우스 간섭 없음)
    global_hotkey.py        # F8 전역 단축키(Win32 RegisterHotKey, 모니터링 마스터 스위치)
    image_utils.py          # QImage ↔ numpy 변환
docs/
    adr/                    # 아키텍처 결정 기록(백그라운드 캡처, 상대 ROI…)
CONTEXT.md                  # 프로젝트 용어집(표준 용어＋금지어, 번체 중국어)
templates/
    1.png ... 9.png         # 실제 게임 화면에서 취득한 숫자 템플릿(tools/build_templates.py로 생성)
tools/
    build_templates.py      # 스크린샷＋어노테이션 JSON에서 템플릿 생성/업데이트
tests/                      # pytest 단위 테스트(solver와 brute-force 참조 구현 대조 포함)
```

### 좌표계

파이프라인 전체에서 **물리 스크린 픽셀** 사용: `main.py`에서 Per-Monitor DPI awareness를 설정하고 Qt High-DPI 스케일링을 비활성화(`QT_ENABLE_HIGHDPI_SCALING=0`)하므로 Qt 좌표와 캡처 좌표가 일치하고 Overlay도 같은 좌표계. 설정 파일에는 **창 상대 비율**(`roi_frac`)을 저장하고 시작 시와 매 tick에 live 게임 클라이언트 영역에서 절대 좌표로 환산하므로 창 이동/해상도 변경에도 재선택 불필요.
