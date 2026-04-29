# Цунамис Mobile

Первый Expo-прототип iPhone-приложения для сайта Цунамис.

## Что уже есть

- вход по API-токену;
- сохранение токена в `AsyncStorage`;
- восстановление сессии при запуске;
- список соревнований из `/api/v1/competitions/`;
- выход с отзывом текущего токена.

## Запуск

```powershell
cd C:\Users\Оксана\Documents\Projects\trannig_platform\mobile
npm install
npm start
```

По умолчанию приложение ходит на:

```text
https://xn--80aqlcxhu.xn--p1ai/api/v1
```

Для локального Django-сервера нужно будет заменить `DEFAULT_API_URL` в
`src/api.ts`, например на адрес компьютера в локальной сети.
