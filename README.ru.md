<p align="right">
  <a href="./README.md">English</a> · <strong>Русский</strong>
</p>

<p align="center">
  <a href="https://orcestr.com">
    <img src="./assets/orcestr-banner.webp" alt="Баннер CommerceXL" width="100%" />
  </a>
</p>

# CommerceXL

[![PyPI](https://img.shields.io/pypi/v/commercexl)](https://pypi.org/project/commercexl/)
[![CI](https://github.com/Artasov/commercexl/actions/workflows/ci.yml/badge.svg)](https://github.com/Artasov/commercexl/actions/workflows/ci.yml)
[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](./LICENSE)

Композиционная backend-основа коммерции для экосистемы [Orcestr](https://orcestr.com).

CommerceXL предоставляет переиспользуемые примитивы каталога, заказов, балансов и платежей для
FastAPI, Pydantic 2 и SQLAlchemy 2. Host-приложение владеет DB engine, сессиями, пользователями,
аутентификацией, CSRF-политикой, миграциями и callback-маршрутами конкретных провайдеров.

## Статус

| Пункт | Значение |
| --- | --- |
| Пакет | `commercexl` |
| Версия | `0.3.1` |
| Статус | Beta, breaking относительно 0.2 |
| Runtime | Python 3.12+ |
| Frameworks | FastAPI, SQLAlchemy 2, Pydantic 2 |

## Что входит

| Зона | Содержимое |
| --- | --- |
| Каталог | товары, точные decimal-цены и расширяемые product services |
| Заказы | несколько позиций и канонические состояния заказа/позиций |
| Платежи | canonical payment attempts, строгий registry и typed checkout actions |
| Lifecycle | идемпотентное создание, verification, cancel, refund и однократный product effect |
| Балансы | внутренние кредитные балансы и конвертация валют |
| Промо | основы промокодов и подарочных сертификатов |
| События | transactional payment outbox и глобальные claims provider evidence |
| HTTP | auth-neutral FastAPI router через `create_router(...)` |
| Persistence | типизированные SQLAlchemy-модели через `CommerceBase` |

В CommerceXL нет frontend, wallet-интеграции, blockchain verifier и секретов платежных провайдеров.
Это зона отдельных provider-библиотек и adapter-ов host-приложения.

## Установка

```bash
pip install commercexl
```

Опциональные зависимости:

```bash
pip install "commercexl[test]"
pip install "commercexl[dev]"
```

## Быстрый старт

```python
from decimal import Decimal

from commercexl import (
    BaseConfig,
    CommerceModule,
    DefaultOrderItemService,
    HandMadePaymentService,
    PaymentConfigBuilder,
    PaymentProviderRegistration,
    ProductOrderConfig,
    ProductOrderConfigBuilder,
)


class ProjectCommerceConfig(BaseConfig):
    PAYMENT_SYSTEMS = {"USD": ("handmade",)}
    MIN_TOP_UP_AMOUNTS = {"USD": Decimal("1")}
    CREDITS_CONVERTERS = {"USD": Decimal("10000")}


commerce = CommerceModule(
    config_class=ProjectCommerceConfig,
    product_orders=ProductOrderConfigBuilder(
        ProductOrderConfig(MyProductService, DefaultOrderItemService),
    ),
    payments=PaymentConfigBuilder(
        PaymentProviderRegistration(
            system="handmade",
            provider_kind="handmade",
            factory=HandMadePaymentService,
        ),
    ),
    public_base_url="https://commerce.example.com",
)
```

Регистрация строгая: duplicate нормализованной `system`, отсутствующий provider из
`PAYMENT_SYSTEMS` или фабрика с неправильным типом результата останавливают сборку модуля.

## Интеграция с FastAPI

Host передаёт dependency аутентифицированного actor и обязательный mutation guard. При cookie-auth
mutation guard должен быть CSRF dependency host-приложения.

```python
from fastapi import Depends
from commercexl import CommerceHTTPConfig, CommerceUserActorDTO, create_router


async def get_commerce_actor(user=Depends(get_current_user)) -> CommerceUserActorDTO:
    return CommerceUserActorDTO(id=user.id, permissions=frozenset(user.permissions))


app.include_router(
    create_router(
        CommerceHTTPConfig(
            get_db_session_dependency=get_db_session,
            get_current_actor_dependency=get_commerce_actor,
            get_mutation_guard_dependency=check_csrf,
            get_commerce_module=lambda: commerce,
        ),
    ),
    prefix="/api/v1",
)
```

Checkout намеренно разделён на две фазы:

1. `POST /orders/` создаёт server-priced заказ и требует `Idempotency-Key`.
2. `GET /orders/{order_id}/payment-options/` возвращает доступные actor варианты.
3. `POST /orders/{order_id}/payment-attempts/` принимает только `payment_option_id` и отдельный
   `Idempotency-Key`.
4. `GET /payments/{payment_public_id}/` возвращает authoritative state без выдачи секрета.
5. `POST /payments/{payment_public_id}/checkout-action/` выпускает новое provider action.

В Python суммы представлены `Decimal`, в JSON — decimal strings. Клиент не может передать итоговую
сумму, коммерческую валюту или произвольную payment system при создании попытки.

## Контракт провайдера

Provider-библиотека реализует `AbstractPaymentService` или `AbstractCallbackPaymentService` и
регистрируется через `PaymentProviderRegistration`. Стабильные provider-facing imports:
`PaymentCreateContext`, `PaymentCreateResult`, `PaymentOption`, `CheckoutAction`,
`PaymentVerificationResult` и `PaymentState`.

Каноническая `PaymentORM` остаётся extension root дочерних provider-таблиц. Провайдер не меняет
заказ и не помечает его оплаченным напрямую. Доверенный callback/reconciliation adapter возвращает
typed verification и передаёт его в `PaymentRuntime.apply_verification(...)` в текущей DB session.

Capability URL и bearer transaction request выдаёт `get_action(...)`; core хранит только
несекретные action metadata. Безопасный evidence имеет глобальную уникальность, а каждое изменение
платежа создаёт `PaymentOutboxEventORM` в той же транзакции.

## Миграции базы данных

CommerceXL не поставляет миграции приложения. Подключи metadata библиотеки к Alembic и создавай
проверенные миграции в host-репозитории:

```python
from commercexl import CommerceBase
from my_project.db import Base

target_metadata = [Base.metadata, CommerceBase.metadata]
```

Версия 0.3 намеренно ломает старую schema/API. До обновления production data выполни
[руководство миграции 0.2 → 0.3](./src/commercexl/docs/MIGRATION_0_3.md).

## Документация

- [Руководство по интеграции](./src/commercexl/docs/HOW_TO_USE.md)
- [Миграция на 0.3](./src/commercexl/docs/MIGRATION_0_3.md)
- [Промокоды](./src/commercexl/docs/PROMOCODES.md)
- [Подарочные сертификаты](./src/commercexl/docs/GIFT_CERTIFICATES.md)
- [Руководство по релизу](./RELEASE_GUIDE.md)

## Разработка

```bash
uv sync --all-extras
uv run pytest -q
uv build
```

## Лицензия

Проект распространяется по [Mozilla Public License 2.0](./LICENSE). Коммерческое использование
разрешено; изменения MPL-файлов остаются под MPL. См. [NOTICE](./NOTICE) и
[TRADEMARKS.md](./TRADEMARKS.md).

## Экосистема Orcestr

- [Orcestr](https://orcestr.com)
- [Orcestr Auth](https://github.com/Artasov/orcestr-auth)
- [Orcestr UI](https://github.com/Artasov/orcestr-ui)
- [Orcestr OS](https://github.com/Artasov/orcestr-os)
