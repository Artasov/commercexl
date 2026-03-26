# PROMOCODES

`Promocode` validates a promocode and calculates the discounted amount.

Main service:

```python
Promocode
```

Main methods:

```python
async def can_apply(session, user_id, code, product_id, currency) -> PromocodeDTO
async def calc_promocode_amount(session, promocode_id, user_id, product_id, currency, original_amount) -> Decimal
```

Use `can_apply()` when UI or API just wants to validate a promocode before order creation.

Use `calc_promocode_amount()` when you already build or recalculate the order amount.

The service checks:

- promocode exists
- promocode already started
- promocode is not expired
- promocode is allowed for the product
- promocode is allowed for the currency
- specific user restriction
- total usage limit
- per-user usage limit
- interval between repeated usages
