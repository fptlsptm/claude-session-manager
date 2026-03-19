import sys
import threading
from PyQt6.QtWidgets import QApplication
from core.session_store import SessionStore
from core.notifier import send_toast
from ui.main_window import MainWindow
import server


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 트레이에서 계속 실행

    # 공유 세션 저장소
    store = SessionStore()
    server.store = store

    # 메인 윈도우
    window = MainWindow(store)
    window.show()
    window._refresh()

    # Flask 서버에 UI 갱신 콜백 연결
    def on_hook_update():
        window.request_update()

    server.set_on_update(on_hook_update)

    # Flask 서버를 백그라운드 데몬 스레드로 실행
    server_thread = threading.Thread(
        target=server.run_server,
        daemon=True,
    )
    server_thread.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
