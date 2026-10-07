# Produção, família e multicanal: design

> Criado em 07/10/2026. Cobre tudo que falta para abrir o bot para outras pessoas,
> o uso pela família (privado e grupo do Telegram) e a preparação para WhatsApp.

## Contexto

Backend, bot e dashboard funcionam localmente. Quatro pontos impedem o uso por terceiros:

1. **Segurança:** policies `TO anon USING (true)` (migrations 002 a 010) expõem todas as
   tabelas a quem tiver a anon key, que é pública no bundle do frontend (SECURITY.md item 1).
   `invites_accept_update` deixa qualquer autenticado aceitar qualquer convite (item 2) e
   `group_members_insert_self` deixa qualquer autenticado se inserir em qualquer grupo.
2. **Deploy:** o bot roda em processo separado com `run_polling`, que exige um worker sempre
   ligado. O `runner.py` fixa `api_base_url` em `http://localhost:8000`, o que quebra as tools
   quando bot e API estão em hosts diferentes.
3. **Família:** quem só usa o Telegram não consegue entrar no grupo financeiro; o convite
   exige cadastro na web.
4. **Acoplamento ao Telegram:** `users.telegram_id` e `tgbot/handlers.py` misturam transporte
   com lógica, o que impede adicionar WhatsApp sem reescrever.

## Fases

Cada fase gera software funcional e tem seu próprio plano de implementação em `specs/`.

| Fase | Entrega | Plano |
|---|---|---|
| 1 | Produção: segurança, bot dentro da API via webhook, deploy | `2026-10-07-plan-4-producao.md` |
| 2 | Núcleo agnóstico de canal + identidades por canal | `2026-10-07-plan-5-nucleo-canal.md` |
| 3 | Família no privado: convite pelo Telegram, nomes, desfazer | `2026-10-07-plan-6-familia-privado.md` |
| 4 | Bot em grupo do Telegram | `2026-10-07-plan-7-grupo-telegram.md` |
| 5 | Adaptador WhatsApp | `2026-10-07-plan-8-whatsapp.md` |
| 6 | Débitos técnicos restantes | a escrever |

---

## Fase 1: produção

### 1.1 Client Supabase de serviço (SEC-01)

- Nova variável `SUPABASE_SERVICE_ROLE_KEY`, só no backend.
- `app/database.py::get_service_supabase()` retorna um client com essa chave (bypassa RLS),
  cacheado. Falha com erro claro se a chave não estiver configurada.
- Usado **apenas** em operações do sistema sem usuário logado:
  - bot: achar/criar usuário pelo `telegram_id`, ler/gravar histórico, consumir código de vínculo;
  - `GET /groups/invite/{token}` (preview público do convite);
  - `POST /groups/accept` (marcar convite e inserir membro, depois de validar o token).
- Operações em nome do usuário continuam com `get_supabase(user_token)`, sob RLS. As tools do
  agente continuam chamando a API com o JWT do usuário.

### 1.2 Migration 011

- `DROP POLICY` de todas as policies `TO anon` criadas em 002, 006, 007, 008, 009 e 010.
- `DROP POLICY invites_accept_update` (SEC-02) e `group_members_insert_self`.
  A criação de grupo continua funcionando porque `group_members_owner_all` (005) cobre o
  insert do dono.
- `REVOKE ALL` do role `anon` nas tabelas do app.
- Um teste lê as migrations e garante que toda policy `TO anon` criada antes foi removida na 011.

### 1.3 Aceite de convite seguro

- `POST /groups/accept`: garante o perfil do usuário, recusa com 409 se ele já pertence a um
  grupo, e "reivindica" o convite com um único `UPDATE ... WHERE token = ? AND accepted_at IS NULL`
  via client de serviço. Sem linha afetada: 404. Com linha: insere o membro no `group_id` do convite.

### 1.4 Vínculo Telegram sem endpoint público

- A lógica de `POST /auth/telegram-link` vira `app/services/telegram_link.py::link_telegram_account(db, code, telegram_id)`,
  que levanta `InvalidLinkCode` quando o código não existe, expirou ou já foi usado.
- O endpoint público é **removido**: com o bot dentro da API, o handler chama a função direto.
  Isso elimina uma rota sem autenticação.

### 1.5 Bot dentro da API (webhook)

- `TELEGRAM_MODE`: `off` (padrão, testes e dev só da API), `webhook` (produção) ou `polling`
  (dev local via `python -m tgbot.runner`).
- Em `webhook`, o lifespan do FastAPI cria a `Application` do python-telegram-bot sem updater,
  inicializa, registra o webhook em `{PUBLIC_BASE_URL}/telegram/webhook` com `secret_token`,
  e inicia o processamento da fila. No shutdown, para e finaliza a aplicação.
- `POST /telegram/webhook`: valida o header `X-Telegram-Bot-Api-Secret-Token` com
  `hmac.compare_digest` (403 se inválido), desserializa o `Update`, coloca na `update_queue`
  e responde 200 na hora. O processamento do LLM acontece em background, então o Telegram não
  sofre timeout nem reenvia.
- `concurrent_updates(8)`: uma resposta lenta do LLM não trava os outros usuários.
- `PUBLIC_BASE_URL` aceita `RENDER_EXTERNAL_URL` como alternativa (o Render injeta essa variável).
- As tools do agente chamam a API **em processo** via `httpx.ASGITransport(app=api)`, sem rede
  e sem depender da URL pública. Continuam passando pelo mesmo caminho HTTP (auth, RLS, validação).
- Rodar com **um** worker do uvicorn: cada worker teria sua própria `Application`.

### 1.6 Configuração

- `CORS_ORIGINS` (lista separada por vírgula), padrão `http://localhost:3000`.
- `API_BASE_URL` usado só no modo `polling`.
- Remove `OPENAI_API_KEY` (OPENAI-01). `extra="ignore"` nas settings para um `.env` antigo não quebrar.
- `tests/conftest.py` define variáveis padrão para a suíte rodar sem `.env`.

### 1.7 Deploy

- `render.yaml` com um único web service (`rootDir: backend`), `healthCheckPath: /health`,
  `TELEGRAM_MODE=webhook` e as variáveis secretas como `sync: false`.
- Frontend na Vercel com `NEXT_PUBLIC_API_URL` apontando para o Render.
- No plano free o serviço hiberna após inatividade; a primeira mensagem acorda o serviço e
  pode demorar. O Telegram reentrega updates que falharam.
- Para desenvolvimento, usar um **bot separado** no BotFather: `run_polling` apaga o webhook do
  bot usado.

### Fora da Fase 1

Rate limit por usuário, nomes de membros, `/desfazer`: Fase 3. Débitos (`?month=`, `EmailStr`,
`getUser()`, senha mínima): Fase 6.

---

## Fase 2: núcleo agnóstico de canal

### Identidades

- Tabela `user_identities (id, user_id → users, channel TEXT CHECK IN ('telegram','whatsapp'), external_id TEXT, created_at, UNIQUE(channel, external_id))`.
- Migration copia `users.telegram_id` para `user_identities` e, em release posterior, remove a coluna.
- `telegram_link_codes` vira `link_codes` com coluna `channel`; o vínculo passa a ser
  `link_identity(db, code, channel, external_id)`.

### Núcleo de conversa

- `core/conversation.py::process_message(msg: IncomingMessage) -> list[OutgoingMessage]`,
  onde `IncomingMessage` tem `channel`, `external_user_id`, `display_name`, `chat_id`,
  `chat_type` (`private` | `group`), `text`, `mentions_bot`.
- Ele resolve a identidade, carrega histórico, roda o agente, aplica as blindagens
  (`resolve_leaked_tool_call`, `is_raw_provider_error`) e devolve as mensagens a enviar,
  incluindo alertas de limite (hoje enviados de dentro da tool com o objeto `bot` do Telegram).
- `tgbot/handlers.py` vira adaptador fino: converte `Update` em `IncomingMessage` e envia as
  `OutgoingMessage`.
- Interface `Notifier` por canal para mensagens proativas (alertas).
- Rate limit por usuário no núcleo (padrão: 30 mensagens a cada 10 minutos, em memória),
  protegendo a cota do Groq.

---

### Ajustes feitos na implementação

- `telegram_link_codes` **não** foi renomeada: o código não pertence a canal; o canal só entra no consumo (`link_identity`).
- `Notifier` adiado: os alertas de limite voltam como `OutgoingMessage` dentro da própria resposta.
- `chat_type` e `mentions_bot` ficam para a Fase 4.
- `users.telegram_id` continua até todos os usuários terem identidade; um fallback adota os antigos.

---

## Fase 3: família no privado

- Tool `gerar_convite` e comando `/convidar`: o dono recebe o link
  `https://t.me/<bot>?start=join_<token>` (reaproveita a tabela `invites`; `email` passa a ser opcional).
- `/start join_<token>`: cria o usuário se preciso e o adiciona ao grupo com a mesma lógica do
  aceite web (1.3), sem cadastro na web.
- Coluna `name` passa a ser exibida em `GET /groups/members` e na tela da família (P3-T6).
- Tool `desfazer_ultima`: apaga a última transação **do próprio usuário** criada nos últimos 10 minutos.
- Cada transação registra quem lançou (já existe `transactions.user_id`); extrato mostra o nome.

---

### Ajustes feitos na implementação

- Qualquer membro do grupo pode gerar convite (era "o dono"); restringir depois é uma checagem.
- Convites expiram em 7 dias (`invites.expires_at`).
- O link do convite é montado pelo adaptador do canal (`invite_link`), porque o formato muda entre Telegram e WhatsApp.
- `_ensure_user_profile` não sobrescreve mais o nome; o nome do canal substitui um nome vazio ou com `@`.

---

## Fase 4: bot em grupo do Telegram

- Tabela `chat_bindings (channel, chat_id, group_id, created_by, created_at, UNIQUE(channel, chat_id))`.
- `/vincular` no grupo do Telegram: só o dono do grupo financeiro consegue vincular o chat.
- Privacy mode do BotFather **ligado**: o bot só processa comandos, menções e respostas a ele.
  Mensagens comuns da família não passam pelo LLM.
- Membro do chat que não é do grupo financeiro: o bot responde que ele precisa ser aprovado e
  avisa o dono, que aprova com um botão (inline keyboard). Entrar no chat não dá acesso automático.
- Histórico e confirmação pendente chaveados por `(chat_id, user_id)`: o "sim" de uma pessoa não
  confirma o lançamento de outra.
- Alertas de limite vão para o chat vinculado.

---

### Ajustes feitos na implementação

- Um chat por grupo financeiro (`UNIQUE(group_id)`).
- A documentação do Telegram não garante entrega de menções com privacy mode ligado; por isso, além de menção e resposta, existe `/f <mensagem>`.
- Aprovação sem tabela de pedidos: o botão carrega `approve:<user_id>` e o backend confere que quem clicou é o dono.
- Histórico de grupo em `group_chat_history` (tabela nova), para não mudar a `UNIQUE(user_id)` de `conversations` no meio do deploy.
- Quando o grupo vira supergrupo, o vínculo é movido para o novo `chat_id`.

---

## Fase 5: WhatsApp

- Decisão de provedor no início da fase (Cloud API oficial da Meta ou BSP), conferindo a
  documentação vigente: suporte a grupos, custo por conversa, janela de 24h e templates.
- Adaptador `wabot/` com webhook (verificação do `hub.challenge` e assinatura `X-Hub-Signature-256`)
  que converte para `IncomingMessage` e chama o mesmo núcleo da Fase 2.
- Alertas fora da janela de 24h via template aprovado.
- Vínculo de conta pelo mesmo `link_codes` com `channel = 'whatsapp'`.
- Modo principal no WhatsApp: cada pessoa no privado (Fase 3). Grupo só se o provedor suportar.

---

### Ajustes feitos na implementação (pesquisa em 07/10/2026)

- Provedor: Cloud API oficial da Meta; Telegram mantido em paralelo.
- Sem grupos no WhatsApp: a Groups API exige Official Business Account e aceita no máximo 8 participantes.
- Sem templates: o bot só responde, então tudo fica na janela de 24h.
- Convite via `wa.me/<número>?text=join_<token>`; vínculo com `/start <código>` como no Telegram.
- Reentregas da Meta descartadas pelo `wamid`; texto acima de 4096 caracteres é dividido.

---

## Fase 6: débitos técnicos

| Origem | Correção |
|---|---|
| P1-T5 | `?month=` validado como `YYYY-MM`, 422 em vez de 500 |
| P3-T2 | `getSession()` no servidor trocado por `getUser()` |
| P3-T2 | Auth callback redireciona para `/login` quando `code` ausente |
| SEC-03 | Senha mínima de 10 caracteres + checagem de senha vazada no Supabase Auth |
| SECURITY item 2 | Código de vínculo com 10 min e uso único já mitiga; avaliar confirmação no web |

## Decisões em aberto (resolver no início de cada fase)

Nenhuma no momento.
