from __future__ import annotations

from catalog import LogisticsCatalog
from factories import CargoBatchBuilder, TransportFactoryProvider
from models import CargoRequest, DeliveryMode, DeliveryQuote, Shipment


class LogisticsService:
    def __init__(
        self,
        catalog: LogisticsCatalog,
        factory_provider: TransportFactoryProvider,
    ):
        self._catalog = catalog
        self._factory_provider = factory_provider

    def calculate_delivery_options(
        self,
        cargo_requests: tuple[CargoRequest, ...],
        distance_km: float,
        mode: DeliveryMode | None = None,
    ) -> tuple[DeliveryQuote, ...]:
        batch_builder = CargoBatchBuilder(self._catalog)
        for request in cargo_requests:
            batch_builder.add_request(request)

        batch = batch_builder.build()
        selected_modes = (mode,) if mode is not None else tuple(DeliveryMode)

        quotes: list[DeliveryQuote] = []
        for selected_mode in selected_modes:
            factory = self._factory_provider.get_factory(selected_mode)
            transports = factory.create_transports()
            quotes.extend(
                Shipment(batch=batch, distance_km=distance_km, transport=transport).build_quote()
                for transport in transports
            )

        return tuple(quotes)
