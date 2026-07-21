# Aqıqat — бот-помощник против информационного шума

**Трек:** Creative Content & Media (борьба с фейками, распознавание манипуляций)
**Языки:** казахский (kk) и русский (ru)

Aqıqat принимает пересланное в чат сообщение и вместо вердикта «97% фейк» даёт
**объяснимый разбор**: какие утверждения проверяемы, что нашлось в базах
фактчекеров, какие манипулятивные приёмы использованы — и как на это ответить.

> ⚠️ Мы честно не выносим вердикт «правда/ложь». Открытые детекторы дают ~78% AUC
> — врать пользователю точностью мы не будем. USP — объяснимость и локальный
> (казахстанский) контекст.

---

## Что это за репозиторий

End-to-end **скелет** MVP: он запускается целиком, имея только ключ Google Fact
Check API. Всё остальное (Anthropic, Telegram, KazLLM, эмбеддинги e5, pgvector)
подключается по мере готовности — без них работает детерминированный мок,
который всё равно вызывает **настоящий** Google Fact Check и локальные
инструменты.

```
Telegram (forward)                     FastAPI backend
      │  текст / фото→OCR                     │  webhook / /analyze
      ▼                                       ▼
  aiogram bot ──────────────────────►  ОРКЕСТРАТОР (Fable 5, tool-use)
      ▲                                       │  агентный цикл
      │  карточка + ссылка                    ▼  вызывает инструменты:
      │                        ┌──────────┬───────────┬────────────┬───────────┐
  Web-card (/r/{id}) ◄──ссылка─┤ Local    │ Google    │ Rhetoric   │ KazLLM    │
                               │ corpus   │ FactCheck │ analyzer   │ specialist│
                               │(Factcheck│ API (REAL)│ (spans)    │ (kk, stub)│
                               │  .kz)    │           │            │           │
                               └──────────┴───────────┴────────────┴───────────┘
```

### Почему это НЕ «пустая обёртка над API» (критерий 2)

Оркестратор (`app/orchestrator/`) — это **кастомный агентный цикл**, а не один
вызов модели:

1. **Классификация** сообщения: факт / мнение / манипуляция / смешанное.
2. **Декомпозиция** на атомарные проверяемые утверждения (claim extraction) —
   дешёвым Haiku 4.5, чтобы не жечь Fable 5.
3. **Маршрутизация каждого утверждения** через tool-use: Fable 5 сам решает,
   звать ли `search_local_corpus`, `google_factcheck`, `kazllm_specialist`.
4. **Синтез карточки** — структура §4, а не голый вердикт.

Ручной цикл tool-use живёт в `app/services/llm.py::run_tool_loop`.

---

## Быстрый старт

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # впишите ключи (минимум — Google Fact Check)

# 1) CLI-демо без сервера и без Telegram:
python -m scripts.demo
python -m scripts.demo "Врачи скрывают, что вакцина вызвала 5000 смертей в Алматы"

# 2) HTTP API + веб-карточка:
python run.py                 # http://localhost:8000
curl -s localhost:8000/analyze -H 'content-type: application/json' \
     -d '{"text":"Средняя зарплата в РК превысила 400 тысяч тенге"}' | jq
# откройте .url из ответа — это страница-разбор /r/{id}

# 3) Telegram-бот: впишите TELEGRAM_BOT_TOKEN в .env и запустите python run.py —
#    бот стартует в режиме long-polling автоматически.

# 4) Собрать реальный корпус Factcheck.kz (иначе используется демо-выборка):
python -m scripts.build_corpus --limit 30     # → data/factcheck_kz.json

# 5) Прогнать eval-набор (§4, adversarial):
python -m scripts.eval

# 6) (опц.) Семантический поиск на e5 + pgvector:
pip install sentence-transformers "psycopg[binary]" pgvector
#   в .env: EMBEDDINGS_ENABLED=true, DATABASE_URL=postgresql://...
python -m scripts.index_corpus            # эмбеддит корпус и грузит в pgvector

# 7) (опц.) KazLLM-8B специалист (llama.cpp):
llama-server -m kazllm-8b.gguf --port 8080
#   в .env: KAZLLM_BASE_URL=http://localhost:8080/v1
```

Проверить, какие бэкенды активны: `GET /health` → `search_backend`
(`pgvector` | `e5-inmemory` | `lexical`), `kazllm`, `llm_provider`.

### Режимы работы

| Ключ в `.env`               | Есть                          | Нет                              |
|-----------------------------|-------------------------------|----------------------------------|
| `GOOGLE_FACTCHECK_API_KEY`  | реальные фактчек-рейтинги      | инструмент возвращает пусто       |
| `ANTHROPIC_API_KEY`         | реальный цикл Fable 5 tool-use | детерминированный мок оркестратора|
| `TELEGRAM_BOT_TOKEN`        | бот принимает forward'ы        | бот не стартует (есть /analyze)   |

---

## Стек (§3 ТЗ)

| Слой            | Технология                         | Статус в скелете           |
|-----------------|------------------------------------|----------------------------|
| Бот             | Python + **aiogram 3**             | ✅ реализовано              |
| Бэкенд          | **FastAPI**                        | ✅ реализовано              |
| Оркестратор     | **Claude Fable 5** (tool-use)      | ✅ + мок-фолбэк             |
| Дешёвые подшаги | **Claude Haiku 4.5**               | ✅ (claim extraction)       |
| Внешний API     | **Google Fact Check Tools API**    | ✅ РЕАЛЬНО подключён        |
| Rhetoric        | правила + span'ы (kk/ru)           | ✅ реализовано              |
| Парсер Factcheck.kz | httpx + og-meta + verdict-метки | ✅ `scripts/build_corpus.py` |
| Локальная модель| **KazLLM-8B-GGUF** (llama.cpp)     | ✅ HTTP-интеграция (`KAZLLM_BASE_URL`), fallback-stub |
| Эмбеддинги      | **multilingual-e5** (ru+kk)        | ✅ опц. (`EMBEDDINGS_ENABLED`), fallback: лексика |
| Vector DB       | **pgvector** (Supabase)            | ✅ опц. (`DATABASE_URL`), fallback: локальный JSON |
| OCR             | **Tesseract** (kaz+rus)            | 🟡 опционально (`ENABLE_OCR`) |
| Веб-карточка    | FastAPI + Jinja2                   | ✅ реализовано              |

Пункты 🟡 — это второстепенные зависимости, честно помеченные как заглушки
(граница MVP, §1). Контракт функций совпадает с продовым — замена точечная.

---

## Что НЕ входит в MVP (§1, честно)

- Надёжная детекция дипфейков «загрузи видео → вердикт» (только демо на своём
  контенте, ограничение проговаривается со сцены).
- Проверка видео/аудио в проде.
- Автоматическая блокировка контента.

---

## Модель решения (§5)

- **Semantic retrieval:** cosine по эмбеддингам, порог τ (`local_corpus.TAU`).
  В скелете — Jaccard-скоринг как плейсхолдер под e5.
- **Confidence** = f(similarity, наличие в Google, ясность рейтинга источника) —
  формула в `orchestrator.compute_confidence`.
- **Rhetoric detection:** каталог приёмов (страх, цифра-без-источника, ложная
  дихотомия, апелляция к авторитету, «свои/чужие», срочность) с указанием
  span'а — `app/tools/rhetoric.py`.

### Структура затрат (Cost Structure)

- **Fable 5** ($10 / $50 за 1M ток.) вызывается **один раз** на сообщение —
  только маршрутизация + синтез.
- Извлечение claim'ов и классификация → **Haiku 4.5** ($1 / $5 за 1M).
- Поиск/эмбеддинги → локально, без API.
- Кэш вердиктов по хешу утверждения (`app/services/cache.py`) — повторяющиеся
  фейки не оплачиваются повторно.

---

## Структура кода

```
app/
  main.py                 FastAPI: /health /analyze /r/{id} /webhook/{token}
  bot.py                  aiogram-хендлеры (forward → карточка)
  presenter.py            рендер карточки (чат + подсветка span'ов для web)
  models.py               pydantic-контракт (Card, ClaimResult, Manipulation…)
  config.py               .env
  store.py                хранилище карточек + короткие id
  orchestrator/
    orchestrator.py       агентный цикл (LLM-путь + детерминированный мок)
    prompts.py            системные промпты + JSON-схемы (для TVEP)
    tools.py              tool-use схемы + dispatch
  services/
    llm.py                обёртка Anthropic (Fable 5 loop, Haiku substep)
    lang.py               определение kk/ru
    cache.py              кэш вердиктов по хешу
    ocr.py                Tesseract (опционально)
  tools/
    google_factcheck.py   РЕАЛЬНЫЙ Google Fact Check Tools API
    local_corpus.py       семантический поиск по Factcheck.kz
    rhetoric.py           детектор манипуляций со span'ами
  templates/card.html     веб-страница-разбор
data/factcheck_kz_sample.json   демо-корпус
scripts/demo.py           CLI end-to-end
```

---

## Комплаенс (§8)

- Все внешние зависимости (KazLLM, e5, API) явно указаны выше как dependencies.
- Дипфейк-демо — только на лицах/голосах членов команды, с согласия.
- Каждый участник понимает свой код.
