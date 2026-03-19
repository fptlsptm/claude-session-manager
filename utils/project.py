import os
import re


def normalize_path(project_path: str) -> str:
    """Git Bash 경로(/c/Users/...)를 Windows 경로(C:/Users/...)로 변환."""
    if not project_path:
        return project_path
    # /c/Users/... → C:/Users/...
    m = re.match(r"^/([a-zA-Z])/(.*)", project_path)
    if m:
        return f"{m.group(1).upper()}:/{m.group(2)}"
    return project_path


def extract_project_name(project_path: str) -> str:
    """경로에서 프로젝트명 추출. 빈 문자열이면 'unknown' 반환."""
    if not project_path:
        return "unknown"
    return os.path.basename(project_path.rstrip("/\\"))
