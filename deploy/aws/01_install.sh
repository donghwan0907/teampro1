#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
APP_USER="${SUDO_USER:-$USER}"
APP_GROUP="$(id -gn "$APP_USER")"

echo "[1/7] Ubuntu 패키지를 설치합니다."
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-venv python3-pip nginx curl

echo "[2/7] Python 실행 환경을 준비합니다."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

echo "[3/7] 서버 환경설정을 준비합니다."
mkdir -p "$APP_DIR/runtime"
if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
fi
chmod 600 "$APP_DIR/.env"
sudo chown -R "$APP_USER:$APP_GROUP" "$APP_DIR/.venv" "$APP_DIR/runtime" "$APP_DIR/.env"

echo "[4/7] systemd 자동실행 서비스를 등록합니다."
SERVICE_TMP="$(mktemp)"
sed \
  -e "s|__APP_DIR__|$APP_DIR|g" \
  -e "s|__APP_USER__|$APP_USER|g" \
  -e "s|__APP_GROUP__|$APP_GROUP|g" \
  "$SCRIPT_DIR/systemd/safelease.service.template" > "$SERVICE_TMP"
sudo install -m 0644 "$SERVICE_TMP" /etc/systemd/system/safelease.service
rm -f "$SERVICE_TMP"

echo "[5/7] Nginx 웹서버를 연결합니다."
NGINX_TMP="$(mktemp)"
sed -e "s|__APP_DIR__|$APP_DIR|g" "$SCRIPT_DIR/nginx/safelease.conf.template" > "$NGINX_TMP"
sudo install -m 0644 "$NGINX_TMP" /etc/nginx/sites-available/safelease
rm -f "$NGINX_TMP"
sudo ln -sfn /etc/nginx/sites-available/safelease /etc/nginx/sites-enabled/safelease
if [[ -L /etc/nginx/sites-enabled/default ]]; then
  sudo unlink /etc/nginx/sites-enabled/default
fi
sudo nginx -t

echo "[6/7] 서비스를 시작합니다."
sudo systemctl daemon-reload
sudo systemctl enable --now safelease
sudo systemctl enable --now nginx
sudo systemctl reload nginx

echo "[7/7] 구동 상태를 확인합니다."
for _ in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    PUBLIC_IP="$(curl -fsS --max-time 3 https://checkip.amazonaws.com 2>/dev/null || hostname -I | awk '{print $1}')"
    echo
    echo "설치 완료: http://${PUBLIC_IP}"
    echo "상태 확인: bash deploy/aws/02_status.sh"
    exit 0
  fi
  sleep 1
done

echo "서비스가 제시간에 응답하지 않았습니다. 아래 로그를 확인합니다." >&2
sudo journalctl -u safelease -n 80 --no-pager >&2
exit 1
