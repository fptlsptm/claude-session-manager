import subprocess
import urllib.request
import json
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor


STATUS_CONFIG = {
    "working": {
        "icon": "\u25cf", "label": "작업중", "color": "#6b7280",
        "bg": "#1e1e2e", "border": "#313244",
    },
    "waiting": {
        "icon": "\u25cf", "label": "대기중", "color": "#f59e0b",
        "bg": "#1e1e2e", "border": "#f59e0b",
    },
    "done": {
        "icon": "\u25cf", "label": "완료", "color": "#22c55e",
        "bg": "#1e1e2e", "border": "#22c55e",
    },
}

BTN_STYLE = """
    QPushButton {{
        background: {bg}; color: {fg}; border: {border};
        border-radius: 4px; padding: 3px 8px;
        font-size: 11px; font-weight: 600;
    }}
    QPushButton:hover {{ background: {hover}; }}
    QPushButton:pressed {{ background: {pressed}; }}
"""


class SessionCard(QFrame):
    """세션 1개를 표시하는 카드 위젯."""

    dismissed = pyqtSignal(str)
    permission_responded = pyqtSignal(str)
    auto_toggled = pyqtSignal(str)

    def __init__(self, session: dict, parent=None):
        super().__init__(parent)
        self.session_id = session["id"]
        self.project_path = session["project"]
        self.permission_request_id = session.get("permission_request_id", "")
        self._build_ui(session)

    def _build_ui(self, session: dict):
        cfg = STATUS_CONFIG.get(session["status"], STATUS_CONFIG["working"])
        status = session["status"]

        self.setStyleSheet(f"""
            SessionCard {{
                background: {cfg['bg']};
                border: 1px solid {cfg['border']}40;
                border-left: 3px solid {cfg['border']};
                border-radius: 8px;
            }}
        """)

        # 카드 그림자
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(5)

        # 상단: 상태 인디케이터 + 프로젝트명 + 상태 태그
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        # 상태 점 (pulse 느낌)
        dot = QLabel(cfg["icon"])
        dot.setFont(QFont("Segoe UI", 8))
        dot.setStyleSheet(f"color: {cfg['color']}; background: transparent;")

        name_label = QLabel(session["project_name"])
        name_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #cdd6f4; background: transparent;")

        # 상태 태그 (pill 형태)
        tag = QLabel(cfg['label'])
        tag.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag.setStyleSheet(f"""
            background: {cfg['color']}20;
            color: {cfg['color']};
            border-radius: 8px;
            padding: 2px 6px;
        """)

        # 오토모드 토글
        is_auto = session.get("auto_mode", False)
        auto_btn = QLabel("A")
        auto_btn.setFixedSize(20, 20)
        auto_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        auto_btn.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        if is_auto:
            auto_btn.setStyleSheet("color: #22c55e; background: #22c55e20; border-radius: 4px;")
            auto_btn.setToolTip("오토모드 ON")
        else:
            auto_btn.setStyleSheet("color: #585b70; background: transparent; border-radius: 4px;")
            auto_btn.setToolTip("오토모드 OFF")
        auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        auto_btn.mousePressEvent = lambda e: self._on_toggle_auto()

        # 닫기 버튼 (✕)
        close_btn = QLabel("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        close_btn.setFont(QFont("Segoe UI", 9))
        close_btn.setStyleSheet("color: #45475a; background: transparent;")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.mousePressEvent = lambda e: self._on_dismiss()

        top_row.addWidget(dot)
        top_row.addWidget(name_label)
        top_row.addStretch()
        top_row.addWidget(tag)
        top_row.addWidget(auto_btn)
        top_row.addWidget(close_btn)
        main_layout.addLayout(top_row)

        # 메시지
        if session.get("message"):
            msg_label = QLabel(session["message"])
            msg_label.setFont(QFont("Consolas", 9))
            msg_label.setStyleSheet("""
                color: #a6adc8; background: #181825;
                border-radius: 4px; padding: 6px 8px;
            """)
            msg_label.setWordWrap(True)
            main_layout.addWidget(msg_label)

        # 활동 로그
        activities = session.get("activities", [])
        if activities:
            TOOL_ICONS = {
                "Bash": "›", "Read": "R", "Edit": "E", "Write": "W",
                "Grep": "G", "Glob": "F", "Agent": "A",
            }
            # 최근 5개만 표시
            recent = activities[-5:]
            log_lines = []
            for act in recent:
                icon = TOOL_ICONS.get(act["tool"], "·")
                summary = act["summary"]
                if len(summary) > 50:
                    summary = summary[:47] + "..."
                log_lines.append(
                    f'<span style="color:#585b70">{act["time"]}</span> '
                    f'<span style="color:#89b4fa">{icon}</span> '
                    f'<span style="color:#a6adc8">{summary}</span>'
                )

            log_label = QLabel("<br>".join(log_lines))
            log_label.setTextFormat(Qt.TextFormat.RichText)
            log_label.setFont(QFont("Consolas", 8))
            log_label.setStyleSheet("""
                background: #11111b; border-radius: 4px;
                padding: 6px 8px; border: 1px solid #18182540;
            """)
            log_label.setWordWrap(True)
            main_layout.addWidget(log_label)

        # 버튼 행 (항상 표시)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()

        # 포커스 버튼 (항상)
        focus_btn = QPushButton("포커스")
        focus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        focus_btn.setStyleSheet(BTN_STYLE.format(
            bg="transparent", fg="#89b4fa", border="1px solid #89b4fa40",
            hover="#89b4fa15", pressed="#89b4fa25",
        ))
        focus_btn.clicked.connect(self._on_focus)
        btn_row.addWidget(focus_btn)

        if status == "waiting" and self.permission_request_id:
            # 권한 요청: 허용/거부
            allow_btn = QPushButton("허용")
            allow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            allow_btn.setStyleSheet(BTN_STYLE.format(
                bg="#22c55e", fg="#fff", border="none",
                hover="#16a34a", pressed="#15803d",
            ))
            allow_btn.clicked.connect(lambda: self._on_permission("allow"))

            deny_btn = QPushButton("거부")
            deny_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            deny_btn.setStyleSheet(BTN_STYLE.format(
                bg="#ef4444", fg="#fff", border="none",
                hover="#dc2626", pressed="#b91c1c",
            ))
            deny_btn.clicked.connect(lambda: self._on_permission("deny"))

            btn_row.addWidget(allow_btn)
            btn_row.addWidget(deny_btn)

        main_layout.addLayout(btn_row)

    def _on_permission(self, decision: str):
        """권한 허용/거부를 서버에 전달."""
        if not self.permission_request_id:
            return
        try:
            data = json.dumps({"decision": decision}).encode("utf-8")
            req = urllib.request.Request(
                f"http://localhost:39393/permission/{self.permission_request_id}/respond",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
        self.permission_responded.emit(self.session_id)

    def _on_toggle_auto(self):
        """세션별 오토모드 토글."""
        try:
            req = urllib.request.Request(
                f"http://localhost:39393/session/{self.session_id}/auto",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass
        self.auto_toggled.emit(self.session_id)

    def _on_focus(self):
        """VS Code로 해당 프로젝트 열기 + 창 1200x800 중앙 배치."""
        if not self.project_path:
            return
        subprocess.Popen(["code", self.project_path], shell=True)

        # VS Code 창을 찾아서 리사이즈 + 중앙 배치
        try:
            import ctypes
            import ctypes.wintypes
            import time
            from PyQt6.QtWidgets import QApplication

            time.sleep(0.5)

            project_name = self.project_path.replace("\\", "/").rstrip("/").split("/")[-1]
            target_hwnd = None

            def enum_cb(hwnd, _):
                nonlocal target_hwnd
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                        if "Visual Studio Code" in buf.value and project_name in buf.value:
                            target_hwnd = hwnd
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

            if target_hwnd:
                w, h = 1600, 1200
                screen = QApplication.primaryScreen()
                if screen:
                    geo = screen.availableGeometry()
                    x = geo.left() + (geo.width() - w) // 2
                    y = geo.top() + (geo.height() - h) // 2
                else:
                    x, y = 200, 100
                ctypes.windll.user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.MoveWindow(target_hwnd, x, y, w, h, True)
                ctypes.windll.user32.SetForegroundWindow(target_hwnd)
        except Exception:
            pass

    def _on_dismiss(self):
        """dismissed 시그널 발생."""
        self.dismissed.emit(self.session_id)
