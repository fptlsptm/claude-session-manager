import threading
from datetime import datetime


class SessionStore:
    """세션 상태를 메모리에 저장하고 관리한다."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}
        self._lock = threading.Lock()

    def add_activity(self, session_id: str, tool_name: str, summary: str):
        """도구 사용 내역 추가 (최대 10개 유지)."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                ts = datetime.now().strftime("%H:%M:%S")
                session["activities"].append({
                    "tool": tool_name, "summary": summary, "time": ts
                })
                session["activities"] = session["activities"][-10:]

    def update(self, session_id: str, project: str, project_name: str,
               status: str, message: str = "",
               permission_request_id: str = "") -> dict:
        """세션 생성 또는 갱신. 갱신된 세션 dict 반환."""
        with self._lock:
            session = self._sessions.get(session_id, {
                "id": session_id,
                "project": project,
                "project_name": project_name,
                "status": "working",
                "message": "",
                "updated_at": "",
                "dismissed": False,
                "permission_request_id": "",
                "activities": [],
            })
            session["project"] = project
            session["project_name"] = project_name
            session["status"] = status
            if message:
                session["message"] = message
            session["permission_request_id"] = permission_request_id
            session["updated_at"] = datetime.now().isoformat(timespec="seconds")
            session["dismissed"] = False
            self._sessions[session_id] = session
            return dict(session)

    def dismiss(self, session_id: str) -> bool:
        """세션을 dismissed 처리. 성공 여부 반환."""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["dismissed"] = True
                return True
            return False

    def remove(self, session_id: str) -> bool:
        """세션 제거."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def get_all(self) -> list[dict]:
        """dismissed되지 않은 세션 목록 반환 (updated_at 내림차순)."""
        with self._lock:
            sessions = [
                dict(s) for s in self._sessions.values()
                if not s["dismissed"]
            ]
        sessions.sort(key=lambda s: s["updated_at"], reverse=True)
        return sessions

    def get_all_including_dismissed(self) -> list[dict]:
        """모든 세션 목록 반환."""
        with self._lock:
            return [dict(s) for s in self._sessions.values()]

    def has_active(self) -> bool:
        """waiting 또는 done 상태의 세션이 있는지 확인."""
        with self._lock:
            return any(
                s["status"] in ("waiting", "done") and not s["dismissed"]
                for s in self._sessions.values()
            )
