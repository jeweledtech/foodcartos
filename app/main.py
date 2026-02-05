"""
FoodCartOS API Entry Point

This is the main FastAPI application that powers FoodCartOS.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, carts, locations, quality, transactions, webhooks


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

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(carts.router, prefix="/api/carts", tags=["Carts"])
app.include_router(locations.router, prefix="/api/locations", tags=["Locations"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(quality.router, prefix="/api/quality", tags=["Quality Checks"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.APP_ENV,
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "FoodCartOS API",
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/health",
    }
