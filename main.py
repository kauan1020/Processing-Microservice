#!/usr/bin/env python3
"""
FIAP X Video Processing Service - Main Application

This module configures and initializes the FastAPI application with all
necessary middleware, routers, exception handlers, and security configurations
for the video processing microservice with comprehensive API documentation.
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.openapi.utils import get_openapi
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infra.settings.settings import get_settings
from api.video_processing_router import router as video_processing_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager with startup and shutdown procedures.

    Manages the complete application lifecycle including service initialization,
    dependency setup, health monitoring initialization, and graceful shutdown
    procedures for the video processing microservice.
    """
    logger.info("🚀 Starting FIAP X Video Processing Service")

    settings = get_settings()
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Database: {settings.database.host}:{settings.database.port}")
    logger.info(f"Kafka: {settings.kafka.bootstrap_servers}")

    logger.info("✅ Application startup completed")

    yield

    logger.info("🛑 Shutting down FIAP X Video Processing Service")
    logger.info("✅ Application shutdown completed")


def custom_openapi():
    """
    Generate custom OpenAPI schema with JWT Bearer authentication.

    Creates a comprehensive OpenAPI schema that includes JWT Bearer token
    authentication configuration, security schemes, and applies appropriate
    security requirements to protected endpoints for API documentation.
    """

    def get_app_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        settings = get_settings()

        openapi_schema = get_openapi(
            title=settings.app_name,
            version=settings.app_version,
            description="FIAP X Video Processing Microservice for frame extraction from videos with job queue management",
            routes=app.routes,
        )

        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Digite apenas o token JWT (sem 'Bearer')"
            }
        }

        security_paths = [
            "/video-processing/jobs",
            "/video-processing/submit",
            "/video-processing/jobs/{job_id}/status",
            "/video-processing/jobs/{job_id}/download",
            "/video-processing/jobs/{job_id}",
            "/video-processing/jobs/{job_id}/frames",
            "/video-processing/jobs/{job_id}/cancel",
            "/video-processing/system/stats",
            "/video-processing/user/preferences"
        ]

        for path in openapi_schema["paths"]:
            for method in openapi_schema["paths"][path]:
                if method.lower() != "options":
                    if any(sec_path in path for sec_path in security_paths):
                        openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    return get_app_openapi


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application with comprehensive middleware.

    Initializes the FastAPI application instance with complete configuration
    including middleware setup, exception handlers, CORS policies, security
    configurations, and route registration for production deployment.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="FIAP X Video Processing Microservice for frame extraction from videos with distributed job processing",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.get_allowed_origins_list(),
        allow_credentials=settings.cors.allow_credentials,
        allow_methods=settings.cors.get_allowed_methods_list(),
        allow_headers=["*"],
        expose_headers=["X-Job-ID", "X-Frame-Count", "X-Processing-Duration", "X-Video-Duration"]
    )

    if not settings.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]
        )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """
        HTTP request logging middleware for monitoring and debugging.

        Logs all incoming HTTP requests with timing information, method,
        path, and response status codes while excluding health check
        endpoints to reduce log noise in production environments.
        """
        start_time = time.time()

        if request.url.path in ["/health", "/system/health"]:
            response = await call_next(request)
            return response

        logger.info(f"📥 {request.method} {request.url.path}")

        response = await call_next(request)

        process_time = time.time() - start_time
        logger.info(f"📤 {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)")

        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        HTTP exception handler with standardized JSON error responses.

        Handles all HTTP exceptions with consistent JSON response format
        including error type identification, status codes, and descriptive
        messages for proper client-side error handling and debugging.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "type": "http_error",
                    "message": exc.detail,
                    "status_code": exc.status_code
                },
                "timestamp": time.time()
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        Request validation error handler with detailed field-level information.

        Processes Pydantic validation errors and returns comprehensive
        error details including field names, validation rules, and input
        values to assist clients in correcting request parameters.
        """
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "type": "validation_error",
                    "message": "Request validation failed",
                    "details": exc.errors()
                },
                "timestamp": time.time()
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """
        General exception handler for unexpected errors with proper logging.

        Catches all unhandled exceptions, logs them with full stack traces
        for debugging purposes, and returns safe error responses without
        exposing internal implementation details to clients.
        """
        logger.error(f"Unexpected error: {str(exc)}", exc_info=True)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "type": "internal_server_error",
                    "message": "An unexpected error occurred",
                    "error_id": f"err_{int(time.time())}"
                },
                "timestamp": time.time()
            }
        )

    app.include_router(video_processing_router)

    @app.get("/health")
    @app.get("/system/health")
    async def health_check():
        """
        Service health check endpoint for monitoring and load balancer probes.

        Provides basic service health information including service status,
        version information, and timestamp for monitoring systems, load
        balancers, and automated health check procedures.
        """
        return {
            "status": "healthy",
            "service": "video-processing",
            "version": settings.app_version,
            "timestamp": time.time()
        }

    @app.get("/")
    async def root():
        """
        Root endpoint with service information and API discovery.

        Returns comprehensive service information including version,
        environment, operational status, and available documentation
        links for API discovery and service identification.
        """
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "status": "running",
            "description": "Video processing microservice for frame extraction and job management",
            "docs_url": "/docs" if settings.debug else None,
            "api_version": "v1"
        }

    return app


app = create_application()
app.openapi = custom_openapi()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
        access_log=True
    )