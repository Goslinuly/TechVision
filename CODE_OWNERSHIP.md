# Карта владения кодом · Aqıqat

Документ по **Критерию финала 4** — «участие ВСЕХ разработчиков в Q&A, а не
только спикера». Распределяет ответственность за код по 4 ролям команды из
`TZ_TechVision_Zone13.md §6`, чтобы на защите отвечал профильный человек, а не
один спикер за всех. Правило переключения (из §6): вопрос про модель → №1,
данные → №3, деньги/устойчивость → №4, деплой/безопасность → №2.

> ⚠️ **Честная оговорка.** Это **заготовка распределения защиты**, а не
> подтверждение авторства. Реальные коммиты каждого участника в свою зону
> (`git log --author`), понимание своего кода (санкция по §8 ТЗ — до 0 баллов
> по критерию 2) и репетиция переключения — **за командой**. Файл говорит, кто
> ЧТО должен уметь защитить, а не кто это фактически написал. Сверьте зоны с
> реальной историей коммитов до финала.

Сводка вопросов и опор по темам — в `QA_PREP.md` (ссылки вида A1, B3 ниже
указывают на него).

---

## Роль №1 — AI / Backend

**Владеет и защищает:** оркестратор, агентный tool-use цикл, RAG-цепочка,
промпты, формула confidence, LLM-обёртки и fallback.

**Файлы/модули:**
- `app/orchestrator/orchestrator.py` — агентный цикл `analyze`, шаги 1–5,
  `compute_confidence`, `_verdict_from_sources`, детерминированный путь
  (`_mock_extract`, `_resolve_claim`).
- `app/orchestrator/tools.py` — tool-use схемы `TOOL_SCHEMAS` + роутер
  `dispatch`.
- `app/orchestrator/prompts.py` — системные промпты, `EXTRACT_SCHEMA`.
- `app/services/llm.py` — `run_tool_loop` (ручной цикл), провайдеры
  Groq/Anthropic/mock, fallback на Opus при refusal.
- `app/models.py` — контракт `Card`, `ClaimResult`, `Verdict`, `Manipulation`.
- Тесты: `tests/test_orchestrator.py`, `tests/test_provider.py`,
  `tests/test_backends.py`, `tests/test_tools.py`.

**Свои вопросы-ответы:**
1. *«Почему это не обёртка над API?»* — 5-шаговый цикл + ручной tool-use loop +
   детерминированный fallback с тем же контрактом `Card`; модель сама выбирает
   инструменты, мы трассируем реальные вызовы. Показать `orchestrator.py::analyze`
   и `llm.py::run_tool_loop`. (см. QA A1, A2)
2. *«Выпишите формулу confidence и обоснуйте веса.»* —
   `0.5·min(1, sim/τ) + 0.45·google`, обрезка до 1.0; два независимых сигнала.
   Показать `compute_confidence` (строки 41–49). (см. QA A4)
3. *«Что если LLM упал / его сломали инъекцией?»* — детерминированный путь по тем
   же реальным инструментам, тот же `Card`; инъекция максимум отрабатывает
   правилами. Показать try/except в `analyze` и `_mock_*`. (см. QA A10, D1)

---

## Роль №2 — Frontend / DevOps

**Владеет и защищает:** Telegram-бот, веб-карточка, API-эндпоинты, деплой,
безопасность инфраструктуры, лимиты ввода, резервный скринкаст.

**Файлы/модули:**
- `app/bot.py` — aiogram-хендлеры, forward → карточка, обрезка ввода (3500).
- `app/main.py` — FastAPI: `/health`, `/analyze` (`MAX_INPUT_CHARS=4000`),
  `/r/{id}`, `/webhook/{token}` (сверка токена → 403), `/metrics`,
  `/image-signal`.
- `app/presenter.py`, `app/templates/card.html`, `app/templates/index.html` —
  рендер карточки, подсветка span'ов, Jinja2-автоэкранирование.
- `app/store.py` — хранилище карточек, случайные короткие id.
- `app/config.py` — секреты через pydantic-settings из env.
- Деплой: `Dockerfile`, `railway.json`, `Procfile`, `DEPLOY.md`, `run.py`.
- Документ: `SECURITY.md`. Тесты: `tests/test_api_limits.py`.

**Свои вопросы-ответы:**
1. *«Как защищаете webhook и секреты?»* — секретный токен в пути `/webhook/{token}`
   → 403 при несовпадении; секреты только в Railway Variables / `.env` (gitignore),
   не логируются, `/health` отдаёт только флаги. Показать `main.py::telegram_webhook`,
   `SECURITY.md §2`. (см. QA D2, D4)
2. *«DoS большим вводом?»* — `MAX_INPUT_CHARS=4000` на сервере (обрезка, не
   отказ), бот — 3500, оба ниже Telegram 4096; тест есть. Показать `main.py` стр.
   156–157, `tests/test_api_limits.py`. (см. QA D3)
3. *«Что если сервис упадёт на сцене?»* — записан обязательный резервный
   скринкаст (§7 ТЗ, день 20.07); прод на Railway с HTTPS и `/health`-liveness.
   Показать `railway.json`, `DEPLOY.md`.

---

## Роль №3 — Data / Research

**Владеет и защищает:** парсер Factcheck.kz, локальный корпус и семантический
поиск, эмбеддинги, дедупликация, eval-набор и метрики, интеграция KazLLM.

**Файлы/модули:**
- `app/tools/factcheck_parser.py` — парсинг Factcheck.kz (og-meta, метки
  вердикта, дедуп URL), запуск `scripts/build_corpus.py`.
- `app/tools/local_corpus.py` — три бэкенда retrieval, τ, маппинг вердиктов.
- `app/services/embeddings.py` — e5 (`multilingual-e5-base`), префиксы, cosine.
- `app/services/vectorstore.py` — pgvector-поиск (`scripts/index_corpus.py`).
- `app/services/kazllm.py` — KazLLM-8B через llama.cpp.
- `app/tools/google_factcheck.py` — реальный Google Fact Check API + маппинг
  рейтингов.
- Данные/eval: `data/factcheck_kz*.json`, `data/eval_set.json`,
  `scripts/eval.py`, `EVAL.md`, `MODELING.md`. Тесты:
  `tests/test_factcheck_parser.py`, `tests/test_eval.py`, `tests/test_lang.py`.

**Свои вопросы-ответы:**
1. *«Как собран корпус и что с дедупликацией?»* — парсер по sitemap/og-meta,
   отбрасывает статьи без метки вердикта; дедуп URL по `seen`/`id` при сборке +
   кэш вердиктов по SHA-256 claim в рантайме. Показать
   `factcheck_parser.py::list_article_urls`, `services/cache.py::_key`. (см. QA
   B1, B3)
2. *«Метрики: на чём и как считали?»* — 12 размеченных кейсов; манипуляции
   precision 0.941 / recall 1.0 / F1 0.97 (TP/FP/FN 16/1/0), язык/мнения/вердикт
   1.0; единственный FP вынесен честно. Показать `EVAL.md`, `scripts/eval.py`.
   (см. QA A7, A8)
3. *«Семантический поиск реально на e5?»* — по умолчанию лексический fallback
   (чтобы запускалось везде), e5/pgvector по флагам с тем же контрактом; активный
   бэкенд видно в `/health`. Показать `local_corpus.py::_retrieve`. (см. QA A5,
   A6, B5)

---

## Роль №4 — Product / Pitch

**Владеет и защищает:** продуктовая идея и USP, формат карточки-разбора,
детектор манипуляций (продуктовая ценность объяснимости), монетизация и
устойчивость, adversarial-тесты, границы MVP.

**Файлы/модули:**
- `app/tools/rhetoric.py` — каталог 6 приёмов, span'ы, ru/kk (продуктовое
  «почему объяснимость»).
- `app/services/metrics.py`, `app/main.py::/metrics` — измеряемый соц-эффект.
- `app/services/image_forensics.py` — второстепенный сигнал (ELA/EXIF),
  дисклеймер, границы MVP.
- Документы: `README.md` (USP, дисклеймер 78% AUC, что НЕ в MVP), `COSTS.md`
  (структура затрат, монетизация при CC-BY-NC), `SUSTAINABILITY.md`,
  `DEMO_SCRIPT.md`, `TVEP_CHECKLIST.md`.
- Тесты (adversarial): `tests/test_rhetoric.py`, `tests/test_image_forensics.py`,
  `tests/test_metrics.py`.

**Свои вопросы-ответы:**
1. *«Почему карточка, а не «97% фейк»?»* — детекторы дают ~78% AUC, врать
   точностью отказываемся; USP — объяснимость + локальный (kk/ru) контекст;
   мнения честно помечаем непроверяемыми. Показать `README.md`,
   `rhetoric.py::_CATALOGUE`, `models.py::Verdict.NOT_CHECKABLE`. (см. QA E1, E2)
2. *«Монетизация при CC-BY-NC и соц-эффект?»* — гранты (Medianet/Soros),
   B2G-пилот с акиматами, white-label для школ; коммерция — на не-NC модели;
   эффект меряем в `/metrics`. Показать `COSTS.md`/`SUSTAINABILITY.md`,
   `services/metrics.py`. (см. QA C3, C4)
3. *«Где честные границы MVP?»* — нет надёжной детекции дипфейков (только
   ELA/EXIF-сигнал на своём демо-контенте с дисклеймером), нет видео/аудио в
   проде, нет автоблокировки. Показать `README.md` «Что НЕ входит в MVP»,
   `image_forensics.py`. (см. QA E4)

---

## Матрица «тема Q&A → роль»

| Тема вопроса | Отвечает | Резерв |
|---|---|---|
| Модель, агентный цикл, confidence, промпты | №1 | №3 |
| Данные, корпус, парсер, метрики, KazLLM, эмбеддинги | №3 | №1 |
| Деньги, монетизация, устойчивость, соц-эффект | №4 | №2 |
| Деплой, бот, веб-карточка, безопасность, лимиты | №2 | №1 |
| Продукт, UX-карточка, границы MVP, объяснимость | №4 | №3 |

**Перед финалом:** прогнать этот файл вслух, сверить зоны с `git log --author`,
отрепетировать 2–3 передачи слова между ролями за 2 минуты Q&A.
