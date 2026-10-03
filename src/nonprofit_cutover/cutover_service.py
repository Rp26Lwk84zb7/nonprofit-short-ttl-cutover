import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Literal

from fastapi import Depends, FastAPI, Header, HTTPException

from .infrai_dns import InfraiDnsClient, InfraiError
from .models import AppliedCutover, CutoverPlan, CutoverRequest, RouteChange


def build_plan(request: CutoverRequest) -> CutoverPlan:
    ready = all(route.ready for route in request.routes)
    changes = [
        RouteChange(
            name=route.name,
            from_address=route.current_address,
            to_address=route.next_address,
            ttl=request.short_ttl,
        )
        for route in request.routes
    ]
    rollback = [
        RouteChange(
            name=route.name,
            from_address=route.next_address,
            to_address=route.current_address,
            ttl=request.short_ttl,
        )
        for route in request.routes
    ]
    return CutoverPlan(
        domain=request.domain,
        decision="ready" if ready else "hold",
        changes=changes,
        rollback=rollback,
    )


def get_dns_client() -> InfraiDnsClient:
    return InfraiDnsClient(os.environ["INFRAI_API_KEY"])


@asynccontextmanager
async def client_lifespan(client: InfraiDnsClient) -> AsyncIterator[InfraiDnsClient]:
    async with client:
        yield client


app = FastAPI(title="Nonprofit DNS cutover")


@app.post("/cutovers/plan", response_model=CutoverPlan)
async def plan_cutover(request: CutoverRequest) -> CutoverPlan:
    return build_plan(request)


@app.post("/cutovers/apply", response_model=AppliedCutover)
async def apply_cutover(
    request: CutoverRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    client: InfraiDnsClient = Depends(get_dns_client),
) -> AppliedCutover:
    return await execute(request, "cutover", idempotency_key, client)


@app.post("/cutovers/rollback", response_model=AppliedCutover)
async def rollback_cutover(
    request: CutoverRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    client: InfraiDnsClient = Depends(get_dns_client),
) -> AppliedCutover:
    return await execute(request, "rollback", idempotency_key, client)


async def execute(
    request: CutoverRequest,
    action: Literal["cutover", "rollback"],
    idempotency_key: str,
    client: InfraiDnsClient,
) -> AppliedCutover:
    plan = build_plan(request)
    if action == "cutover" and plan.decision == "hold":
        raise HTTPException(status_code=409, detail="all three services must be ready")

    selected = plan.changes if action == "cutover" else plan.rollback
    try:
        async with client_lifespan(client):
            zone_id = await client.get_zone_id(request.domain)
            for change in selected:
                await client.upsert_a_record(
                    zone_id=zone_id,
                    name=change.name,
                    content=change.to_address,
                    ttl=change.ttl,
                    idempotency_key=f"{idempotency_key}:{action}:{change.name}",
                )
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return AppliedCutover(
        domain=request.domain,
        zone_id=zone_id,
        action=action,
        records_changed=[change.name for change in selected],
    )


def main() -> None:
    import uvicorn

    uvicorn.run("nonprofit_cutover.cutover_service:app", host="127.0.0.1", port=8000)
