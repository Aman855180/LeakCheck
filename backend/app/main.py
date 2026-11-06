from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.deps import verify_csrf_token
from app.api.v1 import api_router

app = FastAPI(
    title="LeakCheck API",
    description="Intelligent Payment Reconciliation and Financial Leakage Detection Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def csrf_protect_middleware(request: Request, call_next):
    # Verify CSRF on state-changing requests
    try:
        verify_csrf_token(request)
    except Exception as e:
        status_code = getattr(e, "status_code", 403)
        detail = getattr(e, "detail", "CSRF verification failed")
        return JSONResponse(status_code=status_code, content={"detail": detail})
    
    response = await call_next(request)
    return response


app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "app": "LeakCheck API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "operational"
    }
