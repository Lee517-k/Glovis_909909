from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.yp_data import router as yp_data_router
from app.api.yp_upload import router as yp_upload_router
from app.api.YP_dashboard import router as yp_dashboard_router


app = FastAPI(
    title="Multimodal Logistics Agent API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(yp_data_router, prefix="/api")
app.include_router(yp_upload_router, prefix="/api")
app.include_router(yp_dashboard_router, prefix="/api")


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/api", tags=["system"])
def api_root() -> dict[str, str]:
    return {"message": "API modules will be added during feature development."}
