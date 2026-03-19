# Claude Session Manager — 기획서

## 개요

Claude Code 다중 세션을 윈도우 데스크탑에서 한눈에 모니터링하고 제어하는 Python 데스크탑 앱.  
Claude Code Hooks → 로컬 HTTP 서버 → PyQt 팝업 UI 구조로 동작한다.

---

## 기술 스택

| 항목 | 선택 |
|------|------|
| UI 프레임워크 | PyQt6 |
| 로컬 서버 | Flask (백그라운드 스레드) |
| 알림 | Windows 10/11 Toast (winotify) |
| 시스템 트레이 | PyQt6 QSystemTrayIcon |
| 빌드 (선택) | PyInstaller → .exe |

---

## 아키텍처

```
[Claude Code 세션 A] ──┐
[Claude Code 세션 B] ──┼──→ POST localhost:39393/hook ──→ Flask 서버
[Claude Code 세션 C] ──┘                                       │
                                                               ↓
                                                       세션 상태 저장 (메모리)
                                                               │
                                                               ↓
                                                      PyQt6 팝업 UI (갱신)
                                                               │
                                                               ↓
                                                    Windows Toast 알림 발생
```

---

## Claude Code Hook 설정

`~/.claude/settings.json` 에 글로벌 설정 (모든 프로젝트 공통 적용)

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "curl -s -X POST http://localhost:39393/hook -H \"Content-Type: application/json\" -d \"{\\\"event\\\":\\\"stop\\\",\\\"project\\\":\\\"$CLAUDE_PROJECT_DIR\\\",\\\"session\\\":\\\"$CLAUDE_SESSION_ID\\\"}\""
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "curl -s -X POST http://localhost:39393/hook -H \"Content-Type: application/json\" -d \"{\\\"event\\\":\\\"waiting\\\",\\\"project\\\":\\\"$CLAUDE_PROJECT_DIR\\\",\\\"session\\\":\\\"$CLAUDE_SESSION_ID\\\",\\\"message\\\":\\\"$CLAUDE_NOTIFICATION\\\"}\""
          }
        ]
      }
    ]
  }
}
```

### Hook 이벤트 종류

| 이벤트 | 발생 시점 | 의미 |
|--------|-----------|------|
| `Stop` | Claude가 작업을 멈춤 | 완료 또는 입력 대기 |
| `Notification` | Claude가 사용자 입력 요청 | Yes/No 응답 필요 |

---

## Flask 서버 (`server.py`)

### 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/hook` | Claude Code Hook 수신 |
| GET | `/sessions` | 현재 세션 목록 반환 |
| POST | `/session/<id>/dismiss` | 세션 알림 dismissed 처리 |

### 세션 데이터 구조

```python
session = {
    "id": "session_uuid",
    "project": "/path/to/project",       # $CLAUDE_PROJECT_DIR
    "project_name": "shorts-maker",       # 경로에서 추출한 프로젝트명
    "status": "waiting",                  # working | waiting | done
    "message": "계속 진행할까요?",         # 마지막 메시지 (있을 경우)
    "updated_at": "2026-03-20T12:00:00",
    "dismissed": False
}
```

### 상태 전이

```
working → waiting   (Notification hook 수신)
working → done      (Stop hook 수신)
waiting → dismissed (사용자가 팝업에서 확인)
done    → dismissed (사용자가 팝업에서 확인)
```

---

## PyQt6 UI

### 메인 팝업 창

- 항상 최상위 (`setWindowFlags(Qt.WindowStaysOnTopHint)`)
- 화면 우측 하단 고정 위치
- 창 크기: 가로 320px, 세로 자동 (세션 수에 따라 늘어남)
- 최소화 가능, X 버튼은 트레이로 숨김 (종료 아님)

### 세션 카드 (세션 1개당 1개 카드)

```
┌────────────────────────────────┐
│ 🟡 shorts-maker        대기중  │
│ "계속 진행할까요?"               │
│ [포커스]  [확인]                 │
├────────────────────────────────┤
│ ✅ simpler24           완료     │
│                                │
│ [포커스]  [확인]                 │
├────────────────────────────────┤
│ 🔄 lets-roll           작업중  │
│                                │
└────────────────────────────────┘
```

### 상태 아이콘

| 상태 | 아이콘 | 색상 |
|------|--------|------|
| working | 🔄 | 회색 |
| waiting | 🟡 | 노란색 |
| done | ✅ | 초록색 |

### 버튼 동작

| 버튼 | 동작 |
|------|------|
| 포커스 | 해당 프로젝트 경로를 VS Code로 열기 (`code 경로` 명령 실행) |
| 확인 | 세션 카드 dismissed 처리 후 목록에서 제거 |

### 시스템 트레이

- 앱 실행 시 트레이 아이콘 생성
- 우클릭 메뉴: "열기", "종료"
- `waiting` 또는 `done` 세션 발생 시 트레이 아이콘 깜빡임
- 팝업 창 닫으면 트레이로 숨김 (완전 종료 아님)

---

## Windows Toast 알림

`waiting` 또는 `done` 이벤트 수신 시 Toast 알림 발생

```
┌─────────────────────────────────┐
│ 🔔 Claude Session Manager       │
│ [shorts-maker] 입력 대기 중      │
│ "계속 진행할까요?"               │
└─────────────────────────────────┘
```

- 클릭 시 팝업 창 포커스
- `winotify` 라이브러리 사용

---

## 파일 구조

```
claude-session-manager/
├── main.py              # 진입점, PyQt 앱 실행
├── server.py            # Flask 서버 (백그라운드 스레드)
├── ui/
│   ├── main_window.py   # 메인 팝업 창
│   └── session_card.py  # 세션 카드 위젯
├── core/
│   ├── session_store.py # 세션 상태 관리 (메모리)
│   └── notifier.py      # Toast 알림
├── utils/
│   └── project.py       # 경로에서 프로젝트명 추출 등 유틸
├── requirements.txt
└── README.md
```

---

## requirements.txt

```
PyQt6>=6.6.0
Flask>=3.0.0
winotify>=1.1.0
```

---

## 실행 방법

```bash
# 가상환경 생성
python -m venv venv
venv\Scripts\activate   # Windows

# 패키지 설치
pip install -r requirements.txt

# 실행
python main.py
```

### 윈도우 시작 시 자동 실행 (선택)

`shell:startup` 폴더에 배치파일 추가:

```bat
@echo off
cd /d C:\경로\claude-session-manager
python main.py
```

---

## 구현 우선순위

| 단계 | 내용 |
|------|------|
| 1단계 | Flask 서버 + Hook 수신 + 세션 상태 저장 |
| 2단계 | PyQt6 기본 팝업 창 + 세션 카드 렌더링 |
| 3단계 | 버튼 동작 (포커스, 확인) |
| 4단계 | 시스템 트레이 + 자동 시작 |
| 5단계 | Windows Toast 알림 |
| 6단계 | .exe 빌드 (PyInstaller) |

---

## CLAUDE.md 참고사항

Claude Code로 구현 시 아래 순서로 진행 권장:

1. `server.py` 먼저 구현 후 `curl`로 Hook 수신 테스트
2. `session_store.py` 구현 후 상태 전이 단위 테스트
3. UI는 더미 데이터로 레이아웃 먼저 잡고 서버 연결
4. PyQt와 Flask는 별도 스레드 필수 (`threading.Thread` 사용)
5. PyQt UI 갱신은 반드시 메인 스레드에서 (`QMetaObject.invokeMethod` 또는 Signal 사용)
