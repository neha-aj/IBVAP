from contextlib import asynccontextmanager

from fastapi import FastAPI

from ibvap_common.errors import install_error_handlers
from ibvap_common.logging import configure_logging, get_logger, install_correlation_id_middleware
from ibvap_common.metrics import install_metrics

from app.api import alerts as alert_routes
from app.api import data_management as data_management_routes
from app.api import events as event_routes
from app.api import health as health_routes
from app.api import internal_events as internal_event_routes
from app.api import rule_settings as rule_settings_routes
from app.core.config import get_settings
from app.db.session import get_session_factory
from app.streaming.reconcile_manager import ReconcileManager

settings = get_settings()
configure_logging(settings.service_name)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = ReconcileManager(settings, get_session_factory())
    app.state.reconcile_manager = manager
    await manager.start()
    logger.info("event_alert_service_started")
    yield
    await manager.stop()
    logger.info("event_alert_service_stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="IBVAP Event/Alert Service", version="0.1.0", lifespan=lifespan)
    install_correlation_id_middleware(app)
    install_metrics(app, settings.service_name)
    install_error_handlers(app)
    app.include_router(event_routes.router)
    app.include_router(data_management_routes.router)
    # Registered before alert_routes: its static /alerts/thresholds path
    # would otherwise be shadowed by alert_routes' GET /{alert_id} (same
    # ordering concern camera-service's admin_audit_log router has against
    # its own GET /{camera_id}).
    app.include_router(rule_settings_routes.router)
    app.include_router(alert_routes.router)
    app.include_router(internal_event_routes.router)
    app.include_router(health_routes.router)
    return app


app = create_app()
