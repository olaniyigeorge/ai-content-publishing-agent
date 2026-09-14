from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import intake, publishing, requests, reviews
from app.config import get_settings
from auth import endpoints as auth_endpoints
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
