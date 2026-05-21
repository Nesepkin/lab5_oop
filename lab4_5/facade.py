from __future__ import annotations

from pathlib import Path

from behaviors import (
    CompositeFilterStrategy,
    CompositeSortStrategy,
    DeliveryQuoteCollection,
)
from catalog import CatalogLoaderFactory
from exporters import ExportFacade, QuoteExporter
from factories import TransportFactoryProvider
from models import CargoRequest, DeliveryMode
from services import LogisticsService


class LogisticsFacade:
    def __init__(self, service: LogisticsService):
        self._service = service
        self._export_facade = ExportFacade()

    @classmethod
    def from_catalog_file(cls, source_path: Path) -> LogisticsFacade:
        catalog = CatalogLoaderFactory.create(source_path).load()
        return cls(LogisticsService(catalog, TransportFactoryProvider(catalog)))

    def calculate(
        self,
        cargo_requests: tuple[CargoRequest, ...],
        distance_km: float,
        mode: DeliveryMode | None = None,
    ) -> DeliveryQuoteCollection:
        quotes = self._service.calculate_delivery_options(
            cargo_requests=cargo_requests,
            distance_km=distance_km,
            mode=mode,
        )
        return DeliveryQuoteCollection(quotes)

    def apply_behavior(
        self,
        quotes: DeliveryQuoteCollection,
        filter_strategy: CompositeFilterStrategy | None = None,
        sort_strategy: CompositeSortStrategy | None = None,
    ) -> DeliveryQuoteCollection:
        result = quotes
        if filter_strategy is not None:
            result = filter_strategy.apply(result)
        if sort_strategy is not None:
            result = sort_strategy.apply(result)
        return result

    def export(
        self,
        quotes: DeliveryQuoteCollection,
        exporter: QuoteExporter,
        output_dir: Path,
        base_name: str,
    ) -> Path:
        return self._export_facade.save(
            quotes=quotes,
            exporter=exporter,
            output_dir=output_dir,
            base_name=base_name,
        )
