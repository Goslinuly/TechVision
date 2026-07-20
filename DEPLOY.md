# Деплой

Один сервис: FastAPI + (опционально) Telegram-бот в long-polling.

## Переменные окружения (в панели Railway / systemd)

| Переменная                  | Обязательна | Назначение                         |
|-----------------------------|-------------|------------------------------------|
| `GOOGLE_FACTCHECK_API_KEY`  | да          | Google Fact Check Tools API        |
| `ANTHROPIC_API_KEY`         | нет         | включает реальный цикл Fable 5     |
| `TELEGRAM_BOT_TOKEN`        | нет         | включает бота (long-polling)       |
| `PUBLIC_BASE_URL`           | да          | базовый URL для ссылок на карточки |
| `ENABLE_OCR`                | нет         | OCR с фото (нужен tesseract)       |

## Railway

1. New Project → Deploy from GitHub → выбрать `Goslinuly/TechVision`.
2. Railway подхватит `railway.json` / `Dockerfile` автоматически.
3. Прописать переменные окружения (см. выше).
4. Healthcheck уже настроен на `/health`.
5. Скопировать публичный домен в `PUBLIC_BASE_URL` и передеплоить.

## Hetzner VPS (Docker)

```bash
docker build -t aqiqat .
docker run -d --name aqiqat -p 80:8000 --env-file .env aqiqat
```

## Telegram: polling vs webhook

- **Polling** (по умолчанию): ничего настраивать не нужно — бот стартует сам,
  если задан `TELEGRAM_BOT_TOKEN`.
- **Webhook** (прод): в `app/main.py` выставить `_USE_POLLING = False`, затем
  зарегистрировать вебхук у Telegram:
  ```bash
  curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=<PUBLIC_BASE_URL>/webhook/<TOKEN>"
  ```

## Проверка после деплоя

```bash
curl https://<домен>/health
curl -s https://<домен>/analyze -H 'content-type: application/json' \
     -d '{"text":"Средняя зарплата в РК превысила 400 тысяч тенге"}'
```
