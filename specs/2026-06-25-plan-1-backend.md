# Backend Core — Implementation Plan (Plano 1/3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** API REST FastAPI com autenticação Supabase, endpoints de transações, resumo, limites por categoria e convites familiares.

**Architecture:** FastAPI app com routers por domínio, autenticação via JWT do Supabase, acesso ao banco via Supabase Python SDK. Sem ORM — queries diretas pelo SDK.

**Tech Stack:** Python 3.12, FastAPI 0.111+, Supabase Python SDK 2.4+, PyJWT 2.8+, Pydantic 2.7+, pytest + httpx (testes).

## Global Constraints

- Python 3.12 obrigatório
- Apenas BRL — `amount` sempre em float com 2 casas decimais
- Respostas de erro em português
- JWT validado contra `SUPABASE_JWT_SECRET` com audience `"authenticated"`
- Categorias válidas: `Alimentação, Transporte, Moradia, Saúde, Educação, Lazer, Vestuário, Outros`
- Nenhum endpoint aceita requisição sem token válido (exceto health check)

---

## Estrutura de Arquivos

```
backend/
├── pyproject.toml
├── .env.example
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── auth.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── transaction.py
│   │   ├── group.py
│   │   └── limit.py
│   └── routers/
│       ├── __init__.py
│       ├── transactions.py
│       ├── summary.py
│       ├── limits.py
│       └── groups.py
├── supabase/
│   └── migrations/
│       └── 001_initial_schema.sql
└── tests/
    ├── conftest.py
    ├── test_transactions.py
    ├── test_summary.py
    ├── test_limits.py
    └── test_groups.py
```

---

## Task 1: Setup do Projeto

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`

**Interfaces:**
- Produces: `app.config.settings` — objeto Settings com todas as env vars; `app.main.app` — instância FastAPI

- [ ] **Step 1: Criar `backend/pyproject.toml`**

```toml
[project]
name = "my-finance-bot-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.0",
    "supabase>=2.4.0",
    "pyjwt>=2.8.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.14.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Criar `backend/.env.example`**

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase-dashboard
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
OPENAI_API_KEY=sk-...
```

- [ ] **Step 3: Criar `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    supabase_jwt_secret: str
    telegram_bot_token: str
    openai_api_key: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
```

- [ ] **Step 4: Criar `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import transactions, summary, limits, groups

app = FastAPI(title="my-finance-bot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router)
app.include_router(summary.router)
app.include_router(limits.router)
app.include_router(groups.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Criar arquivos `__init__.py` vazios**

```bash
touch backend/app/__init__.py
touch backend/app/models/__init__.py
touch backend/app/routers/__init__.py
```

- [ ] **Step 6: Instalar dependências e verificar servidor sobe**

```bash
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Esperado: servidor rodando em `http://127.0.0.1:8000`, `GET /health` retorna `{"status": "ok"}`

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: setup backend project structure and FastAPI app"
```

---

## Task 2: Schema do Banco (Supabase Migrations)

**Files:**
- Create: `backend/supabase/migrations/001_initial_schema.sql`

**Interfaces:**
- Produces: tabelas `users`, `groups`, `group_members`, `transactions`, `category_limits`, `conversations`, `invites` no Supabase

- [ ] **Step 1: Criar `backend/supabase/migrations/001_initial_schema.sql`**

```sql
-- Extensão para UUIDs
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Tabela de perfis (estende auth.users do Supabase)
CREATE TABLE public.users (
  id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  name TEXT NOT NULL DEFAULT '',
  telegram_id BIGINT UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Grupos financeiros familiares
CREATE TABLE public.groups (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  owner_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Membros do grupo
CREATE TABLE public.group_members (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  group_id UUID REFERENCES public.groups(id) ON DELETE CASCADE NOT NULL,
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
  joined_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(group_id, user_id)
);

-- Transações financeiras
CREATE TABLE public.transactions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  group_id UUID REFERENCES public.groups(id) ON DELETE CASCADE NOT NULL,
  user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
  type TEXT NOT NULL CHECK (type IN ('income', 'expense')),
  category TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  date DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Limites mensais por categoria
CREATE TABLE public.category_limits (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  group_id UUID REFERENCES public.groups(id) ON DELETE CASCADE NOT NULL,
  category TEXT NOT NULL,
  monthly_limit NUMERIC(12,2) NOT NULL CHECK (monthly_limit > 0),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(group_id, category)
);

-- Histórico de conversa do bot (últimas 10 mensagens por usuário)
CREATE TABLE public.conversations (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
  messages JSONB NOT NULL DEFAULT '[]',
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convites para membros da família
CREATE TABLE public.invites (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  group_id UUID REFERENCES public.groups(id) ON DELETE CASCADE NOT NULL,
  invited_by UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  email TEXT NOT NULL,
  token TEXT NOT NULL UNIQUE DEFAULT gen_random_uuid()::text,
  accepted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS: habilitar para todas as tabelas
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.group_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.category_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invites ENABLE ROW LEVEL SECURITY;

-- Política básica: usuário vê apenas seus próprios dados
CREATE POLICY "users_own" ON public.users
  FOR ALL USING (auth.uid() = id);

CREATE POLICY "conversations_own" ON public.conversations
  FOR ALL USING (auth.uid() = user_id);

-- Políticas de grupo: ver dados do próprio grupo
CREATE POLICY "group_members_see_own_group" ON public.group_members
  FOR SELECT USING (
    auth.uid() = user_id OR
    EXISTS (
      SELECT 1 FROM public.group_members gm
      WHERE gm.group_id = group_members.group_id AND gm.user_id = auth.uid()
    )
  );

CREATE POLICY "transactions_group_members" ON public.transactions
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.group_members gm
      WHERE gm.group_id = transactions.group_id AND gm.user_id = auth.uid()
    )
  );

CREATE POLICY "limits_group_members" ON public.category_limits
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.group_members gm
      WHERE gm.group_id = category_limits.group_id AND gm.user_id = auth.uid()
    )
  );
```

- [ ] **Step 2: Executar migration no Supabase**

Acesse o Supabase Dashboard → SQL Editor → cole o conteúdo do arquivo e execute.

Verifique que todas as tabelas aparecem em Table Editor.

- [ ] **Step 3: Commit**

```bash
git add backend/supabase/
git commit -m "feat: add initial database schema with RLS policies"
```

---

## Task 3: Database Client e Auth Middleware

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/auth.py`
- Create: `backend/tests/conftest.py`

**Interfaces:**
- Produces:
  - `app.database.get_supabase() -> Client`
  - `app.auth.get_current_user(credentials) -> dict[str, str]` — retorna `{"id": str, "email": str}`

- [ ] **Step 1: Escrever teste para auth middleware**

Criar `backend/tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_user():
    return {"id": "user-uuid-123", "email": "test@example.com"}


@pytest.fixture
def valid_token():
    import jwt
    from app.config import settings
    payload = {
        "sub": "user-uuid-123",
        "email": "test@example.com",
        "aud": "authenticated",
        "role": "authenticated",
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
```

Criar `backend/tests/test_auth.py`:

```python
def test_health_no_auth(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_protected_endpoint_without_token(client):
    response = client.get("/transactions/")
    assert response.status_code == 403


def test_protected_endpoint_invalid_token(client):
    response = client.get(
        "/transactions/",
        headers={"Authorization": "Bearer token_invalido"}
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Rodar teste para verificar que falha**

```bash
cd backend
pytest tests/test_auth.py -v
```

Esperado: FAIL — `transactions` router ainda não existe

- [ ] **Step 3: Criar `backend/app/database.py`**

```python
from supabase import create_client, Client
from .config import settings


def get_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_key)
```

- [ ] **Step 4: Criar `backend/app/auth.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from .config import settings

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return {"id": payload["sub"], "email": payload.get("email", "")}
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )
```

- [ ] **Step 5: Criar router placeholder de transactions para o teste compilar**

Criar `backend/app/routers/transactions.py`:

```python
from fastapi import APIRouter, Depends
from ..auth import get_current_user

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/")
async def list_transactions(user: dict = Depends(get_current_user)):
    return []
```

- [ ] **Step 6: Criar routers placeholder para summary, limits, groups**

`backend/app/routers/summary.py`:
```python
from fastapi import APIRouter, Depends
from ..auth import get_current_user

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/")
async def get_summary(user: dict = Depends(get_current_user)):
    return {}
```

`backend/app/routers/limits.py`:
```python
from fastapi import APIRouter, Depends
from ..auth import get_current_user

router = APIRouter(prefix="/limits", tags=["limits"])


@router.get("/")
async def list_limits(user: dict = Depends(get_current_user)):
    return []
```

`backend/app/routers/groups.py`:
```python
from fastapi import APIRouter, Depends
from ..auth import get_current_user

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("/")
async def get_group(user: dict = Depends(get_current_user)):
    return {}
```

- [ ] **Step 7: Rodar testes — devem passar**

```bash
pytest tests/test_auth.py -v
```

Esperado: 3 testes PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/ backend/tests/
git commit -m "feat: add database client, JWT auth middleware, and router stubs"
```

---

## Task 4: Modelos Pydantic

**Files:**
- Create: `backend/app/models/transaction.py`
- Create: `backend/app/models/limit.py`
- Create: `backend/app/models/group.py`

**Interfaces:**
- Produces:
  - `TransactionCreate(amount, type, category, description, date)` → body do POST /transactions
  - `Transaction` → resposta com id, user_id, group_id, created_at
  - `LimitCreate(category, monthly_limit)` → body do POST /limits
  - `Limit` → resposta com id, group_id, spent, percent_used
  - `InviteCreate(email)` → body do POST /groups/invite

- [ ] **Step 1: Criar `backend/app/models/transaction.py`**

```python
from pydantic import BaseModel, field_validator
from datetime import date
from enum import Enum
from typing import Optional

VALID_CATEGORIES = {
    "Alimentação", "Transporte", "Moradia", "Saúde",
    "Educação", "Lazer", "Vestuário", "Outros"
}


class TransactionType(str, Enum):
    income = "income"
    expense = "expense"


class TransactionCreate(BaseModel):
    amount: float
    type: TransactionType
    category: str
    description: str = ""
    date: date = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Valor deve ser positivo")
        return round(v, 2)

    @field_validator("category")
    @classmethod
    def category_valid(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Categoria inválida. Use uma de: {', '.join(sorted(VALID_CATEGORIES))}")
        return v

    @field_validator("date", mode="before")
    @classmethod
    def default_date(cls, v):
        if v is None:
            return date.today()
        return v


class Transaction(TransactionCreate):
    id: str
    user_id: str
    group_id: str
    created_at: str
```

- [ ] **Step 2: Criar `backend/app/models/limit.py`**

```python
from pydantic import BaseModel, field_validator

from .transaction import VALID_CATEGORIES


class LimitCreate(BaseModel):
    category: str
    monthly_limit: float

    @field_validator("category")
    @classmethod
    def category_valid(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"Categoria inválida: {v}")
        return v

    @field_validator("monthly_limit")
    @classmethod
    def limit_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Limite deve ser positivo")
        return round(v, 2)


class Limit(LimitCreate):
    id: str
    group_id: str
    spent: float = 0.0
    percent_used: float = 0.0
```

- [ ] **Step 3: Criar `backend/app/models/group.py`**

```python
from pydantic import BaseModel, EmailStr


class InviteCreate(BaseModel):
    email: str


class InviteResponse(BaseModel):
    id: str
    email: str
    group_id: str
    token: str
```

- [ ] **Step 4: Escrever testes de validação dos modelos**

Criar `backend/tests/test_models.py`:

```python
import pytest
from datetime import date
from app.models.transaction import TransactionCreate, TransactionType


def test_transaction_amount_positive():
    with pytest.raises(ValueError):
        TransactionCreate(amount=-10, type="expense", category="Alimentação")


def test_transaction_invalid_category():
    with pytest.raises(ValueError):
        TransactionCreate(amount=10, type="expense", category="Mercado")


def test_transaction_valid():
    t = TransactionCreate(amount=50.0, type="expense", category="Alimentação")
    assert t.amount == 50.0
    assert t.date == date.today()


def test_transaction_amount_rounds():
    t = TransactionCreate(amount=50.999, type="expense", category="Alimentação")
    assert t.amount == 51.0
```

- [ ] **Step 5: Rodar testes**

```bash
pytest tests/test_models.py -v
```

Esperado: 4 testes PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/ backend/tests/test_models.py
git commit -m "feat: add pydantic models with validation for transactions and limits"
```

---

## Task 5: Endpoints de Transações

**Files:**
- Modify: `backend/app/routers/transactions.py`
- Create: `backend/tests/test_transactions.py`

**Interfaces:**
- Consumes: `get_current_user`, `get_supabase`, `TransactionCreate`, `Transaction`
- Produces:
  - `POST /transactions/` → cria transação, retorna `Transaction`
  - `GET /transactions/` → lista com filtros `?month=YYYY-MM&category=X&type=income|expense`

- [ ] **Step 1: Escrever testes**

Criar `backend/tests/test_transactions.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import *


def test_create_transaction_success(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.single.return_value.execute.return_value.data = {
        "group_id": "group-uuid-456"
    }
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{
        "id": "tx-uuid-789",
        "user_id": "user-uuid-123",
        "group_id": "group-uuid-456",
        "amount": 50.0,
        "type": "expense",
        "category": "Alimentação",
        "description": "Mercado",
        "date": "2026-06-25",
        "created_at": "2026-06-25T12:00:00Z",
    }]

    with patch("app.routers.transactions.get_supabase", return_value=mock_db):
        response = client.post(
            "/transactions/",
            json={
                "amount": 50.0,
                "type": "expense",
                "category": "Alimentação",
                "description": "Mercado",
                "date": "2026-06-25",
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 201
    assert response.json()["amount"] == 50.0
    assert response.json()["category"] == "Alimentação"


def test_create_transaction_invalid_category(client, valid_token):
    response = client.post(
        "/transactions/",
        json={"amount": 50.0, "type": "expense", "category": "Mercado"},
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 422


def test_list_transactions(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch("app.routers.transactions.get_supabase", return_value=mock_db):
        response = client.get(
            "/transactions/",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Rodar testes — devem falhar**

```bash
pytest tests/test_transactions.py -v
```

Esperado: FAIL — implementação incompleta

- [ ] **Step 3: Implementar `backend/app/routers/transactions.py`**

```python
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from supabase import Client

from ..auth import get_current_user
from ..database import get_supabase
from ..models.transaction import Transaction, TransactionCreate

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _get_user_group(db: Client, user_id: str) -> str:
    result = (
        db.table("group_members")
        .select("group_id")
        .eq("user_id", user_id)
        .limit(1)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não pertence a nenhum grupo. Crie um grupo ou aceite um convite.",
        )
    return result.data["group_id"]


@router.post("/", response_model=Transaction, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    data: TransactionCreate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    group_id = _get_user_group(db, user["id"])
    result = (
        db.table("transactions")
        .insert({
            "user_id": user["id"],
            "group_id": group_id,
            "amount": data.amount,
            "type": data.type.value,
            "category": data.category,
            "description": data.description,
            "date": str(data.date),
        })
        .execute()
    )
    return result.data[0]


@router.get("/", response_model=list[Transaction])
async def list_transactions(
    month: Optional[str] = Query(None, description="Formato YYYY-MM, ex: 2026-06"),
    category: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    group_id = _get_user_group(db, user["id"])
    query = db.table("transactions").select("*").eq("group_id", group_id)

    if month:
        year, mon = month.split("-")
        first_day = f"{year}-{mon}-01"
        import calendar
        last_day = f"{year}-{mon}-{calendar.monthrange(int(year), int(mon))[1]}"
        query = query.gte("date", first_day).lte("date", last_day)

    if category:
        query = query.eq("category", category)

    if type:
        query = query.eq("type", type)

    result = query.order("date", desc=True).execute()
    return result.data
```

- [ ] **Step 4: Rodar testes**

```bash
pytest tests/test_transactions.py -v
```

Esperado: 3 testes PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/transactions.py backend/tests/test_transactions.py
git commit -m "feat: implement transactions CRUD endpoints with group filtering"
```

---

## Task 6: Endpoint de Resumo Financeiro

**Files:**
- Modify: `backend/app/routers/summary.py`
- Create: `backend/tests/test_summary.py`

**Interfaces:**
- Consumes: `get_current_user`, `get_supabase`
- Produces:
  - `GET /summary/?month=YYYY-MM` → `{balance, total_income, total_expense, by_category: [{category, total}]}`

- [ ] **Step 1: Escrever teste**

Criar `backend/tests/test_summary.py`:

```python
from unittest.mock import patch, MagicMock
from tests.conftest import *


def test_get_summary_current_month(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = [
        {"type": "income", "amount": 5000.0, "category": "Outros"},
        {"type": "expense", "amount": 150.0, "category": "Alimentação"},
        {"type": "expense", "amount": 50.0, "category": "Transporte"},
    ]
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.single.return_value.execute.return_value.data = {
        "group_id": "group-uuid-456"
    }

    with patch("app.routers.summary.get_supabase", return_value=mock_db):
        response = client.get(
            "/summary/?month=2026-06",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total_income"] == 5000.0
    assert data["total_expense"] == 200.0
    assert data["balance"] == 4800.0
    assert len(data["by_category"]) == 2
```

- [ ] **Step 2: Rodar teste — deve falhar**

```bash
pytest tests/test_summary.py -v
```

Esperado: FAIL

- [ ] **Step 3: Implementar `backend/app/routers/summary.py`**

```python
import calendar
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from supabase import Client

from ..auth import get_current_user
from ..database import get_supabase
from ..routers.transactions import _get_user_group

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/")
async def get_summary(
    month: Optional[str] = Query(None, description="YYYY-MM, padrão: mês atual"),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    if not month:
        today = date.today()
        month = f"{today.year}-{today.month:02d}"

    year, mon = month.split("-")
    first_day = f"{year}-{mon}-01"
    last_day = f"{year}-{mon}-{calendar.monthrange(int(year), int(mon))[1]}"

    group_id = _get_user_group(db, user["id"])
    result = (
        db.table("transactions")
        .select("type, amount, category")
        .eq("group_id", group_id)
        .gte("date", first_day)
        .lte("date", last_day)
        .execute()
    )

    transactions = result.data or []
    total_income = sum(t["amount"] for t in transactions if t["type"] == "income")
    total_expense = sum(t["amount"] for t in transactions if t["type"] == "expense")

    by_category: dict[str, float] = {}
    for t in transactions:
        if t["type"] == "expense":
            by_category[t["category"]] = by_category.get(t["category"], 0) + t["amount"]

    return {
        "month": month,
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "balance": round(total_income - total_expense, 2),
        "by_category": [
            {"category": k, "total": round(v, 2)}
            for k, v in sorted(by_category.items(), key=lambda x: -x[1])
        ],
    }
```

- [ ] **Step 4: Rodar teste**

```bash
pytest tests/test_summary.py -v
```

Esperado: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/summary.py backend/tests/test_summary.py
git commit -m "feat: implement monthly summary endpoint with income/expense breakdown"
```

---

## Task 7: Endpoints de Limites por Categoria

**Files:**
- Modify: `backend/app/routers/limits.py`
- Create: `backend/tests/test_limits.py`

**Interfaces:**
- Consumes: `get_current_user`, `get_supabase`, `LimitCreate`, `Limit`
- Produces:
  - `POST /limits/` → cria ou atualiza limite, retorna `Limit` com `spent` e `percent_used`
  - `GET /limits/` → lista todos os limites do grupo com % utilizado no mês atual

- [ ] **Step 1: Escrever testes**

Criar `backend/tests/test_limits.py`:

```python
from unittest.mock import patch, MagicMock
from tests.conftest import *


def test_create_limit(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.single.return_value.execute.return_value.data = {
        "group_id": "group-uuid-456"
    }
    mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{
        "id": "limit-uuid",
        "group_id": "group-uuid-456",
        "category": "Alimentação",
        "monthly_limit": 500.0,
    }]
    mock_db.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = []

    with patch("app.routers.limits.get_supabase", return_value=mock_db):
        response = client.post(
            "/limits/",
            json={"category": "Alimentação", "monthly_limit": 500.0},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["monthly_limit"] == 500.0
    assert data["spent"] == 0.0
    assert data["percent_used"] == 0.0


def test_create_limit_invalid_category(client, valid_token):
    response = client.post(
        "/limits/",
        json={"category": "Supermercado", "monthly_limit": 500.0},
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Rodar testes — devem falhar**

```bash
pytest tests/test_limits.py -v
```

- [ ] **Step 3: Implementar `backend/app/routers/limits.py`**

```python
import calendar
from datetime import date
from fastapi import APIRouter, Depends, status
from supabase import Client

from ..auth import get_current_user
from ..database import get_supabase
from ..models.limit import Limit, LimitCreate
from ..routers.transactions import _get_user_group

router = APIRouter(prefix="/limits", tags=["limits"])


def _get_month_spent(db: Client, group_id: str, category: str) -> float:
    today = date.today()
    first_day = f"{today.year}-{today.month:02d}-01"
    last_day = f"{today.year}-{today.month:02d}-{calendar.monthrange(today.year, today.month)[1]}"
    result = (
        db.table("transactions")
        .select("amount")
        .eq("group_id", group_id)
        .eq("category", category)
        .eq("type", "expense")
        .gte("date", first_day)
        .lte("date", last_day)
        .execute()
    )
    return round(sum(t["amount"] for t in (result.data or [])), 2)


@router.post("/", response_model=Limit, status_code=status.HTTP_201_CREATED)
async def upsert_limit(
    data: LimitCreate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    group_id = _get_user_group(db, user["id"])
    result = (
        db.table("category_limits")
        .upsert(
            {"group_id": group_id, "category": data.category, "monthly_limit": data.monthly_limit},
            on_conflict="group_id,category",
        )
        .execute()
    )
    limit_data = result.data[0]
    spent = _get_month_spent(db, group_id, data.category)
    percent = round((spent / data.monthly_limit) * 100, 1) if data.monthly_limit > 0 else 0.0
    return {**limit_data, "spent": spent, "percent_used": percent}


@router.get("/", response_model=list[Limit])
async def list_limits(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    group_id = _get_user_group(db, user["id"])
    result = db.table("category_limits").select("*").eq("group_id", group_id).execute()
    limits = []
    for lim in result.data or []:
        spent = _get_month_spent(db, group_id, lim["category"])
        percent = round((spent / lim["monthly_limit"]) * 100, 1) if lim["monthly_limit"] > 0 else 0.0
        limits.append({**lim, "spent": spent, "percent_used": percent})
    return limits
```

- [ ] **Step 4: Rodar testes**

```bash
pytest tests/test_limits.py -v
```

Esperado: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/limits.py backend/tests/test_limits.py
git commit -m "feat: implement category limits endpoints with monthly spend tracking"
```

---

## Task 8: Endpoints de Grupo e Convites

**Files:**
- Modify: `backend/app/routers/groups.py`
- Create: `backend/tests/test_groups.py`

**Interfaces:**
- Produces:
  - `POST /groups/` → cria grupo, retorna `{id, name}`
  - `POST /groups/invite` → cria convite, retorna `{id, email, token}`
  - `POST /groups/accept?token=X` → aceita convite, vincula usuário ao grupo

- [ ] **Step 1: Escrever testes**

Criar `backend/tests/test_groups.py`:

```python
from unittest.mock import patch, MagicMock
from tests.conftest import *


def test_create_group(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{
        "id": "group-uuid-456",
        "name": "Família Silva",
        "owner_id": "user-uuid-123",
    }]

    with patch("app.routers.groups.get_supabase", return_value=mock_db):
        response = client.post(
            "/groups/",
            json={"name": "Família Silva"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 201
    assert response.json()["name"] == "Família Silva"


def test_send_invite(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.single.return_value.execute.return_value.data = {
        "group_id": "group-uuid-456"
    }
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{
        "id": "invite-uuid",
        "group_id": "group-uuid-456",
        "email": "familiar@example.com",
        "token": "abc-token-123",
    }]

    with patch("app.routers.groups.get_supabase", return_value=mock_db):
        response = client.post(
            "/groups/invite",
            json={"email": "familiar@example.com"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 201
    assert response.json()["email"] == "familiar@example.com"
```

- [ ] **Step 2: Rodar testes — devem falhar**

```bash
pytest tests/test_groups.py -v
```

- [ ] **Step 3: Implementar `backend/app/routers/groups.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from ..auth import get_current_user
from ..database import get_supabase
from ..models.group import InviteCreate
from ..routers.transactions import _get_user_group

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupCreate(BaseModel):
    name: str


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_group(
    data: GroupCreate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    result = db.table("groups").insert({"name": data.name, "owner_id": user["id"]}).execute()
    group = result.data[0]
    db.table("group_members").insert({"group_id": group["id"], "user_id": user["id"], "role": "owner"}).execute()
    return group


@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_member(
    data: InviteCreate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    group_id = _get_user_group(db, user["id"])
    result = db.table("invites").insert({
        "group_id": group_id,
        "invited_by": user["id"],
        "email": data.email,
    }).execute()
    return result.data[0]


@router.post("/accept")
async def accept_invite(
    token: str = Query(...),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_supabase),
):
    invite = db.table("invites").select("*").eq("token", token).is_("accepted_at", "null").single().execute()
    if not invite.data:
        raise HTTPException(status_code=404, detail="Convite inválido ou já utilizado")

    db.table("group_members").insert({
        "group_id": invite.data["group_id"],
        "user_id": user["id"],
        "role": "member",
    }).execute()
    db.table("invites").update({"accepted_at": "NOW()"}).eq("id", invite.data["id"]).execute()
    return {"message": "Convite aceito com sucesso"}
```

- [ ] **Step 4: Rodar todos os testes**

```bash
pytest tests/ -v
```

Esperado: todos PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/groups.py backend/tests/test_groups.py
git commit -m "feat: implement group creation and family invite endpoints"
```

---

## Verificação Final do Plano 1

Após todas as tasks:

```bash
cd backend
pytest tests/ -v --tb=short
uvicorn app.main:app --reload
```

Testar manualmente:
- `GET http://localhost:8000/health` → `{"status": "ok"}`
- `GET http://localhost:8000/docs` → Swagger UI com todos os endpoints documentados
- Criar token de teste no Supabase Dashboard → testar endpoints protegidos

---

*Documento sujeito à revisão do responsável pelo projeto.*
