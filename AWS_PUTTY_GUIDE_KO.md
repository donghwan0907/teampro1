# AWS EC2 + PuTTY 배포 가이드

이 정리본은 **Ubuntu 22.04 또는 24.04 EC2**를 기준으로 합니다. Docker 없이 Python, systemd, Nginx로 실행하므로 이전 `docker-compose` 설치 오류가 발생하지 않습니다.

## 1. AWS 보안 그룹

EC2 인바운드 규칙을 다음처럼 설정합니다.

| 유형 | 포트 | 소스 |
|---|---:|---|
| SSH | 22 | 내 IP |
| HTTP | 80 | 0.0.0.0/0 |
| HTTPS | 443 | 0.0.0.0/0 (도메인과 SSL을 연결할 때) |

8000번 포트는 외부에 열지 않습니다. Nginx만 내부의 FastAPI 8000번 포트에 연결합니다.

## 2. ZIP을 서버로 전송

Windows에서 PuTTY와 함께 설치되는 `pscp.exe`를 이용합니다. CMD에서 ZIP이 있는 폴더로 이동한 뒤 실행합니다.

```bat
pscp -i "C:\키폴더\서버키.ppk" safelease_seoul_REGION_CHART_FINAL_20260806.zip ubuntu@공인IP:/home/ubuntu/
```

WinSCP를 사용한다면 ZIP을 `/home/ubuntu/`에 끌어다 놓아도 됩니다.

## 3. PuTTY에서 설치

PuTTY로 서버에 접속해 아래 명령을 순서대로 붙여넣습니다.

```bash
cd /home/ubuntu
sudo apt-get update
sudo apt-get install -y unzip
unzip safelease_seoul_REGION_CHART_FINAL_20260806.zip
cd safelease-seoul
chmod +x deploy/aws/*.sh
bash deploy/aws/01_install.sh
```

완료되면 화면에 `http://공인IP` 주소가 표시됩니다.

## 4. Supabase 연결

SQLite만 사용할 경우 이 단계는 건너뜁니다. Supabase를 사용하려면 다음 명령으로 서버 안의 환경설정을 엽니다.

```bash
cd /home/ubuntu/safelease-seoul
nano .env
```

다음 세 항목을 수정합니다. Secret key는 ZIP이나 소스코드에 넣지 않습니다.

```dotenv
PERSISTENCE_BACKEND=supabase
SUPABASE_URL=https://fuhgjatdqtmmdqsdameo.supabase.co
SUPABASE_SECRET_KEY=서버용_SECRET_KEY
```

저장은 `Ctrl+O`, Enter, 종료는 `Ctrl+X`입니다. Supabase SQL Editor에서 `sql/001_supabase_safelease.sql`도 한 번 실행한 뒤 서비스를 재시작합니다.

```bash
sudo systemctl restart safelease
bash deploy/aws/02_status.sh
```

## 5. 자주 쓰는 명령

```bash
# 상태와 최근 오류 확인
bash deploy/aws/02_status.sh

# 파일을 새 버전으로 덮어쓴 뒤 업데이트 적용
bash deploy/aws/03_apply_update.sh

# 직접 재시작
sudo systemctl restart safelease

# 실시간 로그 보기 (종료 Ctrl+C)
sudo journalctl -u safelease -f
```

## 6. 도메인과 HTTPS를 연결한 경우

인증서 적용이 끝난 뒤 `.env`의 값을 다음처럼 변경해야 로그인 쿠키가 HTTPS에서만 전달됩니다.

```dotenv
COOKIE_SECURE=true
```

변경 후 `sudo systemctl restart safelease`를 실행합니다.

## 7. Git으로 배포/업데이트하기 (pscp 대신)

로컬에서 GitHub에 push 해두면, 서버에서는 `git pull`만으로 최신 코드를 받을 수 있습니다.

### 최초 1회 (서버에 git으로 받아오기)

```bash
cd /home/ubuntu
git clone <내 GitHub 저장소 주소> safelease-seoul
cd safelease-seoul
cp .env.example .env
nano .env   # SUPABASE_URL, SUPABASE_SECRET_KEY 등 실제 값 채우기
chmod +x deploy/aws/*.sh
bash deploy/aws/01_install.sh
```

`01_install.sh`가 venv 생성, Nginx 연결, systemd 서비스 등록까지 한 번에 처리합니다.

### 이후 코드 수정 시

로컬(Windows)에서:

```powershell
git add .
git commit -m "수정 내용"
git push origin main
```

PuTTY로 서버에 접속해서:

```bash
cd /home/ubuntu/safelease-seoul
bash deploy/aws/04_git_update.sh
```

이 스크립트가 `git pull` → 의존성 재설치 → `systemctl restart safelease` → 헬스체크까지 자동으로 처리합니다.

> `.env`, `.venv`, `runtime/`, `__pycache__`는 `.gitignore`에 이미 포함되어 있어 git에 올라가지 않습니다. 서버의 `.env`는 최초 설치 때 한 번만 직접 채워두면, 이후 `git pull`을 아무리 반복해도 그대로 유지됩니다.
