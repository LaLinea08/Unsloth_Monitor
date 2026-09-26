"""Shared, immutable readings. Missing values are never represented as zero."""

from dataclasses import dataclass, field
from enum import Enum
import time


class Availability(str, Enum):
    AVAILABLE = "available"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    PERMISSION_DENIED = "permission_denied"
    STALE = "stale"


@dataclass(frozen=True)
class Metric:
    value: float | int | str | None = None
    unit: str = ""
    source: str = ""
    availability: Availability = Availability.UNAVAILABLE
    timestamp: float = field(default_factory=time.time)
    detail: str = ""

    @classmethod
    def available(cls, value, unit="", source="", detail=""):
        return cls(value=value, unit=unit, source=source,
                   availability=Availability.AVAILABLE, detail=detail)


@dataclass(frozen=True)
class HardwareSnapshot:
    metrics: dict[str, Metric] = field(default_factory=dict)
    hostname: str = ""
    timestamp: float = field(default_factory=time.time)


class ConnectionStatus(str, Enum):
    CHECKING = "checking"
    OFFLINE = "offline"
    AUTH_REQUIRED = "authentication required"
    UNSUPPORTED = "unsupported response"
    API_REACHABLE = "API reachable · identity unverified"
    ONLINE = "online"
    NO_MODEL = "online · no model loaded"


@dataclass(frozen=True)
class ConnectionSnapshot:
    status: ConnectionStatus = ConnectionStatus.CHECKING
    metrics: dict[str, Metric] = field(default_factory=dict)
    detail: str = ""
    timestamp: float = field(default_factory=time.time)
