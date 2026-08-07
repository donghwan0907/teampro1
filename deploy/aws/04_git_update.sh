#!/usr/bin/env bash
# 서버에서 최신 코드를 받아 바로 반영하는 스크립트.
#
# 사용법 (PuTTY로 서버 접속 후, 프로젝트 폴더 안에서):
#   bash deploy/aws/04_git_update.sh
#
# 하는 일:
#   1. git pull 로 최신 코드를 받아옵니다.
#   2. requirements.txt 변경사항을 venv에 설치합니다.
#   3. safelease 서비스를 재시작하고 정상 응답하는지 확인합니다.
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
cd "$APP_DIR"

echo "[1/2] git pull"
git pull

echo "[2/2] 의존성 설치 및 서비스 재시작"
bash "$SCRIPT_DIR/03_apply_update.sh"
