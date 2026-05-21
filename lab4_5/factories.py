from __future__ import annotations

from abc import ABC, abstractmethod

from catalog import LogisticsCatalog, TransportSpec
from models import (
    AirTransport,
    Cargo,
    CargoBatch,
    CargoRequest,
    DeliveryMode,
    LandTransport,
    Transport,
    WaterTransport,
)


class CargoBatchBuilder:
    def __init__(self, catalog: LogisticsCatalog):
        self._catalog = catalog
        self._items: list[Cargo] = []

    def add_request(self, request: CargoRequest) -> CargoBatchBuilder:
        prototype = self._catalog.get_cargo_prototype(request.cargo_name)
        self._items.append(prototype.clone(request.quantity))
        return self

    def build(self) -> CargoBatch:
        return CargoBatch(tuple(self._items))


class TransportFactory(ABC):
    def __init__(self, specs: tuple[TransportSpec, ...]):
        self._specs = specs

    def create_transports(self) -> tuple[Transport, ...]:
        return tuple(self._create_transport(spec) for spec in self._specs)

    @abstractmethod
    def _create_transport(self, spec: TransportSpec) -> Transport:
        raise NotImplementedError


class LandTransportFactory(TransportFactory):
    def _create_transport(self, spec: TransportSpec) -> Transport:
        return LandTransport(
            name=spec.name,
            delivery_overhead_per_km=spec.delivery_overhead_per_km,
            speed_kmh=spec.speed_kmh,
        )


class WaterTransportFactory(TransportFactory):
    def _create_transport(self, spec: TransportSpec) -> Transport:
        return WaterTransport(
            name=spec.name,
            delivery_overhead_per_km=spec.delivery_overhead_per_km,
            speed_kmh=spec.speed_kmh,
        )


class AirTransportFactory(TransportFactory):
    def _create_transport(self, spec: TransportSpec) -> Transport:
        return AirTransport(
            name=spec.name,
            delivery_overhead_per_km=spec.delivery_overhead_per_km,
            speed_kmh=spec.speed_kmh,
        )


class TransportFactoryProvider:
    def __init__(self, catalog: LogisticsCatalog):
        self._factories: dict[DeliveryMode, TransportFactory] = {
            DeliveryMode.LAND: LandTransportFactory(
                catalog.get_transport_specs(DeliveryMode.LAND)
            ),
            DeliveryMode.WATER: WaterTransportFactory(
                catalog.get_transport_specs(DeliveryMode.WATER)
            ),
            DeliveryMode.AIR: AirTransportFactory(
                catalog.get_transport_specs(DeliveryMode.AIR)
            ),
        }

    def get_factory(self, mode: DeliveryMode) -> TransportFactory:
        try:
            return self._factories[mode]
        except KeyError as error:
            raise ValueError(f"unsupported delivery mode: {mode.value}") from error
