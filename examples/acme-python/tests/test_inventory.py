"""Stdlib unittest for examples/acme-python/inventory.py."""

from __future__ import annotations

import unittest

from inventory import Inventory


class InventoryTests(unittest.TestCase):
    def test_reserve_reduces_quantity(self) -> None:
        stock = Inventory({"sku-1": 3})
        self.assertEqual(stock.reserve("sku-1", 1), 2)
        self.assertEqual(stock.get_qty("sku-1"), 2)

    def test_reserve_last_unit(self) -> None:
        stock = Inventory({"sku-1": 1})
        self.assertEqual(stock.reserve("sku-1", 1), 0)

    def test_over_reserve_rejected(self) -> None:
        stock = Inventory({"sku-1": 3})
        with self.assertRaises(ValueError):
            stock.reserve("sku-1", 99)
        self.assertEqual(stock.get_qty("sku-1"), 3)

    def test_missing_sku_rejected(self) -> None:
        stock = Inventory({"sku-1": 3})
        with self.assertRaises(ValueError):
            stock.reserve("sku-missing", 1)
        self.assertEqual(stock.get_qty("sku-missing"), 0)

    def test_non_positive_qty_rejected(self) -> None:
        stock = Inventory({"sku-1": 3})
        with self.assertRaises(ValueError):
            stock.reserve("sku-1", 0)
        with self.assertRaises(ValueError):
            stock.reserve("sku-1", -1)
        self.assertEqual(stock.get_qty("sku-1"), 3)


if __name__ == "__main__":
    unittest.main()
