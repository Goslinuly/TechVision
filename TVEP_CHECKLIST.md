# TVEP Checklist · соответствие кода паспорту (Aqıqat)

Таблица сверки «раздел паспорта TVEP / ТЗ ↔ реализация в коде». Составлена по
`TZ_TechVision_Zone13.md` и `MODELING.md`, для Критерия финала 2 (соответствие
кода паспорту). Каждый раздел ТЗ отображён на конкретные файлы — жюри может
открыть и проверить.

**Сам паспорт — `TVEP.md`** (3 страницы: боль/USP · архитектура · математика и
затраты). Этот файл — сверка паспорта с кодом, а не замена паспорта.

Все пути указаны от корня репозитория.

---

## Раздел 0 · Боль / проблема («один пользователь — одна боль», стр. 1 TVEP)

Пользователь получил «новость» в чат на kk/ru и не знает, как проверить и что
ответить. USP — не бинарный вердикт, а объяснимый разбор.

| Что | Файлы |
|---|---|
| Формулировка боли и USP (текст) | `TVEP.md` стр. 1, `TZ_TechVision_Zone13.md` §0, `README.md` |
| Приём пересланного текста, тон «разбор, не вердикт» | `app/bot.py` (`_WELCOME`, `_HELP`, `on_message`) |
| Принцип «не 97% фейк, а разбор» в логике | `app/orchestrator/orchestrator.py` (`analyze`), `MODELING.md` §1 |

---

## Раздел 1 · Границы MVP

Входит: приём текста (и OCR из фото), оркестратор, локальный корпус + Google,
разбор манипуляций, карточка, kk/ru. Не входит: надёжные дипфейки, видео/аудио,
автоблокировка.

| Что | Файлы |
|---|---|
| Приём текста в бот | `app/bot.py` (`on_message`) |
| OCR из фото (опционально, `ENABLE_OCR`) | `app/services/ocr.py`, `app/bot.py`, `app/main.py` (`/analyze`, `/image-signal`) |
| Определение языка kk/ru | `app/services/lang.py` |
| Дипфейк как **второстепенный сигнал**, не вердикт | `app/services/image_forensics.py`, `MODELING.md` §6 |
| Явная фиксация границ MVP | `README.md`, `TZ_TechVision_Zone13.md` §1 |

---

## Раздел 2 · Архитектура (Bot → FastAPI → Оркестратор → инструменты)

Схема паспорта — `TVEP.md` стр. 2; она дословно совпадает со схемой в `README.md`
и проверяется живьём через `GET /health` (`llm_provider`, `orchestrator_model`,
`search_backend`, `kazllm`, `image_signal`). На момент сдачи прод-оркестратор —
Groq · Llama 3.3 70B; конфигурация на Claude Fable 5 включается через
`LLM_PROVIDER=anthropic` без изменения цикла.

| Компонент архитектуры | Файлы |
|---|---|
| Выбор LLM-провайдера (прод Groq / альт. Anthropic / детерминированный путь) | `app/config.py` (`active_provider`), `app/services/llm.py` (`_GroqBackend`, `_AnthropicBackend`, `LLMClient`), `tests/test_provider.py` |
| Сверка «схема ↔ реальность» одним запросом | `app/main.py` (`/health`) |
| Telegram-бот (aiogram 3), forward-приём | `app/bot.py` |
| FastAPI backend: webhook, `/analyze`, web-card, `/health` | `app/main.py` |
| Оркестратор (агентный цикл) | `app/orchestrator/orchestrator.py` |
| Веб-карточка (статика для шаринга обратно в чат) | `app/templates/card.html`, `app/templates/index.html`, `app/presenter.py`, `app/main.py` (`/r/{id}`) |
| Хранилище карточек + шаринговые ссылки | `app/store.py`, `app/models.py` (`Card.url`) |
| Инструменты: Vector DB, Google, Rhetoric, KazLLM | `app/tools/local_corpus.py`, `app/tools/google_factcheck.py`, `app/tools/rhetoric.py`, `app/services/kazllm.py` |

---

## Раздел 2.1 · Агентный цикл оркестратора («не пустая обёртка над API»)

Кастомный цикл: классификация → декомпозиция на атомарные утверждения →
маршрутизация каждого через tool-use → синтез карточки.

| Шаг цикла | Файлы |
|---|---|
| Точка входа `analyze(text) → Card` | `app/orchestrator/orchestrator.py` (`analyze`) |
| Шаг 1–2: классификация + декомпозиция на claims | `orchestrator.py` (`_extract`, `_mock_extract`), `app/orchestrator/prompts.py` (`EXTRACT_SYSTEM`, `EXTRACT_SCHEMA`) |
| Шаг 3: маршрутизация через tool-use (модель сама выбирает инструмент) | `orchestrator.py` (`_analyze_llm`), `app/services/llm.py` (`run_tool_loop`), `app/orchestrator/prompts.py` (`ORCHESTRATOR_SYSTEM`) |
| Определения инструментов и dispatch | `app/orchestrator/tools.py` (`TOOL_SCHEMAS`, `dispatch`, `search_local_corpus`/`google_factcheck`/`analyze_rhetoric`/`kazllm_specialist`) |
| Шаг 4: синтез карточки (структура, не вердикт) | `orchestrator.py` (`analyze` → `Card`), `app/presenter.py` |
| Устойчивость: детерминированный fallback при сбое/лимите LLM | `orchestrator.py` (`_resolve_claim`, `_mock_reply_suggestion`, ветки `except`) |
| Промпты — дословно для паспорта | `app/orchestrator/prompts.py` |
| Тесты цикла | `tests/test_orchestrator.py` |

---

## Раздел 2.2 · KazLLM (локальный контекст, USP)

KazLLM-8B вызывается оркестратором как специалист по казахскому (идиомы,
локальные сущности, диалекты).

| Что | Файлы |
|---|---|
| Интеграция KazLLM (llama.cpp, OpenAI-совместимый) | `app/services/kazllm.py` (`available`, `explain`) |
| Инструмент `kazllm_specialist` в цикле | `app/orchestrator/tools.py` |
| Конфиг (`KAZLLM_BASE_URL`, модель) | `app/config.py` |
| Флаг в health | `app/main.py` (`/health` → `kazllm`) |

---

## Раздел 3 · Стек технологий

| Слой (ТЗ §3) | Технология | Файлы |
|---|---|---|
| Бот | aiogram 3 | `app/bot.py`, `requirements.txt` |
| Бэкенд | FastAPI | `app/main.py`, `run.py`, `requirements.txt` |
| Оркестратор | Fable 5 / Groq Llama 3.3, tool-use | `app/services/llm.py`, `app/orchestrator/*` |
| Дешёвые подшаги | Haiku / Groq (`complete_json`) | `app/services/llm.py`, `app/config.py` (`substep_model`) |
| Локальная модель | KazLLM-8B | `app/services/kazllm.py` |
| Эмбеддинги | multilingual-e5 | `app/services/embeddings.py` |
| Vector DB | pgvector (Postgres/Supabase) | `app/services/vectorstore.py`, `app/tools/local_corpus.py` |
| Внешний API | Google Fact Check Tools | `app/tools/google_factcheck.py` |
| OCR | Tesseract / Vision | `app/services/ocr.py` |
| Веб-карточка | FastAPI + Jinja2 (статика) | `app/templates/*`, `app/presenter.py` |
| Деплой | Railway | `Dockerfile`, `Procfile`, `railway.json`, `DEPLOY.md` |
| Кэш / стоимость | кэш по хешу утверждения | `app/services/cache.py`, `COSTS.md` |

---

## Раздел 4 · Формат карточки-разбора

Структура: проверяемые утверждения + вердикты, манипулятивные приёмы с
подсветкой, «как можно ответить», ссылка на веб-разбор.

| Элемент карточки | Файлы |
|---|---|
| Модель карточки (`Card`, `ClaimResult`, `Manipulation`, `Evidence`) | `app/models.py` |
| Вердикты и эмодзи (❌/✅/⚠️/💭) | `app/models.py` (`Verdict`, `VERDICT_EMOJI`) |
| Краткая карточка в чат | `app/presenter.py` (`chat_card`), `app/bot.py` |
| Веб-страница разбора + подсветка фраз | `app/templates/card.html`, `app/presenter.py` (`web_card_context`, `highlight_source`) |
| «Как можно ответить» (reply_suggestion) | `orchestrator.py` (`_mock_reply_suggestion`, поле в `ORCHESTRATOR_SYSTEM`) |
| Шаринговая ссылка `/r/{id}` | `app/main.py` (`web_card`), `app/store.py`, `app/models.py` (`Card.url`) |

---

## Раздел 5 · Модель решения и структура затрат

### Алгоритмическая модель

| Что (ТЗ §5) | Файлы |
|---|---|
| Semantic retrieval, порог τ | `app/tools/local_corpus.py`, `app/services/embeddings.py`, `app/config.py` (`tau_cosine`), `MODELING.md` §2 |
| Формула confidence (выписана явно) | `orchestrator.py` (`compute_confidence`), `MODELING.md` §3 |
| Маппинг рейтинг источника → вердикт | `app/tools/google_factcheck.py`, `app/tools/factcheck_parser.py`, `MODELING.md` §4 |
| Rhetoric detection (правила + span) | `app/tools/rhetoric.py`, `MODELING.md` §5 |
| Метрики (доказательная база эффекта) | `app/services/metrics.py`, `app/main.py` (`/metrics`), `scripts/eval.py`, `data/eval_set.json`, `EVAL.md` |

### Структура затрат (Cost Structure)

| Что | Файлы |
|---|---|
| Разбор затрат в двух конфигурациях (текущая Groq ≈$0.004 / фронтир ≈$0.10 за разбор) + хостинг + self-hosted KazLLM | `COSTS.md`, `TVEP.md` стр. 3 §6, `README.md` («Структура затрат») |
| Митигация стоимости: оркестратор один раз на сообщение, декомпозиция дешёвым подшагом | `app/services/llm.py` (`run_tool_loop` vs `complete_json`), `orchestrator.py` (`_extract` vs `_analyze_llm`) |
| Кэш вердиктов по хешу | `app/services/cache.py` |
| Работа при цене API $0 (лимит/сбой LLM) | `orchestrator.py` (ветки `except`, `_resolve_claim`) |

---

## Раздел 8 · Комплаенс и безопасность

| Пункт | Файлы |
|---|---|
| Зависимости явно указаны | `README.md`, `requirements.txt`, `requirements-dev.txt` |
| Лицензия проекта и лицензии сторонних компонентов (KazLLM — CC-BY-NC) | `LICENSE`, `SUSTAINABILITY.md §7`, `COSTS.md` |
| Дипфейк-демо только на своём материале, как сигнал | `app/services/image_forensics.py`, `MODELING.md` §6 |
| Модель угроз, секреты, ротация ключей, промпт-инъекции | `SECURITY.md` |
| Валидация и лимиты ввода + тесты | `app/main.py` (`MAX_INPUT_CHARS`), `app/bot.py` (`_MAX_INPUT`), `tests/test_api_limits.py` |
| Секреты вне git, не логируются | `.gitignore`, `app/config.py`, `.env.example` |
| Непрерывность разработки | git-лог репозитория |

---

## Как проверить сборку

```bash
python3 -m pytest -q      # офлайн, детерминированно (tests/conftest.py форсит mock)
```

Все разделы паспорта, помеченные выше, покрыты кодом и тестами; расхождений
«паспорт ↔ код» на момент сдачи нет.
