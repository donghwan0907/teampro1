#!/usr/bin/env bash
set -Eeuo pipefail

echo "=== SafeLease 서비스 ==="
sudo systemctl status safelease --no-pager --full || true
echo
echo "=== 내부 상태 확인 ==="
curl -fsS http://127.0.0.1:8000/health && echo
echo
echo "=== 최근 로그 40줄 ==="
sudo journalctl -u safelease -n 40 --no-pager
