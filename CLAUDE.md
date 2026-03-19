# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

Claude Code 다중 세션을 모니터링하고 권한 요청을 원격 제어하는 Windows 데스크탑 앱.
Claude Code Hooks(http 타입) → Flask HTTP 서버(localhost:39393) → PyQt6 UI 구조.

## 기술 스택

- **UI**: PyQt6 (네이티브 윈도우 + AppBar 좌측 도킹, 시스템 트레이)
- **서버**: Flask (백그라운드 데몬 스레드, 다중 인코딩 JSON 디코딩)
- **알림**: winotify (Windows Toast)
- **Windows API**: AppBar(`SHAppBarMessage`) 도킹, `EnumWindows` 포커스/리사이즈
- **빌드**: PyInstaller → .exe (선택)

## 실행 방법

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 아키텍처

- `main.py` — 진입점. PyQt QApplication + Flask 서버 스레드 시작
- `server.py` — Flask 앱. `/hook` 엔드포인트로 Hook 이벤트 수신, 권한 요청 대기/응답, 활동 로그 기록
- `core/session_store.py` — 스레드 안전한 세션 저장소 (메모리, dict 기반, activities 리스트 포함)
- `core/notifier.py` — winotify를 이용한 Windows Toast 알림
- `ui/main_window.py` — 메인 창 + 시스템 트레이 + AppBar 좌측 도킹
- `ui/session_card.py` — 세션 카드 위젯 (상태, 활동 로그, 허용/거부, 포커스 버튼)
- `utils/project.py` — 경로 정규화(Git Bash→Windows) + 프로젝트명 추출 유틸

## Hook 설정 (`~/.claude/settings.json`)

**반드시 `http` 타입을 사용해야 함.** `command`(curl) 타입은 Windows에서 한글 경로 인코딩(CP949) 문제 발생.

`http` 타입은 Claude Code가 자체 JSON 포맷으로 직접 POST하므로:
- `session_id`, `cwd`, `hook_event_name`, `tool_name`, `tool_input` 등이 자동 포함됨
- body 필드 불필요 (Claude Code가 자체 데이터 전송)
- UTF-8 인코딩 보장

```json
{
  "hooks": {
    "PreToolUse": [{ "matcher": "", "hooks": [{ "type": "http", "url": "http://localhost:39393/hook", "async": true }] }],
    "Stop": [{ "matcher": "", "hooks": [{ "type": "http", "url": "http://localhost:39393/hook", "async": true }] }],
    "Notification": [{ "matcher": "", "hooks": [{ "type": "http", "url": "http://localhost:39393/hook", "async": true }] }],
    "PermissionRequest": [{ "matcher": "", "hooks": [{ "type": "http", "url": "http://localhost:39393/hook" }] }]
  }
}
```

**주의: `PermissionRequest`는 `async` 없음** — 동기로 동작해야 서버가 대시보드 응답을 기다린 후 허용/거부를 반환할 수 있음.

## 핵심 규칙

### Hook 이벤트 매핑

| hook_event_name | 세션 상태 | 의미 |
|---|---|---|
| `PreToolUse` | working | Claude가 도구 사용 중 (활동 로그에 기록) |
| `Stop` | done | Claude 응답 완료 |
| `Notification` | waiting | 사용자 알림 (VSCode에서는 미발생) |
| `PermissionRequest` | waiting | 권한 승인 대기 (허용/거부 버튼 표시) |

### 권한 원격 제어 흐름

1. `PermissionRequest` hook → Flask `/hook` (동기, 연결 유지)
2. 세션 상태 "waiting" + `permission_request_id` 저장
3. 대시보드 카드에 "허용"/"거부" 버튼 표시
4. 사용자 클릭 → `POST /permission/<id>/respond` → `{"decision": "allow"}` 또는 `{"decision": "deny"}`
5. Flask가 대기 중인 hook 요청에 `{"hookSpecificOutput": {"decision": {"behavior": "allow"}}}` 응답
6. Claude Code가 자동으로 허용/거부 처리
7. 타임아웃(120초) 시 자동 허용
8. **VS Code에서 직접 허용한 경우**: 다음 `PreToolUse` 수신 시 대기 중인 권한 요청 자동 해제

### 활동 로그

- `PreToolUse` 이벤트마다 `tool_name` + `tool_input` 요약을 세션별로 기록
- 최대 10개 유지, UI에서 최근 5개 표시
- 도구별 요약: Bash→command, Read/Edit/Write→파일명, Grep/Glob→pattern, Agent→description

### 좌측 도킹 (AppBar)

- Windows `SHAppBarMessage` API로 좌측 고정
- `ABM_NEW` → `ABM_QUERYPOS` → `ABM_SETPOS` 순서로 등록
- 다른 창들이 도킹 영역을 피해서 자동 재배치됨
- 해제 시 `ABM_REMOVE`로 작업 영역 자동 복원
- **`SPI_SETWORKAREA`는 기존 창을 밀지 못함** → 반드시 AppBar API 사용

### 포커스 기능

- `EnumWindows`로 프로젝트명이 포함된 VS Code 창을 찾음
- `MoveWindow`로 1600x1200 크기, 화면 정중앙 배치
- `SetForegroundWindow`로 포커스 전환

### 스레딩

- **PyQt + Flask 스레딩**: Flask는 `threading.Thread(daemon=True)`로 실행. UI 갱신은 반드시 `pyqtSignal`을 통해 메인 스레드에서 수행.
- **SessionStore는 스레드 안전**: 내부 `threading.Lock` 사용. Flask 스레드와 Qt 메인 스레드에서 동시 접근 가능.
- **권한 대기**: `threading.Event`로 Flask 요청 스레드를 블로킹. UI 스레드와 독립.

### Windows 경로 처리

- Claude Code Hook의 `cwd`는 Windows 경로(`c:\Users\...`)로 전달됨
- Git Bash 경로(`/c/Users/...`)가 올 수도 있으므로 `normalize_path()`로 변환
- **`command` 타입 curl은 한글 경로에서 CP949 인코딩 문제 발생** → 반드시 `http` 타입 사용

### JSON 인코딩 처리

- Flask의 `get_json()`은 UTF-8만 시도 → Windows curl의 CP949 한글이 깨짐
- 서버에서 UTF-8 → CP949 → EUC-KR 순으로 디코딩 시도하여 해결
- `http` 타입 hook은 UTF-8 보장이므로 이 문제 없음

### VSCode 확장 환경 제약

- `Notification` hook이 발생하지 않음 (CLI에서만 동작)
- `$CLAUDE_SESSION_ID` 환경변수가 비어있을 수 있음 → 프로젝트 경로 해시로 fallback ID 생성
- `PermissionRequest` hook은 정상 동작

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/hook` | Claude Code Hook 수신 (http 타입) |
| GET | `/sessions` | 현재 세션 목록 반환 |
| POST | `/session/<id>/dismiss` | 세션 dismissed 처리 |
| POST | `/permission/<id>/respond` | 권한 허용/거부 응답 |
| GET | `/permissions/pending` | 대기 중인 권한 요청 목록 |

## 테스트

```bash
# 세션 목록 확인
curl http://localhost:39393/sessions

# 대기 중인 권한 요청 확인
curl http://localhost:39393/permissions/pending
```
