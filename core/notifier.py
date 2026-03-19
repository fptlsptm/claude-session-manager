from winotify import Notification, audio


APP_ID = "Claude Session Manager"


def send_toast(project_name: str, status: str, message: str = ""):
    """Windows Toast 알림을 발생시킨다."""
    if status == "waiting":
        title = f"[{project_name}] 입력 대기 중"
        body = message if message else "Claude가 사용자 입력을 기다리고 있습니다."
    elif status == "done":
        title = f"[{project_name}] 작업 완료"
        body = message if message else "Claude가 작업을 완료했습니다."
    else:
        return

    toast = Notification(
        app_id=APP_ID,
        title=title,
        msg=body,
        duration="short",
    )
    toast.set_audio(audio.Default, loop=False)
    toast.show()
