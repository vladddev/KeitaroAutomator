from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, campaigns, editor, references
from app.config import get_settings
from app.services.keitaro_client import KeitaroError
from app.services.weights import WeightValidationError

settings = get_settings()

app = FastAPI(title="Keitaro API Wrapper", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(KeitaroError)
async def keitaro_error_handler(_: Request, exc: KeitaroError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(WeightValidationError)
async def weight_validation_error_handler(
    _: Request, exc: WeightValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(references.router)
app.include_router(campaigns.router)
app.include_router(editor.router)
