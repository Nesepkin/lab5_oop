from __future__ import annotations

from pathlib import Path

from behaviors import (
    CompositeFilterStrategy,
    CompositeSortStrategy,
    MaxPriceFilterStrategy,
    MinSpeedFilterStrategy,
    SortDirection,
    SpeedSortStrategy,
    TotalPriceSortStrategy,
    TransportNameSortStrategy,
)
from exporters import (
    CsvQuoteExporter,
    EncryptedQuoteExporter,
    JsonQuoteExporter,
    ZipCompressedQuoteExporter,
)
from facade import LogisticsFacade
from models import CargoRequest, DeliveryQuote


BASE_DIR = Path(__file__).resolve().parent


def print_quotes(title: str, quotes: tuple[DeliveryQuote, ...]) -> None:
    print(f"\n=== {title} ===")
    for quote in quotes:
        print(
            f"{quote.transport_name}: mode={quote.mode.value}, "
            f"price={quote.total_price:.2f}, speed={quote.speed_kmh:.2f} km/h, "
            f"eta={quote.estimated_hours:.2f} h"
        )


def main() -> None:
    facade = LogisticsFacade.from_catalog_file(BASE_DIR / "logistic.csv")

    cargo_requests = (
        CargoRequest("Электроника", 10),
        CargoRequest("Одежда", 50),
        CargoRequest("Оборудование", 2),
    )
    distance_km = 1200

    raw_quotes = facade.calculate(
        cargo_requests=cargo_requests,
        distance_km=distance_km,
        mode=None,
    )

    filter_strategy = CompositeFilterStrategy(
        (
            MinSpeedFilterStrategy(60),
            MaxPriceFilterStrategy(180_000),
        )
    )
    sort_strategy = CompositeSortStrategy(
        (
            TotalPriceSortStrategy(SortDirection.ASC),
            SpeedSortStrategy(SortDirection.DESC),
            TransportNameSortStrategy(SortDirection.ASC),
        )
    )

    prepared_quotes = facade.apply_behavior(
        quotes=raw_quotes,
        filter_strategy=filter_strategy,
        sort_strategy=sort_strategy,
    )

    print_quotes("Подходящие варианты", prepared_quotes.as_tuple())

    output_dir = BASE_DIR / "output"
    json_exporter = JsonQuoteExporter()
    csv_exporter = CsvQuoteExporter()
    encrypted_json_exporter = EncryptedQuoteExporter(json_exporter, key="oop-lab")
    compressed_and_encrypted_csv_exporter = ZipCompressedQuoteExporter(
        EncryptedQuoteExporter(csv_exporter, key="oop-lab")
    )

    json_path = facade.export(prepared_quotes, json_exporter, output_dir, "quotes")
    encrypted_json_path = facade.export(
        prepared_quotes,
        encrypted_json_exporter,
        output_dir,
        "quotes",
    )
    archive_path = facade.export(
        prepared_quotes,
        compressed_and_encrypted_csv_exporter,
        output_dir,
        "quotes",
    )

    print(f"\nSaved: {json_path}")
    print(f"Saved: {encrypted_json_path}")
    print(f"Saved: {archive_path}")


if __name__ == "__main__":
    main()
