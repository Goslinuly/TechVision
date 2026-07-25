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

## Прод (что реально запущено)

| | |
|---|---|
| Бэкенд + веб-карточка | https://web-production-50fcb.up.railway.app |
| Telegram-бот | https://t.me/Aqiqat_check_bot |
| Оркестратор на проде | **Groq · Llama 3.3 70B** (`llama-3.3-70b-versatile`) |
| Проверить конфигурацию живьём | `GET /health` → `llm_provider`, `orchestrator_model`, `search_backend`, `kazllm` |
| Соц-эффект живьём | `GET /metrics` |

`/health` — источник истины по тому, что крутится. Если он отдаёт
`llm_provider: groq` — значит на проде Groq, и схема ниже это отражает.
Anthropic (Fable 5 + Haiku 4.5) — поддерживаемая альтернативная конфигурация
того же цикла, переключается одной переменной `LLM_PROVIDER`.

---

## Что это за репозиторий

End-to-end MVP: он запускается целиком, имея только ключ Google Fact
Check API. Всё остальное (LLM-провайдер, Telegram, KazLLM, эмбеддинги e5,
pgvector) подключается по мере готовности — без них работает детерминированный
путь, который всё равно вызывает **настоящий** Google Fact Check и локальные
инструменты.

```
Telegram (forward)                       FastAPI backend
      │  текст / фото→OCR                       │  webhook / /analyze
      ▼                                         ▼
  aiogram bot ──────────────────────►  ОРКЕСТРАТОР — агентный tool-use цикл
      ▲                                    │  прод:  Groq · Llama 3.3 70B
      │  карточка + ссылка                 │  опц.:  Claude Fable 5 + Haiku 4.5
      │                                    │  без ключа: детерминированный путь
      │                                    ▼  модель сама выбирает инструменты:
      │        ┌──────────┬───────────┬────────────┬───────────┬─────────────┐
  Web-card ◄───┤ Local    │ Google    │ Rhetoric   │ KazLLM-8B │ Image       │
  (/r/{id})    │ corpus   │ FactCheck │ analyzer   │ (kk-конт.)│ forensics   │
               │(Factcheck│ API (REAL)│ (spans)    │(llama.cpp)│ (ELA/EXIF,  │
               │  .kz)    │           │            │           │ 2-й сигнал) │
               └──────────┴───────────┴────────────┴───────────┴─────────────┘
```

Схема выше = то, что показывает `/health`. Та же схема идёт на стр. 2 паспорта
TVEP (`TVEP.md`) — расхождений «паспорт ↔ код ↔ прод» нет.

### Почему это НЕ «пустая обёртка над API» (критерий 2)

Оркестратор (`app/orchestrator/`) — это **кастомный агентный цикл**, а не один
вызов модели, и он **не зависит от вендора**:

1. **Классификация** сообщения: факт / мнение / манипуляция / смешанное.
2. **Декомпозиция** на атомарные проверяемые утверждения (claim extraction) —
   дешёвым подшагом (`complete_json`): на Anthropic это Haiku 4.5, на Groq —
   та же Llama 3.3 с `response_format: json_object`.
3. **Маршрутизация каждого утверждения** через tool-use: модель сама решает,
   звать ли `search_local_corpus`, `google_factcheck`, `analyze_rhetoric`,
   `kazllm_specialist`.
4. **Синтез карточки** — структура §4, а не голый вердикт.

Ручной цикл tool-use живёт в `app/services/llm.py::run_tool_loop` — по одной
реализации на провайдера (Groq: OpenAI-совместимые `tool_calls`; Anthropic:
`tool_use`/`tool_result`), но контракт для оркестратора один. Именно поэтому
смена провайдера не меняет ни архитектуру, ни выходной `Card`.

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

| Ключ в `.env`               | Есть                            | Нет                               |
|-----------------------------|---------------------------------|-----------------------------------|
| `GOOGLE_FACTCHECK_API_KEY`  | реальные фактчек-рейтинги        | инструмент возвращает пусто        |
| `GROQ_API_KEY`              | **прод-конфигурация:** цикл tool-use на Llama 3.3 70B | падаем на Anthropic, если есть его ключ |
| `ANTHROPIC_API_KEY`         | цикл tool-use на Fable 5 + Haiku 4.5 подшаги | используется Groq либо детерминированный путь |
| ни одного LLM-ключа         | —                               | детерминированный путь: те же реальные инструменты, тот же `Card` |
| `TELEGRAM_BOT_TOKEN`        | бот принимает forward'ы          | бот не стартует (есть /analyze)    |

Приоритет провайдера задаётся `LLM_PROVIDER` (`auto` | `groq` | `anthropic` |
`mock`, см. `app/config.py::active_provider`). `auto` — текущий прод: сначала
Groq (бесплатный tier), затем Anthropic, затем детерминированный путь.
Фактически выбранный провайдер всегда виден в `/health`.

---

## Стек (§3 ТЗ)

| Слой            | Технология                         | Статус в скелете           |
|-----------------|------------------------------------|----------------------------|
| Бот             | Python + **aiogram 3**             | ✅ реализовано              |
| Бэкенд          | **FastAPI**                        | ✅ реализовано              |
| Оркестратор (прод) | **Groq · Llama 3.3 70B** (tool-use) | ✅ работает на проде, см. `/health` |
| Оркестратор (альт.) | **Claude Fable 5** (tool-use)   | ✅ тот же цикл по `LLM_PROVIDER=anthropic` |
| Дешёвые подшаги | **Haiku 4.5** / Llama 3.3 `json_object` | ✅ (claim extraction)   |
| Фолбэк без ключей | детерминированный путь оркестратора | ✅ тот же контракт `Card` |
| Внешний API     | **Google Fact Check Tools API**    | ✅ РЕАЛЬНО подключён        |
| Rhetoric        | правила + span'ы (kk/ru)           | ✅ реализовано              |
| Парсер Factcheck.kz | httpx + og-meta + verdict-метки | ✅ `scripts/build_corpus.py` |
| Локальная модель| **KazLLM-8B-GGUF** (llama.cpp)     | ✅ HTTP-интеграция (`KAZLLM_BASE_URL`), fallback-stub |
| Эмбеддинги      | **multilingual-e5** (ru+kk)        | ✅ опц. (`EMBEDDINGS_ENABLED`), fallback: лексика |
| Vector DB       | **pgvector** (Supabase)            | ✅ опц. (`DATABASE_URL`), fallback: локальный JSON |
| OCR             | **Tesseract** (kaz+rus)            | 🟡 опционально (`ENABLE_OCR`) |
| Сигнал по фото  | ELA/EXIF (Pillow)                  | 🟡 второстепенный сигнал, не вердикт (`/image-signal`) |
| Веб-карточка    | FastAPI + Jinja2                   | ✅ реализовано (`/`, `/r/{id}`) |
| Метрики эффекта | in-process счётчики                | ✅ `/metrics`               |

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
  По умолчанию — лексический fallback (Jaccard), e5/pgvector по флагам.
- **Confidence** = f(similarity, наличие в Google, ясность рейтинга источника) —
  формула в `orchestrator.compute_confidence`:
  `0.5·min(1, sim/τ) + 0.45·[есть вердикт в Google]`.
  Максимум по формуле — **0.95, а не 1.0**, и это сделано намеренно: 1.0 значило
  бы «машина уверена абсолютно», а мы этого не утверждаем нигде в продукте (тот
  же принцип, что и отказ от «97% фейк»). Оставшиеся 0.05 — то, что закрывает
  только человек-фактчекер. Подробнее — `MODELING.md §3`.
- **Rhetoric detection:** каталог приёмов (страх, цифра-без-источника, ложная
  дихотомия, апелляция к авторитету, «свои/чужие», срочность) с указанием
  span'а — `app/tools/rhetoric.py`.

### Структура затрат (Cost Structure)

Две конфигурации — обе рабочие, разница только в цене одного разбора:

| Конфигурация | Оркестратор | ~Цена одного разбора |
|---|---|---|
| **Текущая (прод)** | Groq · Llama 3.3 70B | **≈ $0.004** (на free tier — $0) |
| **На фронтир-модели** | Claude Fable 5 + Haiku 4.5 | **≈ $0.10** |

То есть вилка ×25: прод сегодня практически бесплатен, а если качество
потребует фронтир-модели, порядок затрат заранее известен и всё равно
выдерживается. Полный расчёт с ценами за 1M токенов — `COSTS.md`.

Архитектурные митигации (одинаковы для обеих конфигураций):

- Оркестратор вызывается **один раз** на сообщение — только маршрутизация +
  синтез.
- Извлечение claim'ов и классификация → дешёвый подшаг (`complete_json`).
- Поиск/эмбеддинги → локально, без API.
- Кэш вердиктов по хешу утверждения (`app/services/cache.py`) — повторяющиеся
  фейки не оплачиваются повторно.

---

## Структура кода

```
app/
  main.py                 FastAPI: / /health /analyze /r/{id} /metrics
                          /image-signal /webhook/{token}
  bot.py                  aiogram-хендлеры (forward → карточка, /help, kk/ru)
  presenter.py            рендер карточки (чат + подсветка span'ов для web)
  models.py               pydantic-контракт (Card, ClaimResult, Manipulation…)
  config.py               .env + выбор провайдера (active_provider)
  store.py                хранилище карточек + короткие id
  orchestrator/
    orchestrator.py       агентный цикл (LLM-путь + детерминированный путь),
                          compute_confidence
    prompts.py            системные промпты + JSON-схемы (для TVEP)
    tools.py              tool-use схемы TOOL_SCHEMAS + dispatch
  services/
    llm.py                провайдеры Groq / Anthropic / mock, run_tool_loop
    embeddings.py         multilingual-e5, префиксы query/passage, cosine
    vectorstore.py        pgvector-поиск (Postgres/Supabase)
    kazllm.py             KazLLM-8B через llama.cpp (казахский контекст)
    image_forensics.py    ELA/EXIF — второстепенный сигнал по фото
    metrics.py            счётчики соц-эффекта для /metrics
    lang.py               определение kk/ru
    cache.py              кэш вердиктов по хешу
    ocr.py                Tesseract (опционально)
  tools/
    google_factcheck.py   РЕАЛЬНЫЙ Google Fact Check Tools API
    factcheck_parser.py   парсер Factcheck.kz (og-meta, метки вердикта, дедуп)
    local_corpus.py       retrieval: pgvector | e5-inmemory | лексика
    rhetoric.py           детектор манипуляций со span'ами
  templates/
    index.html            лендинг с живой формой разбора (RU/KK)
    card.html             веб-страница-разбор
data/factcheck_kz_sample.json   демо-корпус (+ factcheck_kz.json от парсера)
data/eval_set.json        размеченный eval-набор (12 кейсов)
scripts/demo.py           CLI end-to-end
scripts/build_corpus.py   сборка корпуса Factcheck.kz
scripts/index_corpus.py   эмбеддинг корпуса → pgvector
scripts/eval.py           precision/recall/F1 (см. EVAL.md)
```

---

## Команда и зоны ответственности

Кто какой код защищает на Q&A — `CODE_OWNERSHIP.md` (4 роли по §6 ТЗ), сводка
вопросов и ответов — `QA_PREP.md`. Правило переключения на Q&A: модель → №1,
данные → №3, деньги/устойчивость → №4, деплой/безопасность → №2.

## Документы к защите

| Документ | О чём |
|---|---|
| `TVEP.md` | паспорт проекта, 3 страницы (боль/USP · архитектура · математика и затраты) |
| `TVEP_CHECKLIST.md` | сверка «раздел паспорта ↔ файлы в коде» |
| `MODELING.md` | модель решения: retrieval, confidence, вердикты, манипуляции |
| `COSTS.md` | структура затрат: текущая конфигурация и фронтир-модель |
| `EVAL.md` | eval-набор и метрики (12 кейсов, sanity-check) |
| `SECURITY.md` | модель угроз, секреты, промпт-инъекции |
| `SUSTAINABILITY.md` | соц-эффект, монетизация, масштабирование |
| `DEMO_SCRIPT.md` | отрепетированное демо на 4 минуты + чек-лист стабильности |
| `CODE_OWNERSHIP.md` | зоны кода по ролям для Q&A |
| `DEPLOY.md` | деплой на Railway / Docker |

---

## Комплаенс (§8)

- Все внешние зависимости (KazLLM, e5, API) явно указаны выше как dependencies.
- Дипфейк-демо — только на лицах/голосах членов команды, с согласия.
- Каждый участник понимает свой код.
- **Лицензии.** Наш код — MIT (`LICENSE`). Сторонние компоненты и их
  ограничения — `LICENSE` §«Сторонние компоненты»; ключевое: веса KazLLM-8B
  (ISSAI) под **CC-BY-NC**, поэтому коммерческая версия — на модели без
  NC-ограничения (`SUSTAINABILITY.md §7`), архитектура при этом не меняется.
