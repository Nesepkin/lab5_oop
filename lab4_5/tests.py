from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from behaviors import (
    CompositeFilterStrategy,
    CompositeSortStrategy,
    MaxPriceFilterStrategy,
    ModeFilterStrategy,
    SortDirection,
    SpeedSortStrategy,
    TotalPriceSortStrategy,
)
from catalog import CatalogLoaderFactory
from exporters import CsvQuoteExporter, EncryptedQuoteExporter, ZipCompressedQuoteExporter
from facade import LogisticsFacade
from factories import TransportFactoryProvider
from models import CargoRequest, DeliveryMode
from services import LogisticsService


BASE_DIR = Path(__file__).resolve().parent


def build_service(catalog_path: Path) -> LogisticsService:
    catalog = CatalogLoaderFactory.create(catalog_path).load()
    return LogisticsService(catalog, TransportFactoryProvider(catalog))


class LogisticsServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.csv_service = build_service(BASE_DIR / "logistic.csv")
        cls.cargo_requests = (
            CargoRequest("Электроника", 2),
            CargoRequest("Одежда", 5),
            CargoRequest("Оборудование", 1),
        )

    def test_land_delivery_quotes_match_formula(self) -> None:
        quotes = self.csv_service.calculate_delivery_options(
            self.cargo_requests,
            distance_km=100,
            mode=DeliveryMode.LAND,
        )

        self.assertEqual(2, len(quotes))
        self.assertEqual("Грузовик (Земля)", quotes[0].transport_name)
        self.assertAlmostEqual(3530.0, quotes[0].total_price)
        self.assertAlmostEqual(80.0, quotes[0].speed_kmh)
        self.assertAlmostEqual(1.25, quotes[0].estimated_hours)

        self.assertEqual("Поезд (Земля)", quotes[1].transport_name)
        self.assertAlmostEqual(2530.0, quotes[1].total_price)
        self.assertAlmostEqual(60.0, quotes[1].speed_kmh)
        self.assertAlmostEqual(100 / 60, quotes[1].estimated_hours)

    def test_mode_is_optional_and_returns_all_transports(self) -> None:
        quotes = self.csv_service.calculate_delivery_options(
            self.cargo_requests,
            distance_km=100,
            mode=None,
        )

        self.assertEqual(5, len(quotes))
        modes = {quote.mode for quote in quotes}
        self.assertEqual({DeliveryMode.LAND, DeliveryMode.WATER, DeliveryMode.AIR}, modes)

    def test_json_loader_matches_csv_results(self) -> None:
        json_service = build_service(BASE_DIR / "logistic.json")

        csv_quotes = self.csv_service.calculate_delivery_options(
            self.cargo_requests,
            distance_km=100,
            mode=DeliveryMode.WATER,
        )
        json_quotes = json_service.calculate_delivery_options(
            self.cargo_requests,
            distance_km=100,
            mode=DeliveryMode.WATER,
        )

        self.assertEqual(len(csv_quotes), len(json_quotes))
        self.assertAlmostEqual(csv_quotes[0].total_price, json_quotes[0].total_price)
        self.assertEqual(csv_quotes[0].transport_name, json_quotes[0].transport_name)

    def test_xml_loader_matches_csv_results(self) -> None:
        xml_service = build_service(BASE_DIR / "logistic.xml")

        csv_quotes = self.csv_service.calculate_delivery_options(
            self.cargo_requests,
            distance_km=100,
            mode=DeliveryMode.AIR,
        )
        xml_quotes = xml_service.calculate_delivery_options(
            self.cargo_requests,
            distance_km=100,
            mode=DeliveryMode.AIR,
        )

        self.assertEqual(len(csv_quotes), len(xml_quotes))
        self.assertEqual(
            {quote.transport_name for quote in csv_quotes},
            {quote.transport_name for quote in xml_quotes},
        )

    def test_unknown_cargo_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            self.csv_service.calculate_delivery_options(
                (CargoRequest("Несуществующий груз", 1),),
                distance_km=100,
                mode=DeliveryMode.LAND,
            )

    def test_distance_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            self.csv_service.calculate_delivery_options(
                self.cargo_requests,
                distance_km=0,
                mode=DeliveryMode.WATER,
            )


class BehaviorAndExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.facade = LogisticsFacade.from_catalog_file(BASE_DIR / "logistic.csv")
        cls.cargo_requests = (
            CargoRequest("Электроника", 2),
            CargoRequest("Одежда", 5),
            CargoRequest("Оборудование", 1),
        )

    def test_filters_and_composite_sort_are_applied(self) -> None:
        quotes = self.facade.calculate(
            cargo_requests=self.cargo_requests,
            distance_km=100,
            mode=None,
        )

        filter_strategy = CompositeFilterStrategy(
            (
                ModeFilterStrategy(DeliveryMode.LAND),
                MaxPriceFilterStrategy(4000),
            )
        )
        sort_strategy = CompositeSortStrategy(
            (
                SpeedSortStrategy(SortDirection.ASC),
                TotalPriceSortStrategy(SortDirection.DESC),
            )
        )

        prepared = self.facade.apply_behavior(
            quotes=quotes,
            filter_strategy=filter_strategy,
            sort_strategy=sort_strategy,
        )

        prepared_quotes = prepared.as_tuple()
        self.assertEqual(2, len(prepared_quotes))
        self.assertEqual("Поезд (Земля)", prepared_quotes[0].transport_name)
        self.assertEqual("Грузовик (Земля)", prepared_quotes[1].transport_name)

    def test_export_can_combine_encryption_and_zip(self) -> None:
        quotes = self.facade.calculate(
            cargo_requests=self.cargo_requests,
            distance_km=100,
            mode=DeliveryMode.AIR,
        )

        exporter = ZipCompressedQuoteExporter(
            EncryptedQuoteExporter(CsvQuoteExporter(), key="oop-lab")
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = self.facade.export(
                quotes=quotes,
                exporter=exporter,
                output_dir=Path(tmp_dir),
                base_name="delivery_quotes",
            )

            self.assertTrue(output_path.exists())
            self.assertTrue(output_path.name.endswith(".zip"))

            with ZipFile(output_path, "r") as archive:
                names = archive.namelist()
                self.assertEqual(1, len(names))
                self.assertTrue(names[0].endswith(".csv.enc"))
                payload = archive.read(names[0])
                self.assertGreater(len(payload), 0)


if __name__ == "__main__":
    unittest.main()
