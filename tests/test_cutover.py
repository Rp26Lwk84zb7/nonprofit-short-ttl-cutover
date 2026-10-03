import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException

from nonprofit_cutover.cutover_service import build_plan, execute
from nonprofit_cutover.infrai_dns import InfraiDnsClient
from nonprofit_cutover.models import CutoverRequest


def cutover_request(*, reports_ready: bool = True) -> CutoverRequest:
    return CutoverRequest.model_validate(
        {
            "domain": "giving.example.org",
            "short_ttl": 300,
            "routes": [
                {"name": "receipts", "current_address": "192.0.2.10", "next_address": "198.51.100.10", "ready": True},
                {"name": "volunteers", "current_address": "192.0.2.11", "next_address": "198.51.100.11", "ready": True},
                {"name": "reports", "current_address": "192.0.2.12", "next_address": "198.51.100.12", "ready": reports_ready},
            ],
        }
    )


def test_plan_holds_every_route_when_campaign_reporting_is_not_ready() -> None:
    plan = build_plan(cutover_request(reports_ready=False))

    assert plan.decision == "hold"
    assert [change.name for change in plan.changes] == ["receipts", "volunteers", "reports"]
    assert all(change.ttl == 300 for change in plan.changes)
    assert plan.rollback[0].to_address == "192.0.2.10"


def test_apply_gets_zone_id_before_upserting_records() -> None:
    asyncio.run(assert_apply_request_boundary())


def test_apply_translates_missing_zone_id_to_controlled_error() -> None:
    asyncio.run(assert_missing_zone_id_error())


async def assert_apply_request_boundary() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/domain/get"):
            return httpx.Response(200, json={"ok": True, "data": {"zone_id": "zone_123"}, "error": None, "metadata": {}})
        return httpx.Response(200, json={"ok": True, "data": {"record_id": "record_123"}, "error": None, "metadata": {}})

    client = InfraiDnsClient("test-key", transport=httpx.MockTransport(handler))
    result = await execute(cutover_request(), "cutover", "cutover-2026-09-23", client)

    assert result.zone_id == "zone_123"
    assert seen[0].method == "GET"
    assert seen[0].url.params["domain"] == "giving.example.org"
    bodies = [json.loads(request.content) for request in seen[1:]]
    assert all(body["zone_id"] == "zone_123" for body in bodies)
    assert [body["name"] for body in bodies] == ["receipts", "volunteers", "reports"]
    assert all(request.method == "PUT" for request in seen[1:])


async def assert_missing_zone_id_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": True, "data": {}, "error": None, "metadata": {}},
        )

    client = InfraiDnsClient("test-key", transport=httpx.MockTransport(handler))

    with pytest.raises(HTTPException) as caught:
        await execute(cutover_request(), "cutover", "cutover-missing-zone", client)

    assert caught.value.status_code == 502
    assert caught.value.detail == {
        "code": "INFRAI_INVALID_RESPONSE",
        "message": "domain response did not include a nonempty zone_id",
    }
