# Engineering Knowledge Graph

Engineering Knowledge Graph, или Engineering KG, - это локальный инструмент для сборки навигационного графа инженерных знаний по проектному workspace. Он помогает агентам и людям быстро понять, какие репозитории входят в проект, где лежат требования, какие OpenSpec-изменения затрагивают какие спецификации, какие сервисы за что отвечают и по каким исходным файлам можно проверить факт.

Проект ориентирован на работу системного аналитика с требованиями и спецификациями. Он не заменяет требования, OpenAPI/AsyncAPI/GraphQL-контракты, Jira, Bitbucket или OpenLore. Его задача - собрать из локальных источников компактный, проверяемый и детерминированный слой навигации, который не смешивает логику разных сервисов.

## Зачем это нужно

В больших проектах информация о задаче обычно разбросана между Jira, требованиями, OpenSpec, wiki, несколькими backend/frontend репозиториями, библиотеками моделей и сгенерированными индексами кода. Без явной карты агент может начать искать по всем файлам подряд и ошибочно объединить поведение разных сервисов.

Engineering KG решает эту проблему так:

- хранит список репозиториев проекта и их роли;
- отделяет requirements-репозиторий от implementation-репозиториев;
- извлекает из OpenSpec структуру спецификаций, требований, сценариев, активных и архивных изменений;
- сохраняет факты в локальный graph store;
- выводит производные связи, например связь OpenSpec change с durable specification;
- валидирует целостность графа;
- дает локальный Python API и тонкие MCP/FastMCP wrappers для запросов.

Главная идея: граф хранит не большие тексты и не код, а проверяемые ссылки на источники. Например, вместо тела функции хранится `CodeLocator`: репозиторий, ревизия, файл и символ. Детали кода должны разрешаться через OpenLore, а не копироваться в Engineering KG.

## Что уже поддерживает MVP

Текущая версия проекта - локальный MVP. Она поддерживает:

- загрузку и проверку `repo-index.yaml`;
- построение канонического графа workspace, repositories и services;
- проверку workspace-level OpenLore конфигурации без чтения содержимого code graph;
- проверку OpenSpec store source;
- извлечение OpenSpec durable specs, active changes, archived changes, requirements и scenarios;
- локальное сохранение графа в LadybugDB-compatible adapter store (`graph.json`);
- deterministic derivation связей;
- graph integrity validation;
- локальные query API: requirements, services, changes, traceability;
- FactMCP/FastMCP wrappers для query tools.

Jira MCP и Bitbucket MCP пока описаны как архитектурные границы pipeline, но в текущем MVP нет полноценного извлечения payload из Jira или Bitbucket. Это осознанное ограничение: проект остается local-first, credential-free и не требует внешних API для базового запуска.

## Основные ограничения

- Проект работает локально и детерминированно.
- Для базового запуска не нужны API keys, cloud services или доступ к enterprise-системам.
- Generated graph/index state не должен коммититься как источник истины.
- Requirements repository хранит требования, OpenSpec, wiki и конфигурацию Engineering KG.
- Implementation repositories остаются отдельными Git-репозиториями.
- Один service в MVP должен соответствовать одному repository.
- `repo-index.yaml` не должен хранить implementation details, Jira payload, Bitbucket payload, OpenSpec requirement bodies, generated documentation, source code или credentials.
- Output query/pipeline не должен содержать source code, call graph, dependency graph, symbol bodies, tokens, credentials или внешние API responses.

## Рекомендуемая структура директорий

Engineering KG рассчитан на workspace, который сам не является Git-репозиторием. Внутри него лежат отдельные репозитории и локально сгенерированные индексы:

```text
project-directory/
├── .engineering-kg/
│   └── ladybugdb/
│       └── graph.json
├── .openlore/
├── src/
│   └── codebase_repos/
│       ├── service-a/
│       └── service-b/
└── openspec/
    └── requirements_repo/
        ├── openspec/
        │   ├── specs/
        │   └── changes/
        ├── wiki/
        └── repo-index.yaml
```

В этой схеме:

- `project-directory/` - локальный workspace всего проекта;
- `.engineering-kg/ladybugdb/` - локальный generated graph store;
- `.openlore/` - локальный generated OpenLore workspace index;
- `src/codebase_repos/*` - независимые implementation repositories;
- `openspec/requirements_repo/` - requirements repository и OpenSpec store.

Generated state (`.engineering-kg`, `.openlore`) должен лежать на уровне workspace и не должен попадать внутрь requirements repository или implementation repository.

## Предварительные требования (prerequisites)

Для корректной работы нужны:

- Python `3.11` или новее.
- Git, потому что workspace состоит из отдельных Git-репозиториев.
- Доступ к локальным клонам нужных репозиториев.
- `repo-index.yaml` в корне requirements repository.
- В requirements repository должны существовать директории:
  - `openspec/specs/`;
  - `openspec/changes/`.
- Для stages `openspec-store-source` и `openspec-graph-extraction` при запуске через `scripts/build.py` нужен доступный CLI `openspec`, потому что runner вызывает `openspec store list --json`.
- Для запуска тестов желательно иметь стандартный `unittest`; отдельный test runner не обязателен.
- Для FactMCP/FastMCP wrappers нужен Python runtime, который предоставляет `mcp.server.fastmcp.FastMCP`. Без него reusable query API все равно работает.
- LadybugDB Node package не обязателен для текущего Python MVP. Сейчас persistence реализован через adapter-compatible local store, который пишет `graph.json`. Если целевая среда требует реальный LadybugDB runtime, подтвержденная зависимость описана как `@ladybugdb/core`.

На enterprise рабочем контуре также должны быть заранее настроены разрешенные способы получения зависимостей. Не добавляйте в конфигурации secrets, tokens, private keys, production URLs с чувствительными данными или payload внешних систем.

## Установка

Клонируйте репозиторий Engineering KG:

```sh
git clone <engineering-kg-repository-url> engineering-kg
cd engineering-kg
```

Создайте virtual environment:

```sh
python3.11 -m venv .venv
source .venv/bin/activate
```

Установите пакет в editable-режиме:

```sh
python -m pip install --upgrade pip
python -m pip install -e .
```

Проверьте установку:

```sh
python -m unittest
python scripts/build.py
```

Второй запуск должен вернуть JSON со статусом `completed`, нулем configured/executed stages и пустым graph snapshot.

## Настройка `repo-index.yaml`

`repo-index.yaml` - главный конфигурационный файл workspace. Он лежит в requirements repository и описывает только стабильную топологию и локальные ссылки: workspace, layout, Engineering KG output, OpenLore references, список репозиториев и Git policies.

Минимальный пример:

```yaml
version: 1

workspace:
  id: payments-workspace
  name: Payments Workspace
  description: Workspace for requirements, services, OpenSpec and generated local KG state.

layout:
  root_path: ../..
  openlore_path: .openlore

engineering_kg:
  enabled: true
  store_repository: requirements
  output_path: .engineering-kg/ladybugdb
  pipeline_stages:
    - workspace-registry
    - openspec-store-source
    - openspec-graph-extraction
    - ladybugdb-persistence
    - graph-derivation
    - graph-integrity-validation

openlore:
  federation_enabled: true
  freshness_policy: validate-only

repositories:
  - id: requirements
    path: .
    description: OpenSpec changes, requirements, wiki content, and Engineering KG configuration.
    ssh_url: git@bitbucket.example.internal:PROJECT/requirements.git
    default_branch: main
    role: requirements
    exploration:
      include_by_default: true
      search_exclusions:
        - .git
      notes: Start here for requirements and OpenSpec context.
    git:
      dirty_worktree: read-with-warning
      fetch: forbidden
      pull: forbidden
      pull_requires_default_branch: true
      branch_rule: Keep requirements branches separate from implementation repositories.

  - id: payment-service
    path: ../../src/codebase_repos/payment-service
    description: Backend service that implements payment operations.
    ssh_url: git@bitbucket.example.internal:PROJECT/payment-service.git
    default_branch: main
    role: code
    service:
      id: payment-service
      name: Payment Service
    openlore:
      include_in_federation: true
      index_location: .openlore/index
    exploration:
      include_by_default: true
      search_exclusions:
        - .git
        - build
    git:
      dirty_worktree: read-with-warning
      fetch: allowed
      pull: allowed
      pull_requires_default_branch: true
      branch_rule: Inspect the current branch; never change it during exploration.
```

Важные правила:

- `version` сейчас должен быть `1`.
- `engineering_kg.store_repository` должен ссылаться на repository с `role: requirements`.
- `layout.root_path` указывает на workspace root, а не на Git root Engineering KG.
- `engineering_kg.output_path` резолвится относительно workspace root.
- `layout.openlore_path` резолвится относительно workspace root.
- `repositories[*].path` резолвится относительно файла `repo-index.yaml`, если путь не абсолютный.
- `repositories[*].ssh_url` должен начинаться с `ssh://` или `git@`.
- Для code/library repositories нельзя размещать пути внутри requirements repository.
- Generated paths `.openlore` и `.engineering-kg/ladybugdb` не должны находиться внутри любого configured repository.

## Pipeline config

Pipeline управляется массивом:

```yaml
engineering_kg:
  pipeline_stages:
    - workspace-registry
    - workspace-openlore-source
    - openspec-store-source
    - openspec-graph-extraction
    - ladybugdb-persistence
    - graph-derivation
    - graph-integrity-validation
```

Не все stages обязательны. Runner выполняет только те stages, которые перечислены в `repo-index.yaml`, плюс может вставить `ladybugdb-persistence`, если передан `--persistence-path`, а stage не был указан явно. В таком случае persistence вставляется перед `graph-derivation` и `graph-integrity-validation`.

Некоторые stages зависят от предыдущих:

- `openspec-graph-extraction` требует успешный `openspec-store-source`;
- `graph-integrity-validation` может работать после extraction и/или derivation;
- `ladybugdb-persistence` сохраняет текущий graph snapshot и возвращает readback из local store.

## Как работает каждый pipeline stage

Концептуальная цепочка pipeline выглядит так:

```text
Workspace Registry
  -> Workspace OpenLore
  -> OpenSpec Store
  -> Jira MCP
  -> Bitbucket MCP
  -> Normalize
  -> LadybugDB-compatible local store
  -> Derive
  -> Validate
  -> MCP queries
```

В текущем MVP часть шагов уже реализована как executable stages в `run_pipeline`, а часть пока является архитектурной границей для будущих source adapters. У каждого шага ниже явно указан статус.

### `workspace-registry` - реализовано в MVP

Загружает `repo-index.yaml`, проверяет структуру и строит первые graph facts:

- workspace node;
- repository nodes;
- service nodes;
- связи `workspace contains repository`;
- связи `service owns repository`.

Stage не читает код, не обращается в сеть, не вызывает OpenLore, Jira или Bitbucket. Он только превращает стабильную topology configuration в canonical graph snapshot.

### `workspace-openlore-source` - реализовано в MVP

Проверяет, что workspace-level OpenLore source configured корректно:

- `.openlore` находится внутри workspace root;
- `.openlore` не находится внутри requirements/code/library repository;
- repositories, включенные в OpenLore federation, имеют `openlore.index_location`.

Stage не читает source code и не копирует OpenLore graph contents в Engineering KG. Он сохраняет только ссылки на локальные OpenLore index locations.

### `openspec-store-source` - реализовано в MVP

Определяет и проверяет requirements repository как OpenSpec store:

- берет repository из `engineering_kg.store_repository`;
- требует `role: requirements`;
- при обычном script-запуске сверяет локальный repository с результатом `openspec store list --json`;
- проверяет наличие `openspec/`, `openspec/specs/` и `openspec/changes/`.

Если OpenSpec stores зарегистрированы неоднозначно или не совпадают с requirements repository, stage требует явный `--openspec-store-id`.

### `openspec-graph-extraction` - реализовано в MVP

Читает OpenSpec files из validated store и строит graph facts:

- durable specs из `openspec/specs/**/spec.md`;
- active changes из `openspec/changes/<change>/`;
- archived changes из `openspec/changes/archive/<archive-directory>/`;
- planning artifacts: `.openspec.yaml`, `proposal.md`, `design.md`, `tasks.md`;
- requirements из заголовков `### Requirement: <name>`;
- scenarios из заголовков `#### Scenario: <name>`;
- связи spec -> requirement, requirement -> scenario;
- связи change -> artifact и change -> touched spec;
- non-confident related-spec relationships из frontmatter `related`, если ссылка разрешается однозначно.

Capability identity берется из пути spec file. Например:

- `openspec/specs/payments/spec.md` становится capability `payments`;
- `openspec/specs/service/payments/spec.md` становится capability `service/payments`.

Stage не сохраняет полные bodies markdown-файлов в graph output. Evidence содержит путь к файлу, тип artifact, OpenSpec identity, heading и line number, если это применимо.

### `jira-mcp` - архитектурный placeholder для будущей реализации

Этот шаг зарезервирован для получения facts из Jira через MCP, например связи user story с OpenSpec change, задачами аналитика/разработчика/QA или статусами workflow. В текущем MVP этот extractor не реализован и pipeline не обращается к Jira.

Важное правило для будущей реализации: Jira payload не должен попадать в graph store целиком. Engineering KG должен сохранять только нормализованные факты и locators/references, достаточные для traceability.

### `bitbucket-mcp` - архитектурный placeholder для будущей реализации

Этот шаг зарезервирован для получения facts из Bitbucket через MCP, например pull request references, repository revision, branch или связь change с PR evidence. В текущем MVP этот extractor не реализован и pipeline не обращается к Bitbucket.

Как и с Jira, graph output не должен содержать raw API responses, diffs целиком, source code или credentials.

### `normalize` - архитектурный placeholder для будущей реализации

Normalize - это слой приведения входных фактов из разных источников к одной canonical ontology. В текущем коде normalization распределена по source modules: registry loader сразу создает `Node`/`Edge`, OpenSpec extractor сразу создает canonical graph facts, persistence принимает `GraphSnapshot`.

Когда появятся Jira/Bitbucket adapters, normalize step должен стать явнее: разные source-specific records будут преобразовываться в общий формат `Node`, `Edge`, `Evidence`, `Locator` до сохранения и derivation.

### `ladybugdb-persistence` - реализовано в MVP через adapter-compatible store

Сохраняет текущий canonical graph snapshot в local store:

```text
.engineering-kg/ladybugdb/graph.json
```

В MVP это adapter-compatible слой, изолированный за Python API. Он нужен, чтобы позже заменить внутреннюю реализацию на реальный LadybugDB binding или Node bridge без изменения pipeline stages и query API.

Persistence делает merge по deterministic IDs и возвращает graph snapshot, прочитанный обратно из store. Это защищает pipeline от ситуации, когда в памяти и на диске разные представления графа.

### `graph-derivation` - реализовано в MVP

Добавляет производные связи, которые можно вывести из уже извлеченных фактов. Текущая основная rule:

```text
openspec-change-to-durable-spec
```

Она ищет change-scoped spec, который touched by OpenSpec change, и durable spec с тем же capability. Если durable spec найден, создается связь:

```text
openspec-change-traces-to-spec
```

Если durable spec не найден, stage не выдумывает связь. Он добавляет deterministic diagnostic с объяснением unresolved input.

### `graph-integrity-validation` - реализовано в MVP

Проверяет целостность graph snapshot:

- edge endpoints ссылаются на существующие nodes;
- evidence references ссылаются на существующие evidence records;
- duplicate IDs не имеют конфликтующих serialized values;
- traceability edges имеют корректные source/target kinds;
- unresolved related specs представлены явно.

Если есть `error`, pipeline завершается ошибкой `GraphIntegrityValidationError`. Warnings могут оставаться в результате, если graph status остается `valid`.

### `MCP queries` - реализовано как query layer, не как `run_pipeline` stage

MCP query layer не является build stage в текущем `run_pipeline`, но это последняя архитектурная точка использования графа. После сборки graph store можно открыть через Python query API или FactMCP/FastMCP tools:

- `list_requirements`;
- `list_services`;
- `list_changes`;
- `get_traceability`.

Wrappers тонкие: они не реализуют обход графа сами, а делегируют в reusable Python API.

## Команды запуска

Пустой bootstrap run:

```sh
python scripts/build.py
```

Запуск pipeline по registry:

```sh
python scripts/build.py /path/to/requirements_repo/repo-index.yaml
```

Запуск с сохранением graph store:

```sh
python scripts/build.py /path/to/requirements_repo/repo-index.yaml \
  --persistence-path /path/to/project-directory/.engineering-kg/ladybugdb
```

Запуск с явным OpenSpec store id:

```sh
python scripts/build.py /path/to/requirements_repo/repo-index.yaml \
  --openspec-store-id requirements-store
```

Запуск derivation-oriented wrapper:

```sh
python scripts/derive.py /path/to/requirements_repo/repo-index.yaml
```

## Использование Python API

Pipeline можно вызвать из Python:

```python
from engineering_kg.pipeline import run_pipeline

result = run_pipeline(
    "/path/to/requirements_repo/repo-index.yaml",
    persistence_path="/path/to/project-directory/.engineering-kg/ladybugdb",
)

print(result.status)
print(result.graph.node_count)
```

Query API можно использовать поверх persisted store:

```python
from engineering_kg.query import EngineeringKgQuery

query = EngineeringKgQuery.from_store(
    "/path/to/project-directory/.engineering-kg/ladybugdb",
    require_validation=True,
)

requirements = query.list_requirements(capability="payments")
services = query.list_services()
changes = query.list_changes()
traceability = query.get_traceability(changes[0]["id"])
```

## Концептуальная архитектура

Архитектура разделяет источники, нормализацию, storage и query layer:

```text
repo-index.yaml
OpenSpec files
OpenLore index references
Jira / Bitbucket adapter boundaries
        |
        v
Reusable Python modules
        |
        v
Canonical ontology: Node, Edge, Evidence, Locator
        |
        v
LadybugDB-compatible local store
        |
        v
Derivation + validation
        |
        v
Python Query API + FactMCP/FastMCP tools
```

Основные модули:

- `engineering_kg.project.registry` - загрузка и валидация `repo-index.yaml`;
- `engineering_kg.openlore` - проверка OpenLore source configuration;
- `engineering_kg.ingest.openspec` - проверка OpenSpec store и extraction OpenSpec facts;
- `engineering_kg.ontology` - canonical graph model;
- `engineering_kg.persistence` - local graph store boundary;
- `engineering_kg.derivation` - deterministic derived relationships;
- `engineering_kg.validation` - graph integrity validation;
- `engineering_kg.query` - локальные запросы к graph snapshot/store;
- `engineering_kg.mcp.factmcp_server` - MCP/FastMCP tools поверх query API.

## Модель графа

Граф состоит из трех типов записей:

- `Node` - объект: workspace, repository, service, OpenSpec spec, requirement, scenario, change, artifact.
- `Edge` - связь между объектами: contains, owns, spec contains requirement, requirement contains scenario, change touches spec, change traces to spec.
- `Evidence` - ссылка на источник факта: OpenSpec file/heading, CodeLocator, Confluence page ref и другие locators.

Идентификаторы создаются детерминированно через stable hash от типа объекта и его identity parts. Поэтому одинаковый input должен давать одинаковые node IDs, edge IDs и evidence IDs.

## Что не хранится в графе

Engineering KG намеренно не хранит:

- исходный код;
- тела функций и классов;
- call graph и dependency graph из OpenLore;
- полные requirement/change/spec bodies;
- Jira, Bitbucket или Confluence payload;
- credentials, tokens, API responses;
- generated documentation.

Это снижает риск утечек и не превращает graph store во вторую копию всех систем. Граф хранит ссылки и компактные факты, а не исходные данные целиком.

## Глоссарий проекта

`workspace` - локальная папка, которая объединяет requirements repository, implementation repositories, generated OpenLore index и generated Engineering KG graph store. В MVP workspace не обязан быть Git-репозиторием.

`requirements repository` - Git-репозиторий, где живут требования, OpenSpec specs/changes, wiki и `repo-index.yaml`. В этом проекте он является центральной точкой конфигурации Engineering KG.

`implementation repository` - отдельный Git-репозиторий с кодом сервиса, frontend, backend, library или infrastructure. Engineering KG использует его как отдельную сущность и не складывает его код в requirements repository.

`store` - в контексте проекта это локальное место хранения фактов графа. Чаще всего имеется в виду `.engineering-kg/ladybugdb/graph.json`, а не магазин, база требований или registry внешней системы.

`OpenSpec store` - requirements repository, зарегистрированный или выбранный как источник OpenSpec files. Из него читаются `openspec/specs` и `openspec/changes`.

`wiki` - проектная документация внутри requirements repository. Она может объяснять домен и правила проекта, но текущий MVP pipeline не парсит wiki как основной source extractor.

`graph` - набор узлов, связей и evidence, построенный из локальных источников. Это не картинка и не диаграмма, а машинно-читаемая структура для навигации и traceability.

`node` - объект графа: сервис, репозиторий, спецификация, требование, сценарий, изменение или artifact.

`edge` - связь между двумя nodes. Например, workspace содержит repository, service владеет repository, OpenSpec spec содержит requirement.

`evidence` - ссылка на источник, из которого был получен факт. Evidence не содержит полный исходный текст, а хранит locator.

`locator` - компактный адрес источника. Для OpenSpec это путь к файлу, identity и heading; для кода это `CodeLocator` с repository, revision, file и symbol.

`CodeLocator` - ссылка на код без копирования кода в граф. OpenLore должен использовать эту ссылку, чтобы найти детали символа.

`OpenLore` - внешний/отдельный слой code intelligence. В Engineering KG он считается authoritative source для code graph, architecture, impact и symbol resolution, но его payload не сохраняется в Engineering KG.

`LadybugDB-compatible store` - локальный persistence boundary для graph snapshot. В MVP реализован как `graph.json`, но интерфейс отделен так, чтобы позже подключить реальный LadybugDB backend.

`pipeline` - последовательность локальных stages, которые читают конфигурацию и источники, строят граф, сохраняют его, выводят связи и проверяют целостность.

`stage` - один шаг pipeline. Например, `workspace-registry`, `openspec-graph-extraction` или `graph-integrity-validation`.

`derivation` - вывод новых связей из уже известных фактов без LLM и без догадок. Например, active change touches spec delta, а durable spec с тем же capability существует; значит можно построить traceability edge.

`validation` - проверка, что graph snapshot не содержит битых ссылок, конфликтующих IDs и некорректных traceability edges.

`traceability` - прослеживаемость между требованиями, изменениями, спецификациями, сервисами и evidence. В этом проекте traceability должна быть основана на graph facts, а не на предположениях агента.

`capability` - идентификатор OpenSpec specification, полученный из пути к `spec.md` относительно `openspec/specs` или change-local `specs`. Например, `service/payments`.

`durable spec` - текущая спецификация из `openspec/specs/**/spec.md`.

`change-scoped spec` - delta specification внутри `openspec/changes/<change>/specs/**/spec.md` или архивного изменения.

`active change` - директория изменения в `openspec/changes/<change>/`, которая еще не находится в `archive`.

`archived change` - директория изменения в `openspec/changes/archive/<archive-directory>/`.

`canonical graph` - нормализованное внутреннее представление графа через `Node`, `Edge` и `Evidence`, одинаковое для pipeline, persistence и queries.

`deterministic` - одинаковые входные файлы должны давать одинаковый JSON output, одинаковые IDs и одинаковые diagnostics.

`local-first` - pipeline должен работать по локальным файлам и локальному store, без обязательного доступа к cloud, enterprise APIs или LLM services.

## Разработка и проверка

Запуск всех тестов:

```sh
python -m unittest
```

Запуск одного test module:

```sh
python -m unittest tests.test_pipeline_runner
```

Проверка примера registry fixture:

```sh
python scripts/build.py tests/fixtures/repo-index.yaml
```

Проверка полного OpenSpec/derivation/validation сценария на fixture требует, чтобы `openspec store list --json` возвращал store, совпадающий с fixture requirements repository. В unit tests это подменяется fake CLI, поэтому tests остаются local-first.

## Где смотреть детали

- `docs/engineering-knowledge-graph-pipeline-mvp.md` - исходное MVP-описание pipeline.
- `docs/engineering-kg-project-constraints-mvp.md` - ограничения проекта.
- `docs/engineering-kg-development-plan-mvp.md` - план развития MVP.
- `docs/repo-index.schema.json` - JSON Schema для `repo-index.yaml`.
- `docs/ladybugdb-dependency.md` - заметки по LadybugDB dependency boundary.
- `openspec/specs/` - OpenSpec specs текущих capabilities проекта.
- `tests/fixtures/` - рабочие примеры `repo-index.yaml` и OpenSpec stores.
