from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.db import PersistenceUnavailable, database_status, init_database
from app.routers import api, auth

APP_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app = FastAPI(title=settings.app_name, version="5.1.0-region-neighbor-chart", debug=settings.debug, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), check_dir=True), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.include_router(api.router, prefix="/api")
app.include_router(auth.router, prefix="/api")


@app.exception_handler(PersistenceUnavailable)
async def persistence_unavailable(_: Request, error: PersistenceUnavailable):
    return JSONResponse(
        status_code=503,
        content={"detail": str(error), "code": "PERSISTENCE_UNAVAILABLE"},
    )


@app.middleware("http")
async def prevent_stale_local_ui(request: Request, call_next):
    """로컬 실행 중 이전 CSS가 브라우저 캐시에 남지 않도록 한다."""
    response = await call_next(request)
    if request.url.path.startswith("/static/") or response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


def render(request: Request, template_name: str, **context):
    template_path = TEMPLATE_DIR / template_name
    if not template_path.exists():
        return HTMLResponse(
            content=(
                "<h1>서울 안심전세 AI 실행 오류</h1>"
                f"<p>템플릿을 찾지 못했습니다: <code>{template_path}</code></p>"
                "<p>ZIP을 완전히 압축 해제한 뒤 프로젝트 최상위 폴더에서 실행하세요.</p>"
            ),
            status_code=500,
        )
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={"app_name": settings.app_name, "ui_version": "20260806-hover-emphasis", **context},
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return render(request, "home.html", page_title="전세계약 안전 실행실", active_page="home")


@app.get("/map", response_class=HTMLResponse)
async def map_page(request: Request):
    return render(request, "index.html", page_title="서울 법정동 참고지도", active_page="map")


@app.get("/analysis", response_class=HTMLResponse)
async def analysis_page(request: Request):
    return render(request, "analysis.html", page_title="계약 안전진단", active_page="analysis")


@app.get("/contract", response_class=HTMLResponse)
async def contract_page(request: Request):
    return render(request, "contract.html", page_title="계약 실행 체크리스트", active_page="contract")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render(request, "login.html", page_title="체크리스트 로그인", active_page="login")


@app.get("/emergency", response_class=HTMLResponse)
async def emergency_page(request: Request):
    return render(request, "emergency.html", page_title="보증금 미반환 긴급대응", active_page="emergency")


@app.get("/methodology", response_class=HTMLResponse)
async def methodology_page(request: Request):
    return render(request, "methodology.html", page_title="서울 분석 기준", active_page="methodology")


@app.get("/support", response_class=HTMLResponse)
async def support_page(request: Request):
    return render(request, "support.html", page_title="서울 맞춤 지원", active_page="support")


@app.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    return render(request, "guide.html", page_title="계약 전 해결 가이드", active_page="guide")


@app.get("/region/{legal_dong_code}", response_class=HTMLResponse)
async def region_page(request: Request, legal_dong_code: str):
    return render(
        request,
        "region.html",
        page_title="법정동 상세 분석",
        active_page="map",
        legal_dong_code=legal_dong_code,
    )


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": app.version, "scope": "서울특별시 법정동"}


@app.get("/diagnostics")
def diagnostics():
    required_files = {
        "base_template": TEMPLATE_DIR / "base.html",
        "map_template": TEMPLATE_DIR / "index.html",
        "home_template": TEMPLATE_DIR / "home.html",
        "analysis_template": TEMPLATE_DIR / "analysis.html",
        "contract_template": TEMPLATE_DIR / "contract.html",
        "login_template": TEMPLATE_DIR / "login.html",
        "emergency_template": TEMPLATE_DIR / "emergency.html",
        "methodology_template": TEMPLATE_DIR / "methodology.html",
        "guide_template": TEMPLATE_DIR / "guide.html",
        "support_template": TEMPLATE_DIR / "support.html",
        "css": STATIC_DIR / "css" / "style.css",
        "map_js": STATIC_DIR / "js" / "map.js",
        "region_js": STATIC_DIR / "js" / "region.js",
        "analysis_js": STATIC_DIR / "js" / "analysis.js",
        "contract_js": STATIC_DIR / "js" / "contract.js",
        "auth_widget_js": STATIC_DIR / "js" / "auth-widget.js",
        "login_js": STATIC_DIR / "js" / "login.js",
        "support_js": STATIC_DIR / "js" / "support.js",
        "support_programs": APP_DIR / "data" / "support_programs.json",
        "guarantees": APP_DIR / "data" / "guarantee_products.json",
        "risk_csv": settings.processed_dir / "seoul_dong_risk_latest.csv",
        "official_csv": settings.processed_dir / "seoul_district_official_latest.csv",
        "legal_dong_geojson": settings.geojson_dir / "seoul_legal_dong_risk_web.geojson",
    }
    checks = {
        key: {"path": str(path), "exists": path.exists(), "size": path.stat().st_size if path.exists() else 0}
        for key, path in required_files.items()
    }
    return {
        "status": "ok" if all(item["exists"] for item in checks.values()) else "missing_files",
        "project_dir": str(settings.project_dir),
        "checks": checks,
        "database": database_status(),
    }
