# @orcestr/commerce-ui

Нейтральные к платёжному провайдеру React-компоненты для checkout CommerceXL. Провайдеры остаются
отдельными пакетами; здесь находятся единая оболочка модального окна и явный выбор способа оплаты.

```bash
npm install @orcestr/commerce-ui @orcestr/ui
```

Один раз подключите `@orcestr/commerce-ui/styles.css` в корне приложения. До создания заказа
используйте `CommercePaymentMethodPicker`, а UI выбранного провайдера помещайте в единственный
`CommerceCheckoutDialog`.

Пакет не вычисляет цены и не принимает сумму от клиента. Показывайте только серверные варианты из
каталога, а в checkout отправляйте их стабильные идентификаторы.

## Подключение провайдера

Используйте `CommercePaymentMethodPicker` для всех доступных вариантов оплаты, а
`CommerceCheckoutDialog` оставляйте единственной модальной оболочкой. UI выбранного провайдера
встраивается внутрь этого окна, а не открывает отдельное модальное окно.

Для оплаты через Solana установите опубликованные provider-пакеты:

```bash
npm install @orcestr/commerce-solana-core @orcestr/commerce-solana-react @orcestr/commerce-solana-ui @tanstack/react-query
```

Подключите `@orcestr/commerce-solana-ui/styles.css` и отрисуйте `SolanaCheckout` внутри общего окна
с `showHeader={false}`. Solana UI автоматически создаёт новое короткоживущее действие для кошелька
и показывает QR-код, deep link и состояния платежа. Продукт можно разблокировать только после
authoritative backend-состояния `paid`; callback кошелька не является доказательством оплаты.

Полная схема backend, auth, realtime и finalized-проверки описана в
[руководстве CommerceXL](https://github.com/Artasov/commercexl/blob/master/src/commercexl/docs/HOW_TO_USE.md#6-compose-the-provider-neutral-checkout)
и документации [Orcestr Commerce Solana](https://github.com/Artasov/orcestr-commerce-solana).

## Сборка и локальное подключение

```bash
cd frontend
npm ci
npm run build
npm run pack:dry-run
```

В локальном Orcestr подключайте `../commercexl/frontend/packages/ui` через helper локальных
библиотек consumer-приложения до запуска dev server. Глобальный `npm link` не используйте.

Для релизов используются теги `commerce-ui-vX.Y.Z`. После первой ручной публикации, создающей
пакет в npm, следующие теги публикует workflow `CI/CD` через npm Trusted Publishing с provenance.
