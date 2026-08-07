# 세이프리스 서울 — 정리된 실행본

FastAPI와 pandas로 구동되는 서울 전세계약 안전지원 사이트입니다. Windows 로컬 실행과 AWS EC2 배포에 필요한 파일만 남겼습니다.

서울 참고지도에서 법정동을 누르면 핵심 수치만 팝업으로 확인할 수 있습니다. 팝업의 **전세 위험 근거 자세히 보기**를 누르면 `/region/{법정동코드}` 상세 페이지로 이동하며, 선택한 동과 가까운 주변 8개 동의 안전 참고점수를 하나의 세로막대그래프로 비교합니다. 기존 점수분포·히스토그램 차트는 제거했습니다.

## 폴더 구조

```text
safelease-seoul/
├─ app/                    FastAPI, 화면, CSS, JavaScript
├─ data/
│  ├─ processed/          화면과 차트가 실제로 읽는 CSV·JSON 4개
│  └─ geojson/            서울 법정동 지도 1개
├─ deploy/aws/             EC2 설치·상태확인·업데이트 스크립트
├─ sql/                    Supabase 테이블 생성 SQL
├─ .env.example            비밀키가 없는 환경설정 예시
├─ requirements.txt        실행 패키지 목록
├─ START_WINDOWS.cmd       Windows 로컬 실행
└─ AWS_PUTTY_GUIDE_KO.md   AWS 배포 순서
```

## Windows에서 실행

`START_WINDOWS.cmd`를 더블클릭합니다. 첫 실행 때만 Python 환경과 패키지를 설치합니다.

## AWS에서 실행

자세한 내용은 `AWS_PUTTY_GUIDE_KO.md`를 확인합니다. PuTTY에서 핵심 명령은 아래와 같습니다.

```bash
chmod +x deploy/aws/*.sh
bash deploy/aws/01_install.sh
```

설치 스크립트가 Python 가상환경, systemd 자동실행, Nginx 80번 포트 연결과 상태 확인을 한 번에 처리합니다.

## 저장소 선택

- `.env`가 없으면 `.env.example`을 복사해 생성합니다.
- Supabase Secret key가 비어 있으면 `runtime/safelease.db` SQLite를 사용합니다.
- Supabase를 사용하면 `.env`에 서버용 Secret key를 직접 입력하고 `sql/001_supabase_safelease.sql`을 실행합니다.
- `.env`, 가상환경, SQLite DB는 ZIP에 포함되지 않습니다.

## 정리하면서 제외한 항목

배포 구동에 쓰이지 않는 전처리 스크립트, 개발 테스트, 중복 Windows 실행파일, 원천·중간 CSV, 기본 지도 중복본, 개발 보고서, 생성된 DB와 캐시를 제외했습니다. 원본 프로젝트는 별도 폴더에 그대로 보존되어 있습니다.
