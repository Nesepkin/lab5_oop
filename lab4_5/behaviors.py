from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Iterator

from models import DeliveryMode, DeliveryQuote


class DeliveryQuoteIterator(Iterator[DeliveryQuote]):
    def __init__(self, quotes: tuple[DeliveryQuote, ...]):
        self._quotes = quotes
        self._index = 0

    def __next__(self) -> DeliveryQuote:
        if self._index >= len(self._quotes):
            raise StopIteration
        quote = self._quotes[self._index]
        self._index += 1
        return quote


@dataclass(frozen=True)
class DeliveryQuoteCollection:
    quotes: tuple[DeliveryQuote, ...]

    def __iter__(self) -> DeliveryQuoteIterator:
        return DeliveryQuoteIterator(self.quotes)

    def as_tuple(self) -> tuple[DeliveryQuote, ...]:
        return self.quotes


class QuoteFilterStrategy(ABC):
    @abstractmethod
    def keep(self, quote: DeliveryQuote) -> bool:
        raise NotImplementedError


class ModeFilterStrategy(QuoteFilterStrategy):
    def __init__(self, mode: DeliveryMode):
        self._mode = mode

    def keep(self, quote: DeliveryQuote) -> bool:
        return quote.mode is self._mode


class MaxPriceFilterStrategy(QuoteFilterStrategy):
    def __init__(self, max_price: float):
        self._max_price = max_price

    def keep(self, quote: DeliveryQuote) -> bool:
        return quote.total_price <= self._max_price


class MinSpeedFilterStrategy(QuoteFilterStrategy):
    def __init__(self, min_speed_kmh: float):
        self._min_speed_kmh = min_speed_kmh

    def keep(self, quote: DeliveryQuote) -> bool:
        return quote.speed_kmh >= self._min_speed_kmh


class NameContainsFilterStrategy(QuoteFilterStrategy):
    def __init__(self, substring: str):
        self._substring = substring.casefold()

    def keep(self, quote: DeliveryQuote) -> bool:
        return self._substring in quote.transport_name.casefold()


class CompositeFilterStrategy:
    def __init__(self, strategies: Iterable[QuoteFilterStrategy] = ()):
        self._strategies = tuple(strategies)

    def apply(self, quotes: DeliveryQuoteCollection) -> DeliveryQuoteCollection:
        filtered = tuple(
            quote
            for quote in quotes
            if all(strategy.keep(quote) for strategy in self._strategies)
        )
        return DeliveryQuoteCollection(filtered)


class SortDirection(Enum):
    ASC = "asc"
    DESC = "desc"


class QuoteSortStrategy(ABC):
    @abstractmethod
    def key(self, quote: DeliveryQuote) -> object:
        raise NotImplementedError

    @property
    def direction(self) -> SortDirection:
        return SortDirection.ASC


class TransportNameSortStrategy(QuoteSortStrategy):
    def __init__(self, direction: SortDirection = SortDirection.ASC):
        self._direction = direction

    def key(self, quote: DeliveryQuote) -> object:
        return quote.transport_name.casefold()

    @property
    def direction(self) -> SortDirection:
        return self._direction


class TotalPriceSortStrategy(QuoteSortStrategy):
    def __init__(self, direction: SortDirection = SortDirection.ASC):
        self._direction = direction

    def key(self, quote: DeliveryQuote) -> object:
        return quote.total_price

    @property
    def direction(self) -> SortDirection:
        return self._direction


class SpeedSortStrategy(QuoteSortStrategy):
    def __init__(self, direction: SortDirection = SortDirection.ASC):
        self._direction = direction

    def key(self, quote: DeliveryQuote) -> object:
        return quote.speed_kmh

    @property
    def direction(self) -> SortDirection:
        return self._direction


class CompositeSortStrategy:
    def __init__(self, strategies: Iterable[QuoteSortStrategy] = ()):
        self._strategies = tuple(strategies)

    def apply(self, quotes: DeliveryQuoteCollection) -> DeliveryQuoteCollection:
        sorted_quotes = list(quotes)
        for strategy in reversed(self._strategies):
            sorted_quotes.sort(
                key=strategy.key,
                reverse=strategy.direction is SortDirection.DESC,
            )
        return DeliveryQuoteCollection(tuple(sorted_quotes))
