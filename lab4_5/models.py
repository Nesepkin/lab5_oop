from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from enum import Enum


class DeliveryMode(Enum):
    LAND = "land"
    WATER = "water"
    AIR = "air"

    @property
    def label(self) -> str:
        labels = {
            DeliveryMode.LAND: "земля",
            DeliveryMode.WATER: "вода",
            DeliveryMode.AIR: "воздух",
        }
        return labels[self]


@dataclass(frozen=True)
class CargoRequest:
    cargo_name: str
    quantity: int

    def __post_init__(self) -> None:
        if not self.cargo_name.strip():
            raise ValueError("cargo name is required")
        if self.quantity <= 0:
            raise ValueError("cargo quantity must be greater than zero")


@dataclass(frozen=True)
class Cargo:
    name: str
    unit_mass_kg: float
    delivery_cost_per_kg: float
    quantity: int = 0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("cargo name is required")
        if self.unit_mass_kg <= 0:
            raise ValueError("cargo unit mass must be greater than zero")
        if self.delivery_cost_per_kg < 0:
            raise ValueError("cargo cost per kg cannot be negative")
        if self.quantity < 0:
            raise ValueError("cargo quantity cannot be negative")

    def clone(self, quantity: int) -> Cargo:
        if quantity <= 0:
            raise ValueError("cargo quantity must be greater than zero")
        return replace(self, quantity=quantity)

    @property
    def total_mass_kg(self) -> float:
        return self.unit_mass_kg * self.quantity

    @property
    def delivery_cost(self) -> float:
        return self.delivery_cost_per_kg * self.total_mass_kg


@dataclass(frozen=True)
class CargoBatch:
    items: tuple[Cargo, ...]

    def __post_init__(self) -> None:
        if not self.items:
            raise ValueError("cargo batch must contain at least one cargo item")

    @property
    def total_mass_kg(self) -> float:
        return sum(item.total_mass_kg for item in self.items)

    @property
    def cargo_delivery_cost(self) -> float:
        return sum(item.delivery_cost for item in self.items)


@dataclass(frozen=True)
class Transport(ABC):
    name: str
    delivery_overhead_per_km: float
    speed_kmh: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("transport name is required")
        if self.delivery_overhead_per_km < 0:
            raise ValueError("delivery overhead cannot be negative")
        if self.speed_kmh <= 0:
            raise ValueError("transport speed must be greater than zero")

    @property
    @abstractmethod
    def mode(self) -> DeliveryMode:
        raise NotImplementedError


@dataclass(frozen=True)
class LandTransport(Transport):
    @property
    def mode(self) -> DeliveryMode:
        return DeliveryMode.LAND


@dataclass(frozen=True)
class WaterTransport(Transport):
    @property
    def mode(self) -> DeliveryMode:
        return DeliveryMode.WATER


@dataclass(frozen=True)
class AirTransport(Transport):
    @property
    def mode(self) -> DeliveryMode:
        return DeliveryMode.AIR


@dataclass(frozen=True)
class DeliveryQuote:
    transport_name: str
    mode: DeliveryMode
    total_price: float
    speed_kmh: float
    estimated_hours: float
    cargo_cost: float
    distance_cost: float


@dataclass(frozen=True)
class Shipment:
    batch: CargoBatch
    distance_km: float
    transport: Transport

    def __post_init__(self) -> None:
        if self.distance_km <= 0:
            raise ValueError("distance must be greater than zero")

    def build_quote(self) -> DeliveryQuote:
        cargo_cost = self.batch.cargo_delivery_cost
        distance_cost = self.distance_km * self.transport.delivery_overhead_per_km
        total_price = cargo_cost + distance_cost
        estimated_hours = self.distance_km / self.transport.speed_kmh
        return DeliveryQuote(
            transport_name=self.transport.name,
            mode=self.transport.mode,
            total_price=total_price,
            speed_kmh=self.transport.speed_kmh,
            estimated_hours=estimated_hours,
            cargo_cost=cargo_cost,
            distance_cost=distance_cost,
        )
