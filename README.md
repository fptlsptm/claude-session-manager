# Claude Code 세션 관리자 (Claude Session Manager)

Claude Code 다중 세션을 모니터링하고 권한 요청을 원격 제어하는 Windows 데스크탑 애플리케이션입니다.

**GitHub**: https://github.com/fptlsptm/claude-session-manager

<img width="882" height="513" alt="image" src="https://github.com/user-attachments/assets/14c7b122-5ec9-4d49-80db-832a3c983805" />

## 주요 기능

### 1. 세션 모니터링
- **작업 상태 실시간 표시**: 작업중(working) / 대기중(waiting) / 완료(done) 상태를 카드 형태로 표시
- **프로젝트별 세션 관리**: 각 Claude Code 세션을 프로젝트명으로 구분
- **자동 세션 종료**: Claude Code 세션 종료 시 자동으로 대시보드에서 제거

### 2. 권한 원격 제어
- **동기 권한 처리**: `PermissionRequest` hook을 동기로 처리하여 대시보드에서 즉시 허용/거부 가능
- **타임아웃 보호**: 120초 이내에 응답이 없으면 자동으로 허용 처리
- **VS Code 직접 허용**: VS Code에서 직접 허용 시 대시보드 대기 상태 자동 해제

### 3. 활동 로그
- **도구 사용 이력 기록**: `PreToolUse` 이벤트마다 `tool_name`과 입력값 자동 기록
- **도구별 요약**: Bash 명령어, 파일 경로, 패턴 등을 간결하게 표시
- **최근 활동 표시**: 최근 5개 활동을 세션 카드에 표시

### 4. Windows 통합 기능
- **좌측 도킹 (AppBar)**: Windows `SHAppBarMessage` API로 화면 좌측에 고정, 다른 창 자동 밀림
- **VS Code 포커스**: 프로젝트명이 포함된 VS Code 창을 찾아 1600x1200 크기로 중앙 배치 후 포커스 전환
- **네이티브 Windows Snap**: 화면 분할 기능 지원

### 5. 시스템 알림
- **Windows Toast 알림**: 상태 변화(waiting/done) 시 자동으로 토스트 알림 표시
- **시스템 트레이**: 트레이 아이콘으로 최소화하여 백그라운드 실행
- **트레이 깜빡임**: 새로운 이벤트 발생 시 트레이 아이콘 깜빡임

## 기술 스택

| 계층 | 기술 |
|------|------|
| **UI** | PyQt6 (프레임리스 윈도우, 시스템 트레이, 드래그/리사이즈) |
| **서버** | Flask (백그라운드 데몬 스레드, 비동기 HTTP hook 처리) |
| **알림** | winotify (Windows Toast) |
| **Windows API** | AppBar, EnumWindows, MoveWindow, SetForegroundWindow |
| **빌드** | PyInstaller (선택사항) |

## 아키텍처

```
Claude Code (http hook)
    ↓
Flask 서버 (localhost:39393)
    ↓
SessionStore (스레드 안전)
    ↓
PyQt6 UI (시스템 트레이, 세션 카드, 버튼)
```

### 주요 파일

| 파일 | 역할 |
|------|------|
| `main.py` | 진입점. PyQt QApplication + Flask 백그라운드 서버 시작 |
| `server.py` | Flask 앱. Hook 이벤트 수신, 권한 요청 대기/응답 처리 |
| `core/session_store.py` | 스레드 안전한 세션 저장소 (메모리 기반) |
| `core/notifier.py` | Windows Toast 알림 |
| `ui/main_window.py` | PyQt6 메인 윈도우, 시스템 트레이, AppBar 도킹 |
| `ui/session_card.py` | 세션 카드 위젯 (상태, 활동 로그, 버튼) |
| `utils/project.py` | 경로 정규화 및 프로젝트명 추출 유틸 |

## 설치 및 실행

### 1. 환경 설정

```bash
# 프로젝트 디렉토리 이동
cd c:\Users\young\Desktop\프로젝트_vscode\클코대쉬보드

# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (Windows)
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 애플리케이션 실행

```bash
python main.py
```

애플리케이션이 시작되면:
1. PyQt6 윈도우가 열리고 화면 좌측에 고정됨 (AppBar)
2. Flask 서버가 백그라운드에서 `localhost:39393`으로 시작
3. 시스템 트레이에 아이콘이 표시됨

## Hook 설정

Claude Code 세션을 모니터링하려면 `~/.claude/settings.json`에 다음과 같이 설정해야 합니다.

### 필수: http 타입 사용

**반드시 `http` 타입을 사용해야 합니다.** `command` 타입(curl)은 Windows에서 한글 경로 CP949 인코딩 문제가 발생합니다.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "http",
            "url": "http://localhost:39393/hook",
            "async": true
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "http",
            "url": "http://localhost:39393/hook",
            "async": true
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "http",
            "url": "http://localhost:39393/hook",
            "async": true
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "http",
            "url": "http://localhost:39393/hook"
          }
        ]
      }
    ]
  }
}
```

### 주의사항

- **`PermissionRequest` 동기 처리**: `async` 필드가 없어야 합니다. 동기로 동작해야 서버가 대시보드 응답을 기다린 후 허용/거부를 반환할 수 있습니다.
- **다른 hook은 async**: `PreToolUse`, `Stop`, `Notification`은 `"async": true`로 설정하여 Claude Code 응답을 차단하지 않습니다.

## Hook 이벤트 매핑

서버에서 Hook 이벤트를 받으면 다음과 같이 처리됩니다.

| hook_event_name | 세션 상태 | 의미 |
|---|---|---|
| `PreToolUse` | working | Claude가 도구 사용 중, 활동 로그에 기록 |
| `Stop` | done | Claude 응답 완료 |
| `Notification` | waiting | 사용자 알림 |
| `PermissionRequest` | waiting | 권한 승인 대기 (허용/거부 버튼 표시) |

## 권한 원격 제어 흐름

### 기본 흐름

1. Claude Code에서 권한이 필요한 도구 사용 (예: Bash)
2. `PermissionRequest` hook → Flask `/hook` 엔드포인트 (동기, 연결 유지)
3. 서버에서 세션 상태를 "waiting"으로 설정, `permission_request_id` 저장
4. 대시보드 카드에 "허용" / "거부" 버튼 표시
5. 사용자가 버튼 클릭 → `POST /permission/<id>/respond` 요청
6. 서버에서 대기 중인 hook 응답에 결정값 포함하여 반환
7. Claude Code가 자동으로 도구 실행 허용/거부 처리
8. 세션 상태가 "working"으로 복원

### 타임아웃 및 자동 허용

- **120초 타임아웃**: 대시보드에서 응답이 없으면 자동으로 허용 처리
- **VS Code 직접 허용**: VS Code에서 직접 허용한 경우, 다음 `PreToolUse` 이벤트 수신 시 대시보드 대기 상태 자동 해제

## API 엔드포인트

서버는 `localhost:39393`에서 다음 엔드포인트를 제공합니다.

### POST /hook
Claude Code Hook 이벤트 수신 (http 타입)

**요청**:
```json
{
  "hook_event_name": "PreToolUse",
  "session_id": "abc123",
  "cwd": "c:\\Users\\project",
  "tool_name": "Bash",
  "tool_input": {"command": "ls -la"}
}
```

**응답**:
```json
{"ok": true}
```

### GET /sessions
현재 활성 세션 목록 반환

**응답**:
```json
[
  {
    "id": "abc123",
    "project": "c:\\Users\\project",
    "project_name": "my-project",
    "status": "working",
    "message": "",
    "updated_at": "2026-03-20T15:30:45",
    "dismissed": false,
    "permission_request_id": "",
    "activities": [
      {"tool": "Read", "summary": "main.py", "time": "15:30:40"}
    ]
  }
]
```

### POST /session/<id>/dismiss
세션 dismissed 처리 (UI에서 숨김)

**응답**:
```json
{"ok": true}
```

### POST /permission/<id>/respond
권한 허용/거부 응답

**요청**:
```json
{"decision": "allow"}
```
또는
```json
{"decision": "deny"}
```

**응답**:
```json
{"ok": true}
```

### GET /permissions/pending
대기 중인 권한 요청 ID 목록

**응답**:
```json
["perm-abc123", "perm-def456"]
```

## 테스트

### 서버 연결 확인

```bash
# 세션 목록 조회
curl http://localhost:39393/sessions

# 대기 중인 권한 요청 확인
curl http://localhost:39393/permissions/pending
```

### 테스트 Hook 발송 (선택사항)

Hook 이벤트를 수동으로 발송하여 테스트할 수 있습니다.

```bash
# PreToolUse 이벤트 테스트
curl -X POST http://localhost:39393/hook \
  -H "Content-Type: application/json" \
  -d '{
    "hook_event_name": "PreToolUse",
    "session_id": "test-session-1",
    "cwd": "c:\\Users\\test",
    "tool_name": "Bash",
    "tool_input": {"command": "echo test"}
  }'

# Stop 이벤트 테스트
curl -X POST http://localhost:39393/hook \
  -H "Content-Type: application/json" \
  -d '{
    "hook_event_name": "Stop",
    "session_id": "test-session-1",
    "cwd": "c:\\Users\\test",
    "last_assistant_message": "Task completed"
  }'
```

## 핵심 기술 포인트

### 스레딩 안전성

- **SessionStore**: 내부 `threading.Lock` 사용으로 Flask 서버 스레드와 PyQt 메인 스레드의 동시 접근 안전
- **권한 대기**: `threading.Event`로 Flask 요청 스레드를 블로킹하여 동기 권한 처리 구현
- **UI 갱신**: PyQt `pyqtSignal`을 통해 메인 스레드에서만 UI 업데이트

### Windows 경로 처리

- Claude Code Hook의 `cwd`는 Windows 경로(`c:\Users\...`) 또는 Git Bash 경로(`/c/Users/...`)로 전달될 수 있음
- `normalize_path()` 함수로 자동 변환
- **http 타입 hook은 UTF-8 보장**: `command` 타입 curl의 CP949 인코딩 문제 없음

### AppBar API (좌측 도킹)

Windows `SHAppBarMessage` API를 사용하여 화면 좌측에 고정:
1. `ABM_NEW`: AppBar 등록
2. `ABM_QUERYPOS`: 위치 쿼리
3. `ABM_SETPOS`: 위치 설정
4. 다른 창들이 자동으로 도킹 영역을 피함

### VS Code 포커스

- `EnumWindows`로 프로젝트명이 포함된 VS Code 창 검색
- `MoveWindow`로 1600x1200 크기, 화면 정중앙 배치
- `SetForegroundWindow`로 포커스 전환

## 트러블슈팅

### Hook 연결이 안 됨
- `localhost:39393`에 접근 가능한지 확인: `curl http://localhost:39393/sessions`
- Claude Code의 `~/.claude/settings.json`에서 hook 설정 확인
- **반드시 `http` 타입 사용** - `command` 타입은 Windows 한글 경로에서 문제 발생

### 세션이 표시되지 않음
- Claude Code에서 Hook이 발동되지 않을 수 있음
- `hook_debug.log` 파일에서 수신된 Hook 데이터 확인
- VS Code 확장 환경에서는 일부 hook이 발동하지 않을 수 있음 (`Notification` hook 등)

### 권한 요청이 무한 대기
- 대시보드의 "허용" / "거부" 버튼을 클릭했는지 확인
- 120초 타임아웃이 지났다면 자동으로 허용됨
- VS Code에서 직접 "허용"하면 자동 해제됨

### 한글 경로 관련 문제
- **반드시 `http` 타입 hook 사용** - `command` 타입 curl은 CP949 인코딩 문제 발생
- 서버 로그(`hook_debug.log`)에서 `cwd` 경로가 올바르게 수신되었는지 확인

## 개발 및 빌드

### PyInstaller로 .exe 빌드 (선택)

```bash
# PyInstaller 설치
pip install pyinstaller

# .exe 빌드
pyinstaller --onefile --windowed --name "ClaudeCodeDashboard" main.py
```

빌드 결과는 `dist/main.exe`에 생성됩니다.

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여

버그 리포트, 기능 제안, 풀 리퀘스트는 [GitHub 저장소](https://github.com/fptlsptm/claude-session-manager)에서 환영합니다.
