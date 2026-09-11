# Warehouse inventory reserve

Two leaves. Not a product-catalog numbering law.
Invariant INV-stock-never-negative: reserve never stores a negative on-hand quantity.

## INV-01 Reserve reduces on-hand quantity

### Functional
- Title: Reserve one unit of a known SKU
- Steps: Start with sku-1 quantity 3; reserve 1
- Expected: Remaining quantity is 2

### Negative
- Title: Reserve more than on-hand
- Steps: Reserve 99 of sku-1
- Expected: Rejected; quantity unchanged

- Invariant: INV-stock-never-negative holds after the refused reserve.

### Edge
- Title: Reserve the last unit
- Steps: Quantity is 1; reserve 1
- Expected: Remaining quantity is 0

## INV-02 Missing SKU or non-positive quantity

### Functional
- Title: Unknown SKU
- Steps: Reserve 1 of sku-missing
- Expected: Rejected; no new SKU created

### Negative
- Title: Quantity zero
- Steps: Reserve 0 of sku-1
- Expected: Rejected; quantity unchanged

### Edge
- Title: Negative quantity
- Steps: Reserve -1 of sku-1
- Expected: Rejected; quantity unchanged
