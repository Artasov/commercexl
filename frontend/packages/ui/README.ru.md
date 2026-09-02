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
