#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"

if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  echo "먼저 bash deploy/aws/01_install.sh 를 실행하세요." >&2
  exit 1
fi

"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
sudo systemctl restart safelease

for _ in {1..20}; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    echo "업데이트 적용과 재시작이 완료되었습니다."
    exit 0
  fi
  sleep 1
done

sudo journalctl -u safelease -n 80 --no-pager >&2
exit 1
