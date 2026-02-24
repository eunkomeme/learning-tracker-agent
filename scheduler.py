"""
뉴스레터 자동 스케줄러 데몬.

매일 지정한 시각에 newsletter.py를 자동 실행합니다.

시작:
    python scheduler.py &          # 백그라운드 실행
    nohup python scheduler.py &    # 터미널 닫아도 유지

종료:
    kill $(cat .scheduler.pid)
"""

import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 매일 실행할 시각 (24시간 기준, 환경변수로 덮어쓰기 가능)
RUN_HOUR = int(os.environ.get("NEWSLETTER_HOUR", "9"))
RUN_MINUTE = int(os.environ.get("NEWSLETTER_MINUTE", "0"))

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "newsletter.log"
PID_FILE = BASE_DIR / ".scheduler.pid"


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_newsletter():
    log("뉴스레터 처리 시작")
    try:
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "newsletter.py")],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
        )
        if result.stdout:
            log(result.stdout.strip())
        if result.returncode != 0 and result.stderr:
            log(f"오류: {result.stderr.strip()}")
    except Exception as e:
        log(f"실행 오류: {e}")
    log("뉴스레터 처리 완료")


def cleanup(signum, frame):
    log("스케줄러 종료")
    PID_FILE.unlink(missing_ok=True)
    sys.exit(0)


def main():
    # PID 파일 저장 (종료 시 사용)
    PID_FILE.write_text(str(os.getpid()))
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    log(f"스케줄러 시작 — 매일 {RUN_HOUR:02d}:{RUN_MINUTE:02d}에 실행")

    last_run_date = None

    while True:
        now = datetime.now()
        today = now.date()

        if (
            now.hour == RUN_HOUR
            and now.minute == RUN_MINUTE
            and last_run_date != today
        ):
            run_newsletter()
            last_run_date = today

        time.sleep(30)  # 30초마다 시각 확인


if __name__ == "__main__":
    main()
