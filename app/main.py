"""
FoodCartOS API Entry Point

This is the main FastAPI application that powers FoodCartOS.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, carts, locations, orders, pages, quality, social, transactions, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    print(f"Starting FoodCartOS API v{settings.VERSION}")
    print(f"Environment: {settings.APP_ENV}")
    yield
    # Shutdown
    print("Shutting down FoodCartOS API")


app = FastAPI(
    title="FoodCartOS API",
    description="The Open-Source Operating System for Food Cart Entrepreneurs",
    version=settings.VERSION,
    lifespan=lifespan,
)

# Session middleware — must come before CORS
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    max_age=settings.SESSION_MAX_AGE,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# API routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(carts.router, prefix="/api/carts", tags=["Carts"])
app.include_router(locations.router, prefix="/api/locations", tags=["Locations"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(quality.router, prefix="/api/quality", tags=["Quality Checks"])
app.include_router(social.router, prefix="/api/social", tags=["Social Media"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])

# Page routes (HTML) — no prefix, serves at /login, /dashboard, etc.
app.include_router(pages.router, tags=["Pages"])


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.APP_ENV,
    }
