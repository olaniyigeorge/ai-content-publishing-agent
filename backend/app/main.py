from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import adaptations, drafts, intake, publishing, requests, reviews, uploads, usage
from app.config import get_settings
from auth import endpoints as auth_endpoints
from db.client import get_supabase
from shared.errors import DomainError

settings = get_settings()

app = FastAPI(title="Koya Content Agent API", docs_url="/docs", openapi_url="/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    """Every domain error carries a message meant to be read directly — this
    is what makes API failures debuggable instead of a generic 500
    (EDGE_CASES.md #52)."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(auth_endpoints.router)
app.include_router(intake.router)
app.include_router(requests.router)
app.include_router(reviews.router)
app.include_router(publishing.router)
app.include_router(uploads.router)
app.include_router(drafts.router)
app.include_router(adaptations.router)
app.include_router(usage.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    """Unlike /health, this actually checks the dependency a load balancer or
    orchestrator would need to know is down before routing traffic here."""
    try:
        get_supabase().table("users").select("id").limit(1).execute()
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any failure means "not ready"
        return JSONResponse(status_code=503, content={"status": "not ready", "detail": str(exc)})
    return JSONResponse(status_code=200, content={"status": "ready"})
