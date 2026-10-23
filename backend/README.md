# Artificial Soul Backend

Artificial Soul은 대학 홈페이지의 학사일정·학사규정·장학금 등 TXT 지식 데이터를 검색하고, 검색된 근거로 기존 LLM이 답변하는 **RAG 기반 대학 정보 AI Assistant**입니다. 사용자 입력은 텍스트이며, 최종 응답은 답변과 출처를 제공합니다.

현재 백엔드는 개발환경·Health API와 **TXT → Document/Chunk → 실제 E5 Embedding → Qdrant 적재 → 질문 Top-K 검색 API**를 제공합니다. Chunking은 NLP 담당의 함수를 주입하며, 초기 Embedding은 PyTorch·Hugging Face Transformers로 실행하는 `intfloat/multilingual-e5-small`입니다. User·Chat/Message 저장·JWT·SSE·LLM 답변 생성은 후속 구현 대상입니다. 검색 API는 **인증 전의 로컬 개발·프론트 연동 검증용**이며 운영에 공개하지 않습니다.

## 기술과 실행 구조

| 구분 | 구성 |
| --- | --- |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2, pydantic-settings |
| PostgreSQL | PostgreSQL 16, SQLAlchemy 2.x Async Engine, asyncpg |
| Vector DB | Qdrant 1.19.1, qdrant-client 1.19.1, AsyncQdrantClient |
| Infrastructure | Docker, Docker Compose, named volumes |
| Testing | pytest, pytest-asyncio, httpx |
| Embedding | PyTorch, Hugging Face Transformers, multilingual-e5-small, CPU |

```text
Host
├── FastAPI / Uvicorn :8000
│   ├── PostgreSQL 연결
│   └── Qdrant 연결
└── Docker Compose
    ├── PostgreSQL :5432 → postgres_data
    └── Qdrant     :6333 → qdrant_data
```

`docker compose up -d`는 PostgreSQL과 Qdrant만 실행합니다. FastAPI는 로컬 IDE나 터미널에서 실행하며, 인프라 포트는 로컬 컴퓨터의 `127.0.0.1`에 바인딩합니다.

## 처음 실행하기

Python 3.12와 Docker Compose를 지원하는 Docker가 필요합니다. macOS/Windows에서 Docker Desktop을 사용한다면 먼저 실행하세요. 아래 명령은 저장소를 clone한 이후 **backend 디렉터리에서** 실행합니다.

### 1. Clone과 가상환경 생성

```bash
git clone <repository-url> Artificial-Soul-main
cd Artificial-Soul-main/backend
python3.12 --version
python3.12 -m venv .venv
source .venv/bin/activate
python --version
```

마지막 출력이 `Python 3.12.x`인지 확인하세요. `.venv`는 이 프로젝트에서만 사용할 패키지를 분리합니다. 다른 버전의 Python이 기본값일 수 있으므로 `python3.12`를 명시합니다.

Windows PowerShell에서는 가상환경 생성·활성화 명령만 다음으로 바꿉니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

Python 3.12가 없고 `uv`를 사용 중이라면 다음 명령으로 프로젝트 내부에 설치할 수 있습니다. `uv`는 선택 도구이며, 이미 Python 3.12가 있다면 필요하지 않습니다.

```bash
export UV_PYTHON_INSTALL_DIR="$PWD/.python"
export UV_CACHE_DIR="$PWD/.cache/uv"
uv python install 3.12 --no-bin
uv venv --python 3.12 --seed .venv
source .venv/bin/activate
```

### 2. Dependency 설치

```bash
python -m pip install -r requirements.txt
```

`requirements.txt`에는 직접 사용하는 라이브러리와 전이 의존성의 버전까지 고정했습니다. Windows 전용 패키지는 환경 조건에 따라 설치됩니다. 라이브러리 버전을 바꿀 때는 Python 3.12에서 테스트한 뒤 이 파일도 갱신합니다.

### 3. 환경변수 준비

```bash
cp .env.example .env
```

PowerShell에서는 `Copy-Item .env.example .env`를 사용합니다. 기존 `.env`가 있다면 덮어쓰지 말고 필요한 항목만 확인하세요.

| 환경변수 | 개발용 예시 | 역할 |
| --- | --- | --- |
| `POSTGRES_DB` | `artificial_soul` | Compose가 초기화할 DB명 |
| `POSTGRES_USER` | `postgres` | Compose DB 사용자 |
| `POSTGRES_PASSWORD` | `postgres` | 로컬 개발용 비밀번호 |
| `POSTGRES_PORT` | `5432` | PostgreSQL의 호스트 포트 |
| `QDRANT_PORT` | `6333` | Qdrant의 호스트 포트 |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/artificial_soul` | FastAPI의 비동기 PostgreSQL 연결 주소 |
| `QDRANT_URL` | `http://localhost:6333` | FastAPI의 Qdrant HTTP 주소 |
| `HEALTH_CHECK_TIMEOUT_SECONDS` | `3` | 서비스별 readiness 확인 제한 시간 |
| `QDRANT_COLLECTION_NAME` | `artificial_soul_e5_small_v1` | E5 전용 적재·검색 컬렉션; 기존 `.env`는 직접 변경 필요 |
| `QDRANT_VECTOR_SIZE` | `384` | E5 실제 차원; Settings 기본값은 None이며 검색·적재 시 일치 필수 |
| `QDRANT_DISTANCE` | `Cosine` | 벡터 거리 함수; `Cosine`, `Dot`, `Euclid`, `Manhattan` 지원 |
| `QDRANT_REQUEST_TIMEOUT_SECONDS` | `10` | Qdrant 클라이언트 요청 제한; Health 확인 제한과 독립 |
| `RETRIEVAL_TIMEOUT_SECONDS` | `30` | 질문 임베딩과 검색의 전체 제한 |
| `EMBEDDING_MODEL_ID` | `intfloat/multilingual-e5-small` | E5 provider가 지원하는 기준 모델 |
| `EMBEDDING_MODEL_REVISION` | `614241f622f53c4eeff9890bdc4f31cfecc418b3` | tokenizer·weights에 동일하게 적용하는 고정 리비전 |
| `EMBEDDING_CACHE_DIR` | `.cache/huggingface` | backend 기준 캐시 경로; 절대 경로도 지원 |
| `EMBEDDING_BATCH_SIZE` | `32` | 문서 임베딩 batch 크기, 1~128 |

`DATABASE_URL`은 반드시 `postgresql+asyncpg://`로 시작해야 합니다. DB명·계정·비밀번호를 변경하면 `POSTGRES_*`와 `DATABASE_URL`을 함께 수정하세요. URL에 들어가는 비밀번호에 특수문자가 있으면 URL 인코딩해야 합니다.

설정은 작업 디렉터리에 관계없이 이 백엔드의 `.env`를 읽으며, 운영체제 환경변수가 `.env`보다 우선합니다. `.env.example`의 계정은 로컬 개발용 예시이며, 실제 비밀번호·Secret은 `.env`나 실행 환경에만 둡니다. `.env`는 Git과 Docker 빌드 컨텍스트에서 제외됩니다.

기존 `.env`는 새 예시로 자동 갱신되지 않습니다. 3주차 검색·적재에는 `QDRANT_VECTOR_SIZE=384`, `QDRANT_DISTANCE=Cosine`과 E5 전용 컬렉션을 설정하세요. 빈 `QDRANT_VECTOR_SIZE=`는 허용하지 않습니다. 이 설정을 생략하거나 모델 파일이 없어도 TXT 준비·FastAPI 시작·Health는 동작하지만 검색·적재는 준비 상태를 확인합니다. 앱 시작과 Health에서 컬렉션을 생성하거나 모델을 다운로드·로드하지 않습니다.

### 4. PostgreSQL과 Qdrant 실행

```bash
docker compose config --quiet
docker compose up -d
docker compose ps
```

첫 실행은 이미지 다운로드와 PostgreSQL 초기화에 시간이 걸립니다. PostgreSQL은 `pg_isready` healthcheck를 제공합니다. 실제 두 서비스의 API 연결 여부는 아래 `/health/ready`로 확인합니다.

### 5. FastAPI 실행

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`--reload`는 코드 수정 시 개발 서버를 다시 시작합니다. IDE에서도 가상환경의 Python을 선택하고, 모듈 `uvicorn`, 인자 `app.main:app --reload`, 작업 디렉터리 `backend`로 설정할 수 있습니다.

## Health Check와 Swagger

서버를 실행한 상태에서 다른 터미널로 확인합니다.

```bash
curl http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/health/ready
```

`GET /health`는 외부 서비스에 요청하지 않고 HTTP 200을 반환합니다. 인프라가 중지되어도 유효한 설정이 있다면 FastAPI를 시작하고 이 API를 사용할 수 있습니다.

```json
{"status": "ok"}
```

`GET /health/ready`는 PostgreSQL에서 `SELECT 1`, Qdrant에서 컬렉션 목록 조회를 수행합니다. 컬렉션이 없어도 정상입니다. 두 확인은 동시에 실행되며 각각 기본 3초의 제한 시간이 적용됩니다.

```json
{"status": "ready", "postgres": "ok", "qdrant": "ok"}
```

두 서비스가 정상이면 HTTP 200입니다. 하나라도 실패하거나 시간초과가 발생하면 HTTP 503이며, 실패한 서비스만 `error`로 표시합니다. 응답이나 readiness 로그에 연결 주소·비밀번호·원본 예외 내용을 넣지 않습니다.

```json
{"status": "not_ready", "postgres": "error", "qdrant": "ok"}
```

- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- Qdrant 자체 준비 상태: `curl -i http://127.0.0.1:6333/readyz`
- PostgreSQL 자체 연결: `docker compose exec postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'`

Swagger의 `Try it out`으로 Health API와 아래에서 설명하는 `/api/rag/retrieve`를 호출할 수 있습니다. 검색 API의 모델 준비·적재 절차는 별도입니다.

## 테스트

가상환경을 활성화한 backend 디렉터리에서 실행합니다.

```bash
python -m pytest -q
python -m pip check
```

테스트는 `.env`, Docker, 실제 DB 없이 실행할 수 있습니다. `Settings(_env_file=None, ...)`로 테스트 설정을 주입하고, readiness에는 모의 연결을 사용합니다. 실제 Engine·클라이언트로도 외부 연결 없이 `/health`가 실행되는지 확인합니다.

검증하는 동작은 liveness, readiness 정상·서비스별 실패·동시 실패·시간초과, Swagger/OpenAPI, 종료 시 리소스 정리, 일부 리소스만 생성된 시작 실패 시 정리입니다. HTTPX `ASGITransport`는 lifespan을 자동 실행하지 않으므로 테스트에서 lifespan을 명시적으로 실행합니다.

Document 테스트는 UTF-8/BOM, 잘못된 TXT 입력, 필드와 JSON metadata 검증, splitter 주입, ID 재현성, 외부 연결 없는 ingestion을 확인합니다. Qdrant 모의 테스트는 컬렉션 생성·재사용·구성 불일치·연결 실패, Point 매핑, 전체 Vector 입력 검증, upsert 완료 여부를 확인합니다.

실제 Qdrant 검증은 기본 테스트에서 건너뜁니다. Qdrant를 실행한 뒤 macOS/Linux에서 명시적으로 실행할 수 있습니다.

```bash
RUN_QDRANT_INTEGRATION=1 QDRANT_URL=http://127.0.0.1:6333 python -m pytest -q -m integration
```

PowerShell에서는 다음과 같이 환경변수를 설정합니다.

```powershell
$env:RUN_QDRANT_INTEGRATION = "1"
$env:QDRANT_URL = "http://127.0.0.1:6333"
python -m pytest -q -m integration
Remove-Item Env:RUN_QDRANT_INTEGRATION
```

이 테스트는 `.env`나 PostgreSQL 없이 실행합니다. 고유한 `test_txt_ingestion_<UUID>` 컬렉션과 테스트용 2차원 벡터로 생성 → 적재 → 재적재 → Point 수·내용 조회를 확인합니다. 테스트가 확보한 이름의 컬렉션만 `finally`에서 삭제하고 클라이언트를 종료합니다. 테스트 벡터는 실제 Embedding 결과가 아닙니다.

## 프로젝트 구조와 파일 역할

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── user/
│   │   └── __init__.py
│   ├── chat/
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── model.py
│   │   └── schema.py
│   ├── document/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── chunker.py
│   │   ├── ingestion.py
│   │   └── schema.py
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── embedding.py
│   │   ├── indexing.py
│   │   ├── retrieval.py
│   │   ├── service.py
│   │   ├── router.py
│   │   ├── schema.py
│   │   ├── errors.py
│   │   └── cli.py
│   ├── health/
│   │   ├── __init__.py
│   │   └── router.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── database.py
│   └── clients/
│       ├── __init__.py
│       ├── qdrant.py
│       └── llm.py
├── tests/
│   ├── conftest.py
│   ├── test_document.py
│   ├── test_health.py
│   ├── test_lifespan.py
│   ├── test_qdrant.py
│   └── test_qdrant_integration.py
├── .env.example
├── .gitignore
├── .dockerignore
├── .python-version
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
└── README.md
```

Document는 내부 TXT 준비 기능을 제공하고, Qdrant는 연결 확인·컬렉션 준비·Chunk 저장을 담당합니다. RAG에는 실제 E5 임베딩·명시적 적재·검색 서비스·HTTP DTO/Router·CLI를 구현했습니다. User·Chat과 `clients/llm.py`는 후속 구현 위치입니다. HTTP API는 Health 2개와 검색 1개이며 Document 업로드·CRUD API는 제공하지 않습니다. 실제 `.env`·가상환경·모델 캐시는 Git·이미지에서 제외됩니다.

| 파일 또는 디렉터리 | 역할 |
| --- | --- |
| `app/main.py` | FastAPI 생성, router 등록, 앱 시작·종료 시 리소스 관리 |
| `app/health/router.py` | HTTP 헬스체크와 인프라 상태 응답 |
| `app/core/config.py` | 환경변수 로딩, 설정 타입·필수값 검증 |
| `app/core/database.py` | Async Engine, 세션 생성기, 요청별 세션, `SELECT 1` 확인 |
| `app/clients/qdrant.py` | AsyncQdrantClient 생성·연결 확인, 명시적인 컬렉션 준비와 Chunk/Vector 저장 |
| `app/user` | 향후 사용자 정보 기능의 개발 위치 |
| `app/chat/router.py`, `service.py` | 향후 Chat/Message HTTP·SSE 응답과 대화 처리 |
| `app/chat/repository.py`, `model.py`, `schema.py` | 향후 Chat/Message 저장, ORM 모델, 요청·응답 DTO |
| `app/document/schema.py` | Pydantic Document·Chunk·IngestionResult와 JSON metadata 검증 |
| `app/document/loader.py`, `chunker.py`, `ingestion.py` | UTF-8 TXT 로딩, 외부 splitter 연결, Document/Chunk 준비 진입점 |
| `app/rag/embedding.py` | 명시적 모델 다운로드, 캐시 전용 지연 로드, E5 CPU 추론·정규화 |
| `app/rag/indexing.py` | 전체 임베딩 검증, 모델 식별 정보 확인, 기존 Qdrant 적재 연결 |
| `app/rag/retrieval.py`, `service.py` | 모델·컬렉션 검증, 질문 임베딩·읽기 전용 Top-K 검색 |
| `app/rag/router.py`, `schema.py`, `errors.py` | 개발용 검색 HTTP 계약과 안전한 오류 응답 |
| `app/rag/cli.py` | 모델 준비와 수동 TXT 적재 명령 |
| `app/clients/llm.py` | 향후 LLM 연결 코드의 위치; 현재 외부 호출 없음 |
| `tests/conftest.py` | 외부 환경과 분리한 설정·모의 연결·HTTPX fixture |
| `tests/test_health.py`, `tests/test_lifespan.py` | API 응답과 리소스 수명주기 검증 |
| `tests/test_document.py`, `tests/test_qdrant.py` | 외부 환경 없이 TXT 준비와 Qdrant 저장 계약 검증 |
| `tests/test_qdrant_integration.py` | 명시적으로 실행하는 실제 Qdrant 적재·재적재·정리 검증 |
| `tests/test_embedding.py`, `test_indexing.py`, `test_retrieval_api.py`, `test_rag_cli.py` | 다운로드·인프라 없는 임베딩·적재·검색·CLI 계약 검증 |
| `tests/test_rag_integration.py` | 실제 E5와 Qdrant를 함께 사용하는 명시적 통합 검증 |
| `.env.example` | 팀원이 복사할 개발용 설정 예시 |
| `.gitignore`, `.dockerignore` | 로컬 설정·가상환경·캐시를 Git·이미지에서 제외 |
| `.python-version`, `requirements.txt` | Python 버전과 검증할 패키지 버전 지정 |
| `docker-compose.yml`, `Dockerfile` | 로컬 인프라 실행, 향후 백엔드 컨테이너의 기본 이미지 |
| `pytest.ini` | 테스트 검색 위치와 asyncio 설정 |

## 기능별 모듈과 아키텍처

MVP의 핵심은 **User + Chat/Message + RAG**입니다. 서비스 데이터는 기능별로 묶고, TXT 지식 데이터는 입력 처리와 RAG 파이프라인의 책임에 따라 분리합니다. 모든 패키지에 Router·Repository를 일괄적으로 만들지 않습니다.

| 모듈 | 기능과 책임 |
| --- | --- |
| User (`user`) | 사용자 정보 |
| Chat (`chat`) | 대화 생성·목록·상세·삭제, Message 저장·조회, SSE Streaming |
| Document (`document`) | 팀이 준비한 TXT 로딩, 텍스트 분할, Document/Chunk 구조 |
| RAG (`rag`) | Chunk·질문 임베딩, Qdrant 관련 Chunk 검색, Context 구성, LLM 답변·출처 처리 |
| Clients (`clients`) | Qdrant·LLM 외부 시스템과의 연결 |

Chat은 `router.py → service.py → repository.py` 흐름으로 업무 처리와 PostgreSQL 저장을 분리하며, `model.py`와 `schema.py`는 각각 ORM 모델과 API DTO를 담당합니다. PostgreSQL에 저장할 관계는 `User → Chat → Message`이며, 각 단계는 1:N입니다.

```text
[지식 구축]
TXT → document.loader → document.chunker → rag.embedding → Qdrant
                                                         (Vector + Payload)

[질문 응답]
텍스트 질문 → rag.embedding → rag.retrieval → Context → LLM → 답변 + Source
```

`document`는 RAG 입력 데이터를 다루는 패키지입니다. MVP에서는 팀이 준비한 TXT를 미리 인덱싱하고, 사용자 파일 업로드·Document CRUD API·문서 상태/버전 관리용 도메인을 만들지 않습니다. Chunking 방식은 NLP 담당이 실험·결정하고 Backend가 실제 서비스 흐름에 통합합니다. Qdrant에는 파일 자체가 아닌 Chunk의 Vector와 `text`, `source`, `category` 등의 Payload를 저장합니다.

`rag/service.py`는 현재 질문 임베딩과 관련 Chunk 검색을 조율합니다. Context 구성·LLM 답변은 4주차 후속 기능입니다. Qdrant 연결은 `clients/qdrant.py`, E5 모델 처리는 `rag/embedding.py`에 두며, LLM 제공자는 아직 결정하지 않았습니다.

Notebook은 Chat 목록을 보여주는 UI 명칭으로 사용할 수 있으며, 현재 별도 백엔드 패키지나 테이블을 두지 않습니다. Settings는 서버 저장이 필요한 사용자 설정이 생길 때 User 기능에서 확장하고, About Us는 프론트엔드 정적 페이지로 처리합니다.

서버 환경변수와 DB 연결은 공통 `core`에서 관리합니다. `core/config.py`의 `Settings` 클래스는 `DATABASE_URL`·`QDRANT_URL` 등 실행 환경설정이며 사용자 설정 도메인이 아닙니다. Health Check는 별도 `health` 모듈에서 연결 확인 함수를 호출합니다.

## TXT Ingestion 사용 방법

TXT 준비는 내부 Python 함수이며, 아래 3주차 `index_knowledge()`와 CLI에서 실제 Embedding·Qdrant 저장으로 연결합니다. HTTP ingestion API는 없습니다.

```text
prepare_txt_ingestion(path, source=..., splitter=...)
  ├── load_txt → Document
  └── chunk_document → list[Chunk]
          ↓
    IngestionResult(document, chunks)
          ↓ rag.indexing / 실제 E5 Embedding
    실제 Vector 목록 → ensure_collection → upsert_chunks
```

### Document·Chunk 구조

| 필드 | Document | Chunk | 규약 |
| --- | --- | --- | --- |
| `id` | UUID | UUID | Document는 source 기반 UUID5, Chunk는 Document UUID와 인덱스 기반 UUID5 |
| `document_id` | — | UUID | Chunk의 원본 Document 식별자 |
| `text` | 원문 | splitter가 반환한 부분 문자열 | 공백뿐인 값은 허용하지 않으며 내용과 줄바꿈을 보존 |
| `chunk_index` | — | 0부터 시작하는 정수 | 공백 Chunk를 제외한 후 순서대로 부여 |
| `source` | 문자열 | 동일 출처 | 호출자가 지정하는 안정적인 출처 식별자 |
| `category` | 문자열 또는 None | 원본 값 전달 | 예: `academic`, `scholarship` |
| `metadata` | JSON 객체 | 원본 값 복사 | 문자열 키, JSON 값만 사용; datetime·set·NaN·Infinity 등은 거부 |

`IngestionResult`는 `document`와 비어 있지 않은 `chunks` 목록을 담습니다. JSON으로 출력하면 UUID는 문자열로 변환됩니다. metadata 기본값과 중첩 객체는 문서·Chunk끼리 공유하지 않습니다.

source에는 `academic/calendar.txt` 같은 상대 경로나 원문 URL을 지정합니다. 로컬 파일의 절대 경로가 자동으로 들어가지 않습니다. source가 같으면 파일 위치나 내용이 달라져도 같은 Document ID이므로, 서로 다른 원문에는 서로 다른 source를 부여하세요.

### NLP 담당과의 splitter 규약

`TextSplitter` 타입은 `Callable[[str], Sequence[str]]`입니다. 함수는 원문 문자열을 받아 **순서가 있는 문자열 목록**을 반환합니다. 토큰·문단 분할, overlap 등 전략은 NLP 담당이 결정합니다. Backend는 전략에 관여하지 않고 결과에 ID와 출처를 붙입니다.

- 빈 문자열과 공백뿐인 문자열은 제외합니다.
- 유효한 문자열이 하나도 없으면 `ValueError`입니다.
- 문자열 하나, bytes, generator, 문자열 이외의 항목을 반환하면 `TypeError`입니다.
- splitter 자체에서 발생한 오류는 호출자에게 전달합니다.
- 기본 splitter는 제공하지 않으므로 호출자가 반드시 지정해야 합니다.

### TXT → IngestionResult 예시

가상환경의 Python에서 아래 코드를 실행합니다. 이 예시는 임시 TXT를 만들기 때문에 기존 지식 파일이나 `.env`, Docker가 필요 없습니다. `str.splitlines`는 연결 방법을 보여주는 예시이며 실제 Chunking 전략을 확정한 것이 아닙니다.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from app.document.ingestion import prepare_txt_ingestion

with TemporaryDirectory() as directory:
    path = Path(directory) / "academic.txt"
    path.write_text("등록 일정 안내\n장학금 신청 안내\n", encoding="utf-8")
    result = prepare_txt_ingestion(
        path,
        source="academic/calendar.txt",
        splitter=str.splitlines,
        category="academic",
        metadata={"year": 2026, "tags": ["학사"]},
    )
    print(result.model_dump_json(indent=2))
```

팀이 준비한 실제 TXT를 사용할 때에는 `path`와 `source`를 해당 파일·출처로 바꾸고 NLP splitter 함수를 전달합니다. Loader는 UTF-8과 UTF-8 BOM, `.txt`/`.TXT`를 지원합니다. 없는 파일은 `FileNotFoundError`, 디렉터리는 `IsADirectoryError`, 잘못된 인코딩은 `UnicodeDecodeError`입니다. 일반 파일이 아니거나 확장자가 다르거나 내용이 비어 있으면 `ValueError`, 데이터 필드가 잘못되면 Pydantic `ValidationError`입니다.

### 실제 Vector를 Qdrant에 저장하기

Qdrant에는 TXT 파일 대신 Chunk의 **UUID + Vector + Payload**를 저장합니다. payload 필드는 `document_id`, `chunk_index`, `text`, `source`, `category`, `metadata`입니다. Document 전체 원문이나 로컬 파일 경로를 추가로 저장하지 않습니다.

다음 함수는 임베딩 단계에서 이미 생성한 Vector를 받는 사용 예시입니다. Vector 목록은 `prepared.chunks`와 같은 순서여야 합니다. `client`에는 FastAPI lifespan에서 만든 `app.state.qdrant_client`, `settings`에는 `app.state.settings`를 전달할 수 있습니다.

```python
from collections.abc import Sequence

from qdrant_client import AsyncQdrantClient

from app.clients.qdrant import ensure_collection, upsert_chunks
from app.core.config import Settings
from app.document.schema import IngestionResult


async def store_prepared_chunks(
    client: AsyncQdrantClient,
    settings: Settings,
    prepared: IngestionResult,
    vectors: Sequence[Sequence[float]],
) -> int:
    await ensure_collection(
        client,
        collection_name=settings.qdrant_collection_name,
        vector_size=settings.qdrant_vector_size,
        distance=settings.qdrant_distance,
    )
    return await upsert_chunks(
        client,
        prepared.chunks,
        vectors,
        collection_name=settings.qdrant_collection_name,
        vector_size=settings.qdrant_vector_size,
    )
```

Embedding 모델을 선택한 뒤 `.env`에 `QDRANT_VECTOR_SIZE`를 모델의 실제 출력 차원으로 설정하고, 모델에 맞는 `QDRANT_DISTANCE`를 선택하세요. 예시용 차원을 운영 설정으로 사용하지 않습니다. 기존 컬렉션의 차원·거리 함수가 다르거나 named/sparse/multivector 구성이면 컬렉션 준비 함수가 `ValueError`를 내며 기존 데이터를 삭제·재생성하지 않습니다. 연결 오류도 그대로 전달합니다.

`upsert_chunks`는 전체 입력의 개수·차원·유한한 실수 여부를 검증한 뒤 한 번의 upsert를 실행합니다. bool, 문자열, NaN·Infinity는 벡터 성분으로 허용하지 않습니다. 두 목록이 모두 비어 있으면 외부 요청 없이 0을 반환합니다. `wait=True`로 적용 완료를 기다리고, 완료된 상태일 때 처리한 Chunk 수를 반환합니다. 반환값은 새로 늘어난 Point 수가 아닙니다. 이 함수들은 전달받은 클라이언트를 종료하지 않습니다.

### 현재 제한과 후속 연결

같은 source와 같은 Chunk 순서로 재적재하면 동일 UUID의 Point가 갱신되므로 중복 Point가 늘어나지 않습니다. 다만 원문 변경·splitter 변경으로 Chunk 수가 줄어들면 이전의 뒤쪽 Point가 남습니다. source 변경도 별도 Document로 처리합니다. **문서 교체 시 잔여 Point 정리, Qdrant 적재의 여러 배치 처리·재시도·병렬화는 아직 제공하지 않습니다.**

3주차에서 실제 E5 임베딩과 검색을 연결했습니다. NLP splitter의 실제 전략 연결, 문서 교체·잔여 Point 정리, 검색 품질 실험은 후속 작업입니다. PostgreSQL Document 테이블·업로드 API·Document CRUD·유료 API 호출은 추가하지 않았습니다. 모델 다운로드는 아래의 명시적 `prepare-model` 명령에서만 수행합니다.

## 3주차 실제 Embedding·적재·검색

초기 모델은 [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small/blob/main/README.md)입니다. **CPU 추론만 사용하며 학습·파인튜닝은 하지 않습니다.** PyTorch `2.14.1`, Transformers `5.20.2`, Python `3.12.14`에서 설치·import·추론을 확인했습니다.

고정 리비전은 `614241f622f53c4eeff9890bdc4f31cfecc418b3`이며 tokenizer와 weights 모두 같은 리비전을 사용합니다. 모델은 384차원, attention mask를 반영한 mean pooling, L2 정규화를 사용합니다. 문서는 `passage: `, 질문은 `query: ` 접두사를 **추론 입력에만** 붙입니다. 원문·출처·Qdrant payload는 변하지 않습니다.

### 1. 환경과 모델 준비

아래 명령은 가상환경을 활성화한 **backend** 디렉터리에서 실행합니다. 처음 실행하는 팀원은 위 절차대로 `.env.example`을 `.env`로 복사하세요. 기존 `.env`를 덮어쓰지 말고, E5 설정을 추가하거나 다음 환경변수로 지정합니다.

```bash
python -m pip install -r requirements.txt
export QDRANT_COLLECTION_NAME=artificial_soul_e5_small_v1
export QDRANT_VECTOR_SIZE=384
export QDRANT_DISTANCE=Cosine
python -m app.rag.cli prepare-model
```

이 명령만 Hugging Face에서 필요한 모델 파일을 내려받습니다. 새 리비전의 `main`을 자동 추적하지 않습니다. HTTP 요청·앱 import·시작·Health에서는 다운로드하지 않으며, 첫 실제 검색/적재에서 준비된 로컬 스냅샷만 지연 로드합니다. 모델 파일이 없으면 검색은 안전한 503 응답으로 준비 명령을 안내합니다. CPU 로드·추론은 작업 스레드에서 실행하고, 프로세스 내 공유 모델을 잠금으로 보호합니다.

캐시는 기본 `backend/.cache/huggingface`이며 Git과 Docker 빌드에서 제외합니다. 캐시를 지우면 `prepare-model`을 다시 실행하세요. 이미지에 모델을 복사하지 않으므로 컨테이너에서 사용할 때에는 별도 모델 준비와 쓰기 가능한 캐시 경로/볼륨이 필요합니다.

Windows PowerShell에서는 환경변수 설정을 다음으로 바꿉니다. 나머지 Python 명령은 같습니다.

```powershell
$env:QDRANT_COLLECTION_NAME = "artificial_soul_e5_small_v1"
$env:QDRANT_VECTOR_SIZE = "384"
$env:QDRANT_DISTANCE = "Cosine"
```

### 2. Qdrant 실행과 샘플 TXT 적재

```bash
docker compose up -d postgres qdrant
python -m app.rag.cli index-txt examples/knowledge/university.txt \
  --source examples/university.txt --category sample \
  --metadata '{"sample":true}' --splitter lines
```

`examples/knowledge/university.txt`는 처리 검증용 가상 대학 정보 4줄이며 실제 학교 공지가 아닙니다. `--splitter lines`는 줄바꿈을 이용하는 **샘플 전략**입니다. 위 명령을 반복하면 같은 4개 UUID를 갱신하며 Point 수는 늘어나지 않습니다. CLI 출력의 `processed_chunks`는 처리 수로, 새로 추가된 Point 수와 다릅니다.

NLP의 실제 함수를 연결할 때에는 `--splitter package.module:function`을 전달합니다. 함수는 기존 `Callable[[str], Sequence[str]]` 규약을 지켜야 합니다. `prepare_txt_ingestion(..., splitter=nlp_splitter)`와 `index_knowledge(prepared, client, provider, settings)`를 내부 코드에서 직접 호출해도 됩니다.

적재는 전체 Chunk의 임베딩 개수·차원·유한한 값·0벡터 여부를 검증한 후 기존 `ensure_collection()`·`upsert_chunks()`를 호출합니다. 모델 식별 정보는 컬렉션 metadata의 `artificial_soul_embedding`에 저장하고, Chunk payload는 그대로 유지합니다. 이미 존재하는 식별 정보 없는 컬렉션은 빈 상태라도 자동 인수하지 않습니다. 새 모델 전용 이름으로 적재하세요.

### 3. API 실행과 검색

위와 같은 환경변수가 설정된 터미널에서 실행합니다.

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

다른 터미널에서 호출하거나 [Swagger](http://127.0.0.1:8000/docs)의 RAG retrieval 항목을 사용합니다.

```bash
curl -i http://127.0.0.1:8000/api/rag/retrieve \
  -H 'Content-Type: application/json' \
  --data '{"question":"장학금 신청 방법을 알려주세요","top_k":3}'
```

HTTP 200 응답 예시입니다. UUID와 점수는 예시이며 점수는 정답 확률이 아닙니다.

```json
{
  "question": "장학금 신청 방법을 알려주세요",
  "top_k": 3,
  "results": [
    {
      "chunk_id": "11111111-1111-4111-8111-111111111111",
      "document_id": "22222222-2222-4222-8222-222222222222",
      "chunk_index": 0,
      "text": "장학금 신청은 학생지원시스템의 장학 메뉴에서 할 수 있으며 재학 증명서와 성적 증명서를 제출해야 합니다.",
      "source": "examples/university.txt",
      "category": "sample",
      "metadata": {"sample": true},
      "score": 0.9044
    }
  ]
}
```

`top_k` 기본값은 5, 범위는 1~20이며 실제 결과가 더 적을 수 있습니다. 질문은 문자열 1~10000자이며 공백뿐인 입력과 정의되지 않은 필드를 거부합니다. Qdrant `query_points()`로 payload를 포함해 검색하고 순서를 유지하며 원시 벡터는 반환하지 않습니다. 임의의 점수 임계값은 적용하지 않습니다. 유효한 빈 컬렉션은 `results: []`이고, 없는 컬렉션은 503입니다. 검색 경로는 컬렉션 생성·Point 적재·모델 다운로드를 하지 않습니다.

| HTTP | 오류 code 또는 상황 |
| --- | --- |
| 422 | `VALIDATION_ERROR`, `EMBEDDING_INPUT_INVALID`: 질문·top_k·토큰 길이 오류 |
| 503 | `EMBEDDING_UNAVAILABLE`: 로컬 모델 미준비 또는 추론 불가 |
| 503 | `RETRIEVAL_CONFIGURATION_ERROR`: 차원·거리 함수·모델 식별 정보 불일치 |
| 503 | `COLLECTION_NOT_READY`: 적재할 검색 컬렉션 없음 |
| 503 | `SEARCH_UNAVAILABLE`: Qdrant 연결·검색 불가 |
| 504 | `RETRIEVAL_TIMEOUT`: 질문 임베딩/검색 전체 제한 또는 Qdrant 요청 시간초과 |
| 500 | `RETRIEVAL_DATA_INVALID`, `INTERNAL_ERROR`: 손상된 payload 또는 예상하지 못한 오류 |

오류는 `{"detail":{"code":"...","message":"..."}}` 형식이며 원본 예외·연결 주소·민감 입력을 반환하지 않습니다. 검색 전체 제한은 기본 30초, Qdrant 클라이언트 제한은 10초이며 Health는 기존대로 서비스별 3초입니다.

### 4. 토큰 제한과 NLP 모델 교체

- E5의 최대 입력은 **접두사·특수 토큰을 포함해 512토큰**입니다. 글자 수와 토큰 수는 다릅니다. 조용히 잘라 저장하지 않고 오류를 반환하므로 NLP splitter가 이 한도 안에서 Chunk를 만들도록 해야 합니다. 긴 질문은 HTTP 422입니다.
- 교체 가능한 경계는 `EmbeddingProvider`의 `embed_documents()`, `embed_query()`, `dimension`, `identity`입니다. `identity`는 모델 ID·고정 리비전·전처리/정규화 버전을 식별합니다.
- 현재 E5 provider는 이 모델만 지원합니다. 다른 모델명만 설정해서 E5 규칙을 그대로 적용하지 않습니다. NLP 담당이 다른 모델을 선택하면 해당 모델의 접두사·pooling·정규화·차원에 맞는 provider를 구현하고 새 identity를 사용합니다.
- **모델이나 리비전이 바뀌면 차원이 같더라도 별도 컬렉션에 다시 적재**합니다. 기존 metadata를 덮어써 재사용하지 않습니다. 현재 적재·검색은 Cosine 구성만 지원합니다.
- 문서 내용 변경으로 Chunk 수가 줄어들 때 이전 뒤쪽 Point를 지우는 재색인 정책은 아직 없습니다. 수동 적재는 한 컬렉션에 한 작업씩 실행하세요. 분산 동시 적재·잠금은 지원하지 않습니다.
- 검색 API는 로컬 개발용이며 JWT가 없습니다. 운영 공개와 인증 연동은 후속 작업입니다. LLM 답변·Context·Chat 저장·SSE·`POST /api/rag/query`는 아직 구현하지 않았습니다.

### 5. 테스트와 관찰한 결과

```bash
# 모델 다운로드와 실제 DB/Qdrant 없이 실행
python -m pytest -q -m 'not integration'

# 준비한 실제 로컬 E5 모델과 실제 Qdrant 사용
RUN_RAG_INTEGRATION=1 QDRANT_URL=http://127.0.0.1:6333 \
  python -m pytest -q -s -m rag_integration

# 기존 2주차 Qdrant 적재 테스트까지 함께 실행
RUN_QDRANT_INTEGRATION=1 RUN_RAG_INTEGRATION=1 \
  QDRANT_URL=http://127.0.0.1:6333 python -m pytest -q
```

PowerShell에서는 필요한 실행 플래그를 `$env:RUN_RAG_INTEGRATION = "1"`과 같이 설정하고 `python -m pytest -q -s -m rag_integration`을 실행합니다. 완료 후 `Remove-Item Env:RUN_RAG_INTEGRATION`으로 해제할 수 있습니다.

기본 테스트는 모의 provider·Qdrant와 작은 합성 Tensor로 접두사, padding 제외, 정규화, 512토큰 경계, 전체 입력 검증, 순서·출처·metadata, 안전한 오류, 시간초과, 모델 없이 시작하는 Health와 자원 정리를 검증합니다. 실제 모델 가중치를 다운로드하지 않습니다.

실제 통합 테스트는 고유한 `test_rag_e5_<UUID>` 컬렉션에서 한국어 샘플 4개를 적재·재적재하고 Point 수가 4로 유지되는지, 실제 384차원 벡터와 HTTP 검색의 UUID·원문·출처를 확인합니다. 생성한 테스트 컬렉션만 `finally`에서 삭제하고 삭제 여부도 확인합니다.

고정 모델 리비전으로 실행한 샘플 질문의 Top-3 관찰은 Chunk 0(장학금) 0.9044, Chunk 3(기숙사) 0.8345, Chunk 1(수강신청) 0.8161이었습니다. 이는 파이프라인 연결 확인이며 실제 대학 지식 전반의 검색 품질 평가가 아닙니다. NLP 담당의 평가 질문셋·Top-K·임계값·Chunking 비교가 별도로 필요합니다.

## Spring 개발자 관점

Chat 구조는 Spring에서 `chat.controller`, `chat.service`, `chat.repository`로 기능별 패키지를 묶는 방식에 대응합니다. Document·RAG는 데이터 처리 역할에 필요한 파일만 두는 구조입니다.

| FastAPI / Python | Spring에서 가까운 개념 |
| --- | --- |
| `APIRouter` | `@RestController` |
| Service 함수 또는 클래스 | `@Service` |
| Repository 함수 또는 클래스 | `@Repository` |
| Pydantic Schema | Request/Response DTO와 입력 검증 |
| SQLAlchemy Model | JPA Entity에 해당하는 ORM 데이터 표현 |
| pydantic-settings의 `Settings` | `application.yml` + `@ConfigurationProperties` |
| SQLAlchemy Async Engine | 커넥션 풀을 관리하는 `DataSource` |
| `AsyncSession` | 요청별 DB 작업과 트랜잭션을 관리하는 세션 |
| `Depends(get_session)` | 의존성 주입; 요청이 끝나면 `yield` 이후 정리 |
| FastAPI `lifespan` | 앱 시작·종료 시 Bean 리소스 초기화와 정리 |
| `clients` | 외부 서비스용 HTTP Client / Gateway |

Engine과 Qdrant 클라이언트는 앱마다 하나씩 만들고 `app.state`에 보관합니다. Engine 생성은 DB 연결을 수행하지 않으며, Qdrant의 생성 시 버전 확인도 꺼 두었습니다. 실제 네트워크 확인은 readiness 호출 시에만 합니다. 종료 시 Engine은 `dispose()`, Qdrant는 `close()`로 정리합니다. `AsyncExitStack`은 초기화 중 오류가 나도 이미 만든 리소스를 정리합니다.

향후 Router는 `Depends(get_session)`으로 요청별 `AsyncSession`을 받아 Service·Repository에 전달합니다. 세션은 요청 간 공유하지 않고, 트랜잭션 commit은 업무 코드에서 명시합니다. 세션이 닫히면 commit하지 않은 작업은 rollback됩니다. 현재는 Entity, 테이블 생성, 마이그레이션, 추상 Repository, Unit of Work를 추가하지 않았습니다.

DDD는 업무 규칙과 경계를 설계하는 접근으로, 특정 폴더 이름 자체가 DDD를 보장하지는 않습니다. 실제 기능과 업무 규칙이 생길 때 Service의 책임과 도메인 모델 분리를 검토합니다.

## 중지와 문제 해결

FastAPI는 실행한 터미널에서 `Ctrl+C`로 중지합니다.

```bash
docker compose stop
docker compose up -d
```

컨테이너를 제거하려면 `docker compose down`을 사용합니다. named volume은 남아 데이터를 유지합니다. `docker compose down -v`는 DB와 Qdrant 데이터를 삭제하므로 개발 데이터를 초기화하려는 경우에만 사용하세요.

| 증상 | 확인할 내용 |
| --- | --- |
| Python 버전이 3.13 등으로 표시됨 | Python 3.12로 `.venv`를 생성했는지, IDE interpreter가 `.venv`인지 확인 |
| `No module named app` | backend 디렉터리에서 실행하거나 IDE working directory를 backend로 지정 |
| `DATABASE_URL` / `QDRANT_URL` 설정 오류 | `.env` 생성 여부, 환경변수 이름, asyncpg URL 형식 확인 |
| Docker daemon 연결 실패 | Docker Desktop 또는 Docker daemon 실행 여부 확인 |
| 5432 또는 6333 포트 충돌 | `.env`의 `POSTGRES_PORT` 또는 `QDRANT_PORT`와 해당 연결 URL 포트를 함께 수정 |
| 8000 포트 충돌 | Uvicorn의 `--port`를 변경하고 같은 포트로 접속 |
| readiness의 `postgres: error` | `docker compose logs postgres`, 계정·DB명·URL·초기화 완료 여부 확인 |
| readiness의 `qdrant: error` | `docker compose logs qdrant`, `QDRANT_URL`, `/readyz` 응답 확인 |
| `.env` 수정이 반영되지 않음 | Uvicorn 재시작, 셸 환경변수의 우선 적용 여부 확인 |

예를 들어 PostgreSQL을 호스트의 5434 포트로 실행하려면 `.env`의 `POSTGRES_PORT=5434`와 `DATABASE_URL`의 호스트 포트를 5434로 바꾸고 `docker compose up -d`로 반영합니다. 컨테이너 내부 포트 5432는 유지합니다. Qdrant도 같은 방식으로 호스트 포트와 `QDRANT_URL`을 함께 변경합니다.

PostgreSQL의 `POSTGRES_*` 초기화 값은 빈 volume의 첫 실행에만 적용됩니다. 이미 생성한 DB의 비밀번호를 `.env` 변경만으로 바꿀 수는 없습니다. 기존 데이터를 유지하려면 DB에서 계정을 변경하고, 초기화할 경우에만 volume을 삭제합니다.

## 백엔드 Dockerfile

현재 개발 기본 경로는 로컬 Uvicorn입니다. Dockerfile은 Python 3.12 이미지에 의존성과 앱을 설치하고 일반 사용자로 Uvicorn을 실행하도록 준비했습니다. `.env`는 이미지에 복사하지 않습니다.

```bash
docker build -t artificial-soul-backend:dev .
```

Compose 인프라에 연결해 컨테이너 실행을 확인하려면, 기본 개발용 계정을 기준으로 다음과 같이 실행합니다. 컨테이너에서는 `localhost` 대신 Compose 서비스 이름을 사용합니다. 계정을 변경했다면 아래 `DATABASE_URL`도 맞춰야 합니다.

```bash
docker run --rm --name artificial-soul-api \
  --network artificial-soul_default \
  -p 127.0.0.1:8001:8000 \
  --env-file .env \
  -e DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/artificial_soul \
  -e QDRANT_URL=http://qdrant:6333 \
  artificial-soul-backend:dev
```

접속 주소는 `http://127.0.0.1:8001/health/ready`입니다. 이 실행은 Compose 기본 서비스에 포함되지 않습니다.

## 다음 단계

첨부된 6주 스프린트 방향에 따라 개발합니다. 백엔드는 1~2주차 기반과 3주차 E5 기준 임베딩·적재·검색 API를 구현했습니다. NLP의 실제 splitter·모델 품질 비교는 별도이며, 다음 기능은 4주차 Context·LLM·답변/출처 응답입니다.

| 주차 | Backend 개발 목표 |
| --- | --- |
| 1주차 | FastAPI 구조, PostgreSQL·Qdrant·Docker 연결, Health API |
| 2주차 | Document 패키지, TXT 로딩·Chunk 처리 통합, ingestion 구조 |
| 3주차 | Embedding 연동, Qdrant Index/Search, Retrieval |
| 4주차 | Retrieval + Context + LLM 통합, 답변·Source 응답으로 End-to-End MVP |
| 5주차 | Chat/Message 저장, SSE Streaming, 예외 처리 |
| 6주차 | Logging, API·통합·부하 테스트, 성능 측정과 배포 |

4주차 종료 시점의 핵심 마일스톤은 **텍스트 질문 → 관련 Chunk 검색 → Context → LLM → 답변 + Source**입니다. Fine-tuning·자체 모델 학습·이미지 입력/처리·사용자 파일 업로드·복잡한 Document CRUD·Redis·Kafka·Kubernetes는 MVP에서 제외합니다.
