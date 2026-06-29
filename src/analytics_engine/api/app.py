"""FastAPI application factory."""

from fastapi import FastAPI

from analytics_engine.api.routes_admin import router as admin_router
from analytics_engine.api.routes_alerts import router as alerts_router
from analytics_engine.api.routes_health import router as health_router
from analytics_engine.api.routes_insights import router as insights_router
from analytics_engine.api.routes_loan import router as loan_router
from analytics_engine.api.routes_metrics import router as metrics_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Project K Analytics Engine",
        description="Working capital analytics for Indian MSMEs",
        version="0.1.0",
        root_path="/analytics",
    )

    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(alerts_router)
    app.include_router(admin_router)
    app.include_router(insights_router)
    app.include_router(loan_router)

    return app


app = create_app()
