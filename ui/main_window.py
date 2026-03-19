import ctypes
import ctypes.wintypes
import struct
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QSystemTrayIcon,
    QMenu, QApplication, QSizePolicy, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor, QAction


# --- Windows AppBar API ---
ABM_NEW = 0x00000000
ABM_REMOVE = 0x00000001
ABM_QUERYPOS = 0x00000002
ABM_SETPOS = 0x00000003
ABE_LEFT = 0

class APPBARDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("hWnd", ctypes.wintypes.HWND),
        ("uCallbackMessage", ctypes.c_uint),
        ("uEdge", ctypes.c_uint),
        ("rc", ctypes.wintypes.RECT),
        ("lParam", ctypes.c_long),
    ]

from ui.session_card import SessionCard
from core.session_store import SessionStore


def _create_tray_icon_pixmap(color: str = "#89b4fa") -> QPixmap:
    """단색 원형 트레이 아이콘 생성."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 56, 56)
    painter.end()
    return pixmap


GLOBAL_STYLE = """
QWidget {
    background: #181825;
    color: #cdd6f4;
    font-family: 'Segoe UI', sans-serif;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 4px 0;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 3px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #585b70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
"""


class MainWindow(QWidget):
    """메인 팝업 창 — 세션 카드 목록을 표시한다."""

    update_requested = pyqtSignal()

    def __init__(self, store: SessionStore):
        super().__init__()
        self.store = store
        self._tray_blink_state = False
        self._docked = False
        self._dock_width = 380
        self._undocked_geo = None
        self._appbar_registered = False
        self._setup_window()
        self._build_ui()
        self._setup_tray()

        self.update_requested.connect(self._refresh)

        # 주기적 갱신 (5초)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)

    def _setup_window(self):
        self.setWindowTitle("Claude Sessions")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(360, 250)
        self.resize(420, 520)

        # 화면 우측 하단 위치
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - 440, geo.bottom() - 540)

    def _build_ui(self):
        self.setStyleSheet(GLOBAL_STYLE)

        panel_layout = QVBoxLayout(self)
        panel_layout.setContentsMargins(16, 12, 16, 12)
        panel_layout.setSpacing(8)

        # 헤더 행
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        # 로고 아이콘
        logo = QLabel("C")
        logo.setFixedSize(28, 28)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFont(QFont("Consolas", 13, QFont.Weight.Bold))
        logo.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #89b4fa, stop:1 #b4befe);
            color: #1e1e2e;
            border-radius: 6px;
        """)

        title = QLabel("Claude Sessions")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4; background: transparent;")

        # 세션 카운트 뱃지
        self._count_badge = QLabel("0")
        self._count_badge.setFixedSize(24, 24)
        self._count_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_badge.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._count_badge.setStyleSheet("""
            background: #313244;
            color: #a6adc8;
            border-radius: 12px;
        """)

        # 도킹 토글 버튼
        self._dock_btn = QLabel("◧")
        self._dock_btn.setFixedSize(24, 24)
        self._dock_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dock_btn.setFont(QFont("Segoe UI", 12))
        self._dock_btn.setStyleSheet("color: #585b70; background: transparent;")
        self._dock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dock_btn.setToolTip("좌측 고정")
        self._dock_btn.mousePressEvent = lambda e: self.toggle_dock()

        header_row.addWidget(logo)
        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(self._count_badge)
        header_row.addWidget(self._dock_btn)
        panel_layout.addLayout(header_row)

        # 구분선
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background: #313244;")
        panel_layout.addWidget(separator)

        # 스크롤 영역
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent;")

        self._card_container = QWidget()
        self._card_container.setStyleSheet("background: transparent;")
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 4, 0, 4)
        self._card_layout.setSpacing(8)
        self._card_layout.addStretch()

        self._scroll.setWidget(self._card_container)
        panel_layout.addWidget(self._scroll)

        # 빈 상태
        self._empty_widget = QWidget()
        self._empty_widget.setStyleSheet("background: transparent;")
        empty_layout = QVBoxLayout(self._empty_widget)
        empty_layout.setContentsMargins(0, 40, 0, 40)

        empty_icon = QLabel("—")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setFont(QFont("Segoe UI", 24))
        empty_icon.setStyleSheet("color: #313244; background: transparent;")

        empty_text = QLabel("활성 세션 없음")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_text.setFont(QFont("Segoe UI", 11))
        empty_text.setStyleSheet("color: #585b70; background: transparent;")

        empty_sub = QLabel("Claude Code 세션이 시작되면 여기에 표시됩니다")
        empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_sub.setFont(QFont("Segoe UI", 9))
        empty_sub.setStyleSheet("color: #45475a; background: transparent;")

        empty_layout.addWidget(empty_icon)
        empty_layout.addWidget(empty_text)
        empty_layout.addWidget(empty_sub)

        panel_layout.addWidget(self._empty_widget)

        # 하단 상태바
        footer = QHBoxLayout()
        self._status_label = QLabel("Port 39393")
        self._status_label.setFont(QFont("Consolas", 8))
        self._status_label.setStyleSheet("color: #45475a; background: transparent;")

        self._status_dot = QLabel("●")
        self._status_dot.setFont(QFont("Segoe UI", 7))
        self._status_dot.setStyleSheet("color: #22c55e; background: transparent;")

        footer.addWidget(self._status_dot)
        footer.addWidget(self._status_label)
        footer.addStretch()
        panel_layout.addLayout(footer)

    def _setup_tray(self):
        self._tray_icon = QSystemTrayIcon(self)
        self._normal_icon = QIcon(_create_tray_icon_pixmap("#89b4fa"))
        self._alert_icon = QIcon(_create_tray_icon_pixmap("#f59e0b"))
        self._tray_icon.setIcon(self._normal_icon)
        self._tray_icon.setToolTip("Claude Session Manager")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #1e1e2e; color: #cdd6f4; border: 1px solid #313244;
                border-radius: 8px; padding: 4px;
            }
            QMenu::item { padding: 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background: #313244; }
        """)
        open_action = QAction("열기", self)
        open_action.triggered.connect(self._show_window)
        self._dock_action = QAction("좌측 고정", self)
        self._dock_action.triggered.connect(self.toggle_dock)
        quit_action = QAction("종료", self)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(open_action)
        menu.addAction(self._dock_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

        # 깜빡임 타이머
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_tray)
        self._blink_timer.setInterval(700)

    def _show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_window()

    def _blink_tray(self):
        self._tray_blink_state = not self._tray_blink_state
        if self._tray_blink_state:
            self._tray_icon.setIcon(self._alert_icon)
        else:
            self._tray_icon.setIcon(self._normal_icon)

    # --- 좌측 도킹 ---
    def toggle_dock(self):
        """좌측 고정 토글."""
        if self._docked:
            self._undock()
        else:
            self._dock()

    def _dock(self):
        """화면 좌측에 고정 (AppBar API로 다른 창들을 밀어냄)."""
        self._undocked_geo = self.geometry()
        screen = QApplication.primaryScreen()
        if not screen:
            return

        screen_geo = screen.geometry()
        avail_geo = screen.availableGeometry()
        w = self._dock_width

        # 프레임리스 + 항상 위
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setGeometry(avail_geo.left(), avail_geo.top(), w, avail_geo.height())
        self.show()

        # AppBar 등록 — 다른 창들이 이 영역을 피함
        try:
            hwnd = int(self.winId())
            abd = APPBARDATA()
            abd.cbSize = ctypes.sizeof(APPBARDATA)
            abd.hWnd = hwnd
            abd.uEdge = ABE_LEFT
            abd.rc.left = avail_geo.left()
            abd.rc.top = avail_geo.top()
            abd.rc.right = avail_geo.left() + w
            abd.rc.bottom = avail_geo.bottom()

            ctypes.windll.shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(abd))
            ctypes.windll.shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(abd))
            abd.rc.right = abd.rc.left + w
            ctypes.windll.shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(abd))

            # AppBar가 결정한 위치로 윈도우 이동
            self.setGeometry(abd.rc.left, abd.rc.top,
                             abd.rc.right - abd.rc.left,
                             abd.rc.bottom - abd.rc.top)
            self._appbar_registered = True
        except Exception:
            self._appbar_registered = False

        self._docked = True
        self._dock_btn.setText("◨")
        self._dock_btn.setToolTip("고정 해제")
        self._dock_btn.setStyleSheet("color: #89b4fa; background: transparent;")
        self._dock_action.setText("고정 해제")

    def _undock(self):
        """고정 해제 — AppBar 제거로 작업 영역 자동 복원."""
        # AppBar 제거
        if getattr(self, '_appbar_registered', False):
            try:
                hwnd = int(self.winId())
                abd = APPBARDATA()
                abd.cbSize = ctypes.sizeof(APPBARDATA)
                abd.hWnd = hwnd
                ctypes.windll.shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(abd))
                self._appbar_registered = False
            except Exception:
                pass

        # 원래 윈도우 스타일 복원
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        if self._undocked_geo:
            self.setGeometry(self._undocked_geo)
        self.show()

        self._docked = False
        self._dock_btn.setText("◧")
        self._dock_btn.setToolTip("좌측 고정")
        self._dock_btn.setStyleSheet("color: #585b70; background: transparent;")
        self._dock_action.setText("좌측 고정")

    def closeEvent(self, event):
        """X 버튼 누르면 트레이로 숨김. 도킹 중이면 해제."""
        if self._docked:
            self._undock()
        event.ignore()
        self.hide()

    def _on_quit(self):
        """종료 시 도킹 해제 후 앱 종료."""
        if self._docked:
            self._undock()
        QApplication.quit()

    def request_update(self):
        """스레드 안전한 UI 갱신 요청 (Flask 스레드에서 호출)."""
        self.update_requested.emit()

    @pyqtSlot()
    def _refresh(self):
        """세션 목록을 다시 그린다."""
        sessions = self.store.get_all()

        # 기존 카드 제거
        while self._card_layout.count() > 1:  # stretch 아이템 유지
            item = self._card_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # 빈 상태 처리
        self._empty_widget.setVisible(len(sessions) == 0)
        self._scroll.setVisible(len(sessions) > 0)

        # 카운트 뱃지
        self._count_badge.setText(str(len(sessions)))
        if len(sessions) > 0:
            waiting = sum(1 for s in sessions if s["status"] == "waiting")
            if waiting > 0:
                self._count_badge.setStyleSheet("""
                    background: #f59e0b; color: #1e1e2e;
                    border-radius: 12px; font-weight: bold;
                """)
            else:
                self._count_badge.setStyleSheet("""
                    background: #313244; color: #a6adc8;
                    border-radius: 12px;
                """)
        else:
            self._count_badge.setStyleSheet("""
                background: #313244; color: #a6adc8;
                border-radius: 12px;
            """)

        # 카드 추가
        for session in sessions:
            card = SessionCard(session)
            card.dismissed.connect(self._on_dismiss)
            card.permission_responded.connect(lambda _: self._refresh())
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)

        # 트레이 깜빡임
        if self.store.has_active():
            if not self._blink_timer.isActive():
                self._blink_timer.start()
        else:
            self._blink_timer.stop()
            self._tray_icon.setIcon(self._normal_icon)

    @pyqtSlot(str)
    def _on_dismiss(self, session_id: str):
        self.store.dismiss(session_id)
        self._refresh()

