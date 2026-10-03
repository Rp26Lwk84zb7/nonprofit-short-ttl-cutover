from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ServiceRoute(BaseModel):
    name: Literal["receipts", "volunteers", "reports"]
    current_address: str = Field(min_length=1)
    next_address: str = Field(min_length=1)
    ready: bool


class CutoverRequest(BaseModel):
    domain: str = Field(min_length=3)
    routes: list[ServiceRoute] = Field(min_length=3, max_length=3)
    short_ttl: int = Field(default=300, ge=60, le=600)

    @model_validator(mode="after")
    def require_each_nonprofit_route(self) -> "CutoverRequest":
        expected = {"receipts", "volunteers", "reports"}
        actual = {route.name for route in self.routes}
        if actual != expected or len(actual) != len(self.routes):
            raise ValueError("routes must contain receipts, volunteers, and reports once each")
        return self


class RouteChange(BaseModel):
    name: str
    from_address: str
    to_address: str
    ttl: int


class CutoverPlan(BaseModel):
    domain: str
    decision: Literal["ready", "hold"]
    changes: list[RouteChange]
    rollback: list[RouteChange]


class AppliedCutover(BaseModel):
    domain: str
    zone_id: str
    action: Literal["cutover", "rollback"]
    records_changed: list[str]
