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

CommerceXL предоставляет переиспользуемые примитивы товаров, позиций заказа, платежей и
балансов для приложений на FastAPI и SQLAlchemy. Приложение сохраняет контроль над DB engine,
сессиями, пользователями, авторизацией, миграциями и проектными payment callbacks.

## Статус

| Пункт | Значение |
| --- | --- |
| Пакет | `commercexl` |
| Версия | `0.2.0` |
| Статус | Beta |
| Runtime | Python 3.12+ |
| Frameworks | FastAPI, SQLAlchemy 2, Pydantic 2 |

Public API уже используется в приложениях Orcestr, но до первого стабильного major-релиза может
уточняться в рамках beta-версий.

## Что входит

| Зона | Содержимое |
| --- | --- |
| Каталог | переиспользуемые контракты товаров и границы сервисов |
| Checkout | DTO и сервисы заказов и позиций заказа |
| Платежи | настраиваемые payment providers и ручные платежи |
| Балансы | кредитные балансы пользователей и настройки конвертации валют |
| Промо | основы промокодов и подарочных сертификатов |
| HTTP | явная сборка FastAPI router через `create_router(...)` |
| Persistence | типизированные SQLAlchemy-модели через `CommerceBase` |

## Установка

```bash
pip install commercexl
```

Опциональные зависимости для разработки:

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
    payments=PaymentConfigBuilder(HandMadePaymentService),
)
```

## Интеграция с FastAPI

```python
from commercexl import CommerceHTTPConfig, CommerceUserActorDTO, create_router

app.include_router(
    create_router(
        CommerceHTTPConfig(
            get_db_session_dependency=get_db_session,
            get_current_user_dependency=get_current_user,
            get_commerce_module=lambda: commerce,
            build_actor=lambda user: CommerceUserActorDTO(id=user.id),
            get_user_id=lambda user: int(user.id),
            is_staff=lambda user: bool(user.is_staff),
        ),
    ),
    prefix="/api/v1",
)
```

## Миграции базы данных

CommerceXL не поставляет миграции приложения. Подключи metadata библиотеки к Alembic в основном
проекте и создавай миграции в репозитории приложения:

```python
from commercexl import CommerceBase
from my_project.db import Base

target_metadata = [Base.metadata, CommerceBase.metadata]
```

## Документация

- [Руководство по интеграции](./src/commercexl/docs/HOW_TO_USE.md)
- [Промокоды](./src/commercexl/docs/PROMOCODES.md)
- [Подарочные сертификаты](./src/commercexl/docs/GIFT_CERTIFICATES.md)
- [Руководство по релизу](./RELEASE_GUIDE.md)

## Разработка

```bash
uv sync --all-extras
uv run pytest -q
uv build
```

PyCharm run configurations для установки зависимостей, тестов, сборки и релизов находятся в
[`.run`](./.run).

## Лицензия

Проект распространяется по [Mozilla Public License 2.0](./LICENSE). Коммерческое использование
разрешено; изменения файлов под MPL остаются на условиях MPL. См. [NOTICE](./NOTICE) и
[TRADEMARKS.md](./TRADEMARKS.md).

## Экосистема Orcestr

- [Orcestr](https://orcestr.com)
- [Orcestr Auth](https://github.com/Artasov/orcestr-auth)
- [Orcestr UI](https://github.com/Artasov/orcestr-ui)
- [Orcestr Overview](https://github.com/Artasov/orcestr-overview)
