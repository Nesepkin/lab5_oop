from __future__ import annotations

import base64
import csv
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from behaviors import DeliveryQuoteCollection


@dataclass(frozen=True)
class ExportArtifact:
    file_name: str
    payload: bytes


class QuoteExporter(ABC):
    @abstractmethod
    def build_artifact(
        self,
        quotes: DeliveryQuoteCollection,
        base_name: str,
    ) -> ExportArtifact:
        raise NotImplementedError


class JsonQuoteExporter(QuoteExporter):
    def build_artifact(
        self,
        quotes: DeliveryQuoteCollection,
        base_name: str,
    ) -> ExportArtifact:
        payload = [
            {
                "transport_name": quote.transport_name,
                "mode": quote.mode.value,
                "total_price": quote.total_price,
                "speed_kmh": quote.speed_kmh,
                "estimated_hours": quote.estimated_hours,
                "cargo_cost": quote.cargo_cost,
                "distance_cost": quote.distance_cost,
            }
            for quote in quotes
        ]
        raw_text = json.dumps(payload, ensure_ascii=False, indent=2)
        return ExportArtifact(file_name=f"{base_name}.json", payload=raw_text.encode("utf-8"))


class CsvQuoteExporter(QuoteExporter):
    _headers = (
        "transport_name",
        "mode",
        "total_price",
        "speed_kmh",
        "estimated_hours",
        "cargo_cost",
        "distance_cost",
    )

    def build_artifact(
        self,
        quotes: DeliveryQuoteCollection,
        base_name: str,
    ) -> ExportArtifact:
        buffer = StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(self._headers)
        for quote in quotes:
            writer.writerow(
                (
                    quote.transport_name,
                    quote.mode.value,
                    f"{quote.total_price:.6f}",
                    f"{quote.speed_kmh:.6f}",
                    f"{quote.estimated_hours:.6f}",
                    f"{quote.cargo_cost:.6f}",
                    f"{quote.distance_cost:.6f}",
                )
            )
        return ExportArtifact(
            file_name=f"{base_name}.csv",
            payload=buffer.getvalue().encode("utf-8"),
        )


class QuoteExporterDecorator(QuoteExporter, ABC):
    def __init__(self, exporter: QuoteExporter):
        self._exporter = exporter


class EncryptedQuoteExporter(QuoteExporterDecorator):
    def __init__(self, exporter: QuoteExporter, key: str):
        super().__init__(exporter)
        if not key:
            raise ValueError("encryption key is required")
        self._key = key.encode("utf-8")

    def build_artifact(
        self,
        quotes: DeliveryQuoteCollection,
        base_name: str,
    ) -> ExportArtifact:
        artifact = self._exporter.build_artifact(quotes, base_name)
        encrypted = self._xor_bytes(artifact.payload)
        encoded = base64.b64encode(encrypted)
        return ExportArtifact(
            file_name=f"{artifact.file_name}.enc",
            payload=encoded,
        )

    def _xor_bytes(self, payload: bytes) -> bytes:
        return bytes(
            value ^ self._key[index % len(self._key)]
            for index, value in enumerate(payload)
        )


class ZipCompressedQuoteExporter(QuoteExporterDecorator):
    def build_artifact(
        self,
        quotes: DeliveryQuoteCollection,
        base_name: str,
    ) -> ExportArtifact:
        artifact = self._exporter.build_artifact(quotes, base_name)
        byte_buffer = BytesIO()
        with ZipFile(byte_buffer, mode="w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(artifact.file_name, artifact.payload)

        return ExportArtifact(
            file_name=f"{artifact.file_name}.zip",
            payload=byte_buffer.getvalue(),
        )


class ExportFacade:
    def save(
        self,
        quotes: DeliveryQuoteCollection,
        exporter: QuoteExporter,
        output_dir: Path,
        base_name: str,
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        artifact = exporter.build_artifact(quotes, base_name)
        output_path = output_dir / artifact.file_name
        output_path.write_bytes(artifact.payload)
        return output_path
