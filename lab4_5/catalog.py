from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from models import Cargo, DeliveryMode


@dataclass(frozen=True)
class TransportSpec:
    name: str
    mode: DeliveryMode
    delivery_overhead_per_km: float
    speed_kmh: float


class LogisticsCatalog:
    def __init__(
        self,
        cargo_prototypes: dict[str, Cargo],
        transport_specs: dict[DeliveryMode, tuple[TransportSpec, ...]],
    ):
        self._cargo_prototypes = cargo_prototypes
        self._transport_specs = transport_specs

    def get_cargo_prototype(self, cargo_name: str) -> Cargo:
        try:
            return self._cargo_prototypes[cargo_name]
        except KeyError as error:
            raise ValueError(f"unknown cargo: {cargo_name}") from error

    def get_transport_specs(self, mode: DeliveryMode) -> tuple[TransportSpec, ...]:
        specs = self._transport_specs.get(mode, ())
        if not specs:
            raise ValueError(f"no transport configured for mode: {mode.value}")
        return specs

    @property
    def cargo_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._cargo_prototypes))


class CatalogLoader(ABC):
    def __init__(self, source_path: Path):
        self._source_path = source_path

    @abstractmethod
    def load(self) -> LogisticsCatalog:
        raise NotImplementedError

    @staticmethod
    def _parse_float(value: str | float | int | None) -> float:
        if value is None:
            raise ValueError("numeric field cannot be empty")
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = value.strip().replace(",", ".")
        if not cleaned:
            raise ValueError("numeric field cannot be empty")
        return float(cleaned)

    @staticmethod
    def _detect_mode(transport_name: str) -> DeliveryMode:
        normalized_name = transport_name.casefold()
        if "земл" in normalized_name:
            return DeliveryMode.LAND
        if "вод" in normalized_name:
            return DeliveryMode.WATER
        if "воздух" in normalized_name:
            return DeliveryMode.AIR
        raise ValueError(
            f"cannot determine delivery mode for transport: {transport_name}"
        )

    @staticmethod
    def _parse_mode(raw_mode: str | None, transport_name: str) -> DeliveryMode:
        if raw_mode is None or not str(raw_mode).strip():
            return CatalogLoader._detect_mode(transport_name)
        normalized_mode = str(raw_mode).strip().casefold()
        aliases = {
            "land": DeliveryMode.LAND,
            "земля": DeliveryMode.LAND,
            "water": DeliveryMode.WATER,
            "вода": DeliveryMode.WATER,
            "air": DeliveryMode.AIR,
            "воздух": DeliveryMode.AIR,
        }
        try:
            return aliases[normalized_mode]
        except KeyError as error:
            raise ValueError(f"unsupported delivery mode: {raw_mode}") from error


class CsvCatalogLoader(CatalogLoader):
    def load(self) -> LogisticsCatalog:
        cargo_prototypes: dict[str, Cargo] = {}
        transport_specs: dict[DeliveryMode, list[TransportSpec]] = {
            DeliveryMode.LAND: [],
            DeliveryMode.WATER: [],
            DeliveryMode.AIR: [],
        }

        with self._source_path.open(encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file, delimiter=";")
            for raw_row in reader:
                row = {key.strip(): value.strip() for key, value in raw_row.items()}
                record_type = row["Тип записи"].lower()
                name = row["Наименование"]

                if record_type == "cargo":
                    cargo_prototypes[name] = Cargo(
                        name=name,
                        unit_mass_kg=self._parse_float(row["Масса_ед_кг"]),
                        delivery_cost_per_kg=self._parse_float(
                            row["Стоимость_перевозки_за_кг"]
                        ),
                    )
                    continue

                if record_type == "transport":
                    mode = self._parse_mode(None, name)
                    transport_specs[mode].append(
                        TransportSpec(
                            name=name,
                            mode=mode,
                            delivery_overhead_per_km=self._parse_float(
                                row["Расход_на_км"]
                            ),
                            speed_kmh=self._parse_float(row["Скорость_км_ч"]),
                        )
                    )
                    continue

                raise ValueError(f"unsupported record type: {record_type}")

        return LogisticsCatalog(
            cargo_prototypes=cargo_prototypes,
            transport_specs={
                mode: tuple(specs) for mode, specs in transport_specs.items() if specs
            },
        )


class JsonCatalogLoader(CatalogLoader):
    def load(self) -> LogisticsCatalog:
        payload = json.loads(self._source_path.read_text(encoding="utf-8"))
        cargo_prototypes: dict[str, Cargo] = {}
        transport_specs: dict[DeliveryMode, list[TransportSpec]] = {
            DeliveryMode.LAND: [],
            DeliveryMode.WATER: [],
            DeliveryMode.AIR: [],
        }

        if isinstance(payload, dict):
            cargo_records = payload.get("cargo", ())
            transport_records = payload.get("transports", ())
        elif isinstance(payload, list):
            cargo_records = [item for item in payload if item.get("type") == "cargo"]
            transport_records = [
                item for item in payload if item.get("type") == "transport"
            ]
        else:
            raise ValueError("JSON catalog root must be object or array")

        for row in cargo_records:
            name = str(row["name"]).strip()
            cargo_prototypes[name] = Cargo(
                name=name,
                unit_mass_kg=self._parse_float(row.get("unit_mass_kg")),
                delivery_cost_per_kg=self._parse_float(row.get("delivery_cost_per_kg")),
            )

        for row in transport_records:
            name = str(row["name"]).strip()
            mode = self._parse_mode(row.get("mode"), name)
            transport_specs[mode].append(
                TransportSpec(
                    name=name,
                    mode=mode,
                    delivery_overhead_per_km=self._parse_float(
                        row.get("delivery_overhead_per_km")
                    ),
                    speed_kmh=self._parse_float(row.get("speed_kmh")),
                )
            )

        return LogisticsCatalog(
            cargo_prototypes=cargo_prototypes,
            transport_specs={
                mode: tuple(specs) for mode, specs in transport_specs.items() if specs
            },
        )


class XmlCatalogLoader(CatalogLoader):
    def load(self) -> LogisticsCatalog:
        tree = ET.parse(self._source_path)
        root = tree.getroot()

        cargo_prototypes: dict[str, Cargo] = {}
        transport_specs: dict[DeliveryMode, list[TransportSpec]] = {
            DeliveryMode.LAND: [],
            DeliveryMode.WATER: [],
            DeliveryMode.AIR: [],
        }

        cargo_nodes = root.findall("./cargo/item")
        for node in cargo_nodes:
            name = str(node.attrib.get("name", "")).strip()
            if not name:
                raise ValueError("cargo name is required in XML catalog")
            cargo_prototypes[name] = Cargo(
                name=name,
                unit_mass_kg=self._parse_float(node.attrib.get("unit_mass_kg")),
                delivery_cost_per_kg=self._parse_float(
                    node.attrib.get("delivery_cost_per_kg")
                ),
            )

        transport_nodes = root.findall("./transports/transport")
        for node in transport_nodes:
            name = str(node.attrib.get("name", "")).strip()
            if not name:
                raise ValueError("transport name is required in XML catalog")
            mode = self._parse_mode(node.attrib.get("mode"), name)
            transport_specs[mode].append(
                TransportSpec(
                    name=name,
                    mode=mode,
                    delivery_overhead_per_km=self._parse_float(
                        node.attrib.get("delivery_overhead_per_km")
                    ),
                    speed_kmh=self._parse_float(node.attrib.get("speed_kmh")),
                )
            )

        return LogisticsCatalog(
            cargo_prototypes=cargo_prototypes,
            transport_specs={
                mode: tuple(specs) for mode, specs in transport_specs.items() if specs
            },
        )


class CatalogLoaderFactory:
    _loader_map = {
        ".csv": CsvCatalogLoader,
        ".json": JsonCatalogLoader,
        ".xml": XmlCatalogLoader,
    }

    @classmethod
    def create(cls, source_path: Path) -> CatalogLoader:
        extension = source_path.suffix.lower()
        loader_class = cls._loader_map.get(extension)
        if loader_class is None:
            supported = ", ".join(sorted(cls._loader_map))
            raise ValueError(
                f"unsupported catalog format '{extension}'. Supported: {supported}"
            )
        return loader_class(source_path)
