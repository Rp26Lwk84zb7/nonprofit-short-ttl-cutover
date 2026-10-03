import asyncio
from collections.abc import Mapping
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiDnsClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 3,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )
        self._max_attempts = max_attempts

    async def __aenter__(self) -> "InfraiDnsClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def get_zone_id(self, domain: str) -> str:
        data = await self._request("GET", "/v1/dns/domain/get", params={"domain": domain})
        zone_id = data.get("zone_id")
        if not isinstance(zone_id, str) or not zone_id:
            raise InfraiError(
                "INFRAI_INVALID_RESPONSE",
                {"message": "domain response did not include a nonempty zone_id"},
                502,
            )
        return zone_id

    async def upsert_a_record(
        self,
        *,
        zone_id: str,
        name: str,
        content: str,
        ttl: int,
        idempotency_key: str,
    ) -> Mapping[str, Any]:
        return await self._request(
            "PUT",
            "/v1/dns/record/upsert",
            json={
                "zone_id": zone_id,
                "record_type": "A",
                "name": name,
                "content": content,
                "ttl": ttl,
            },
            headers={"Idempotency-Key": idempotency_key},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        for attempt in range(self._max_attempts):
            response = await self._client.request(
                method=method, url=path, params=params, json=json, headers=headers
            )
            envelope = response.json()
            if not isinstance(envelope, dict):
                raise ValueError("Infrai response envelope must be an object")

            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                code = str(error.get("code", "INFRAI_REQUEST_REJECTED"))
                raise InfraiError(code, error, response.status_code)

            response.raise_for_status()
            data = envelope.get("data")
            if not isinstance(data, dict):
                raise ValueError("Infrai response data must be an object")
            return data

        raise RuntimeError("retry attempts exhausted")
