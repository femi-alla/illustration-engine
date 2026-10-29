"""HTTP API for the illustration engine.

Endpoints:
    POST /v1/illustrations   run the three-scenario projection
    GET  /v1/assumptions     the synthetic charge, mortality and corridor assumptions in use
    GET  /healthz            liveness (process is up)
    GET  /readyz             readiness (engine can run a projection)
    GET  /metrics            Prometheus exposition
    GET  /version            build metadata injected at deploy time
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

from illustration_engine import __version__
from illustration_engine.assumptions import (
    DEFAULT_PRODUCT,
    RISK_CLASS_MULTIPLIER,
    annual_mortality_rate,
    corridor_factor,
)
from illustration_engine.engine import illustrate
from illustration_engine.logging_config import configure_logging
from illustration_engine.models import IllustrationRequest, IllustrationResponse

log = logging.getLogger("illustration_engine.api")


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path: str | None = getattr(route, "path", None)
    return path or "unmatched"


def create_app(registry: CollectorRegistry | None = None) -> FastAPI:
    """Build the application. A fresh registry per app keeps tests independent."""
    configure_logging()
    registry = registry or CollectorRegistry()
    requests_total = Counter(
        "http_requests_total",
        "HTTP requests by method, route template and status",
        ["method", "route", "status"],
        registry=registry,
    )
    request_latency = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency by route template",
        ["method", "route"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
        registry=registry,
    )
    illustrations_total = Counter(
        "illustrations_total",
        "Illustrations produced, by crediting kind",
        ["crediting_kind"],
        registry=registry,
    )

    app = FastAPI(
        title="Illustration Engine",
        version=__version__,
        description=(
            "Educational demo of a life insurance illustration engine. All assumptions "
            "are synthetic; nothing here describes or promotes a real product."
        ),
        docs_url="/docs",
        redoc_url=None,
    )

    @app.middleware("http")
    async def observe(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled error", extra={"request_id": request_id})
            response = JSONResponse({"detail": "internal error"}, status_code=500)
        elapsed = time.perf_counter() - started
        route = _route_template(request)
        if route != "/metrics":
            requests_total.labels(request.method, route, str(response.status_code)).inc()
            request_latency.labels(request.method, route).observe(elapsed)
        response.headers["x-request-id"] = request_id
        log.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "route": route,
                "status": response.status_code,
                "duration_ms": round(elapsed * 1000, 2),
            },
        )
        return response

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    def readyz() -> dict[str, str]:
        # Run a tiny projection so readiness proves the engine, not just the process.
        illustrate(
            IllustrationRequest(
                issue_age=35, face_amount=25_000, annual_premium=600, projection_years=1
            )
        )
        return {"status": "ready"}

    @app.get("/version", tags=["ops"])
    def version() -> dict[str, str]:
        return {
            "version": __version__,
            "git_sha": os.getenv("GIT_SHA", "unknown"),
            "built_at": os.getenv("BUILD_TIME", "unknown"),
        }

    @app.get("/metrics", tags=["ops"], include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.get("/v1/assumptions", tags=["illustration"])
    def assumptions() -> dict[str, Any]:
        sample_ages = (25, 35, 45, 55, 65, 75, 85, 95)
        return {
            "product": {
                "premium_load": DEFAULT_PRODUCT.premium_load,
                "monthly_policy_fee": DEFAULT_PRODUCT.monthly_policy_fee,
                "per_thousand_monthly_charge": DEFAULT_PRODUCT.per_thousand_monthly_charge,
                "per_thousand_years": DEFAULT_PRODUCT.per_thousand_years,
                "surrender_charge_per_thousand": list(
                    DEFAULT_PRODUCT.surrender_charge_per_thousand
                ),
                "current_coi_factor": DEFAULT_PRODUCT.current_coi_factor,
            },
            "risk_class_multiplier": RISK_CLASS_MULTIPLIER,
            "mortality_per_thousand": {
                str(age): round(annual_mortality_rate(age) * 1000, 3) for age in sample_ages
            },
            "corridor_factor": {str(age): corridor_factor(age) for age in sample_ages},
            "notice": "Synthetic assumptions for an educational demo; not a real product.",
        }

    @app.post("/v1/illustrations", tags=["illustration"], response_model=IllustrationResponse)
    def create_illustration(body: IllustrationRequest) -> IllustrationResponse:
        result = illustrate(body)
        illustrations_total.labels(body.crediting.kind).inc()
        return result

    return app


app = create_app()
