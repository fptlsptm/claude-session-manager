import hashlib
import json
import logging
import os
import threading
from flask import Flask, request, jsonify
from core.session_store import SessionStore
from utils.project import extract_project_name, normalize_path

log = logging.getLogger("werkzeug")
log.setLevel(logging.WARNING)

# 디버그 로그 파일
_log_path = os.path.join(os.path.dirname(__file__), "hook_debug.log")

app = Flask(__name__)
store = SessionStore()

# UI 갱신 콜백 — main.py에서 주입한다
_on_update_callback = None

# 대기 중인 권한 요청: {request_id: {"event": threading.Event, "decision": str}}
_pending_permissions: dict[str, dict] = {}
_perm_lock = threading.Lock()



def set_on_update(callback):
    global _on_update_callback
    _on_update_callback = callback


def _notify_update():
    if _on_update_callback:
        _on_update_callback()


@app.route("/hook", methods=["POST"])
def hook():
    data = request.get_json(silent=True)
    if not data:
        # UTF-8 JSON 파싱 실패 시 다른 인코딩 시도 (Windows CP949 등)
        raw = request.get_data()
        if raw:
            for encoding in ("utf-8", "cp949", "euc-kr"):
                try:
                    text = raw.decode(encoding)
                    data = json.loads(text)
                    break
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
    if not data:
        data = {}
    with open(_log_path, "a", encoding="utf-8") as f:
        f.write(f"[HOOK] {data}\n")

    # http 타입 hook: Claude Code가 자체 포맷으로 전송
    hook_event = data.get("hook_event_name", "")
    if hook_event:
        session_id = data.get("session_id", "")
        project = data.get("cwd", "")
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})
        if hook_event == "PermissionRequest":
            # 권한 요청: 도구명 + 입력 요약
            if tool_name == "Bash":
                message = f"[{tool_name}] {tool_input.get('command', '')[:80]}"
            elif tool_name in ("Edit", "Write"):
                message = f"[{tool_name}] {tool_input.get('file_path', '')}"
            else:
                message = f"[{tool_name}]"
        elif hook_event == "Stop":
            message = data.get("last_assistant_message", "")[:100]
        else:
            message = ""
    else:
        # 레거시: curl command 방식 fallback
        hook_event = data.get("event", "")
        session_id = data.get("session", "")
        project = data.get("project", "")
        message = data.get("message", "")

    # session_id가 비어있으면 프로젝트 경로 기반으로 생성
    if not session_id:
        if project:
            session_id = "auto-" + hashlib.md5(project.encode()).hexdigest()[:8]
        else:
            return jsonify({"error": "session or project required"}), 400

    project = normalize_path(project)
    project_name = extract_project_name(project)

    # hook_event_name 매핑
    event_map = {
        "PreToolUse": "working",
        "Stop": "done",
        "Notification": "waiting",
        "PermissionRequest": "waiting",
        # 레거시 매핑
        "started": "working",
        "stop": "waiting",
        "waiting": "waiting",
    }
    status = event_map.get(hook_event, "")

    if hook_event in ("ended", "SessionEnd"):
        store.remove(session_id)
        _notify_update()
        return jsonify({"ok": True})

    if not status:
        return jsonify({"error": f"unknown event: {hook_event}"}), 400

    permission_request_id = ""
    if hook_event == "PermissionRequest":
        permission_request_id = data.get("tool_use_id", "") or f"perm-{session_id}"

    # PreToolUse가 오면 = Claude가 작업 재개 → 대기 중인 권한 요청 자동 해제
    if hook_event == "PreToolUse":
        perm_key = f"perm-{session_id}"
        with _perm_lock:
            pending = _pending_permissions.get(perm_key)
            if pending:
                pending["decision"] = "allow"
                pending["event"].set()

    store.update(session_id, project, project_name, status, message,
                 permission_request_id=permission_request_id)

    # PreToolUse: 도구 사용 내역 기록
    if hook_event == "PreToolUse" and tool_name:
        if tool_name == "Bash":
            summary = tool_input.get("command", "")[:60]
        elif tool_name == "Read":
            summary = tool_input.get("file_path", "").split("/")[-1].split("\\")[-1]
        elif tool_name in ("Edit", "Write"):
            summary = tool_input.get("file_path", "").split("/")[-1].split("\\")[-1]
        elif tool_name == "Grep":
            summary = tool_input.get("pattern", "")[:40]
        elif tool_name == "Glob":
            summary = tool_input.get("pattern", "")[:40]
        elif tool_name == "Agent":
            summary = tool_input.get("description", "")[:40]
        else:
            summary = str(tool_input)[:40] if tool_input else ""
        store.add_activity(session_id, tool_name, summary)

    # waiting/done 이벤트 시 Toast 알림
    if status in ("waiting", "done"):
        try:
            from core.notifier import send_toast
            send_toast(project_name, status, message)
        except Exception:
            pass

    _notify_update()

    # PermissionRequest: 대시보드에서 허용/거부할 때까지 대기
    if hook_event == "PermissionRequest":
        request_id = permission_request_id

        # 오토모드: 즉시 허용
        if store.is_auto_mode(session_id):
            store.update(session_id, project, project_name, "working", "")
            _notify_update()
            return jsonify({
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "decision": {"behavior": "allow"}
                }
            })

        evt = threading.Event()
        with _perm_lock:
            _pending_permissions[request_id] = {"event": evt, "decision": "allow"}

        # 최대 120초 대기 (타임아웃 시 자동 허용)
        evt.wait(timeout=120)

        with _perm_lock:
            decision = _pending_permissions.pop(request_id, {}).get("decision", "allow")

        # 허용 후 상태를 working으로 복원
        store.update(session_id, project, project_name, "working", "")
        _notify_update()

        return jsonify({
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": decision}
            }
        })

    return jsonify({"ok": True})


@app.route("/sessions", methods=["GET"])
def sessions():
    return jsonify(store.get_all())


@app.route("/session/<session_id>/dismiss", methods=["POST"])
def dismiss(session_id):
    ok = store.dismiss(session_id)
    if ok:
        _notify_update()
    return jsonify({"ok": ok})


@app.route("/permission/<request_id>/respond", methods=["POST"])
def permission_respond(request_id):
    """대시보드에서 권한 허용/거부 응답."""
    data = request.get_json(silent=True) or {}
    decision = data.get("decision", "allow")  # "allow" or "deny"
    with _perm_lock:
        pending = _pending_permissions.get(request_id)
        if pending:
            pending["decision"] = decision
            pending["event"].set()
            return jsonify({"ok": True})
    return jsonify({"error": "not found"}), 404


@app.route("/session/<session_id>/auto", methods=["POST"])
def toggle_auto(session_id):
    """세션별 오토모드 토글."""
    result = store.toggle_auto_mode(session_id)
    _notify_update()
    return jsonify({"auto_mode": result})


@app.route("/permissions/pending", methods=["GET"])
def pending_permissions():
    """대기 중인 권한 요청 목록."""
    with _perm_lock:
        return jsonify(list(_pending_permissions.keys()))


def run_server(host="127.0.0.1", port=39393):
    app.run(host=host, port=port, threaded=True, use_reloader=False)
