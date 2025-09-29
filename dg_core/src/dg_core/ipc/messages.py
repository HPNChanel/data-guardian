"""Pydantic models for JSON-RPC payloads."""
from __future__ import annotations

from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


IDType = Union[str, int, None]


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None

    model_config = ConfigDict(extra="forbid")


class JSONRPCRequest(BaseModel):
    jsonrpc: str = Field(default="2.0")
    method: str
    params: Dict[str, Any] | list[Any] | None = None
    id: IDType = None

    model_config = ConfigDict(extra="forbid")


class JSONRPCResponse(BaseModel):
    jsonrpc: str = Field(default="2.0")
    result: Any | None = None
    error: JSONRPCError | None = None
    id: IDType = None

    model_config = ConfigDict(extra="forbid")


class HealthPayload(BaseModel):
    status: str
    version: str


class ScanRequest(BaseModel):
    text: str
    detectors: list[str] | None = None
    max_results: int | None = None


class ScanResponse(BaseModel):
    detections: list[dict[str, Any]]


class RedactRequest(BaseModel):
    text: str
    policy: dict[str, Any] | None = None
    policy_path: str | None = None


class RedactResponse(BaseModel):
    text: str
    segments: list[dict[str, Any]]


__all__ = [
    "JSONRPCRequest",
    "JSONRPCResponse",
    "JSONRPCError",
    "HealthPayload",
    "ScanRequest",
    "ScanResponse",
    "RedactRequest",
    "RedactResponse",
]