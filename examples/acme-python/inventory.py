"""Tiny in-memory inventory. Stdlib only. Not a product plugin."""

from __future__ import annotations


class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None:
        self._stock = dict(stock or {"sku-1": 3})

    def get_qty(self, sku: str) -> int:
        return int(self._stock.get(sku, 0))

    def reserve(self, sku: str, qty: int) -> int:
        if qty < 1:
            raise ValueError("qty must be positive")
        have = self.get_qty(sku)
        if sku not in self._stock or have < qty:
            raise ValueError("insufficient")
        remaining = have - qty
        self._stock[sku] = remaining
        return remaining
