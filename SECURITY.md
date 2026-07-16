# Segurança — my-finance-bot

Levantamento das vulnerabilidades e pontos fracos conhecidos deste projeto. É um app pessoal/familiar, não um produto multi-tenant com terceiros desconhecidos — mesmo assim, vale registrar o que está frágil, principalmente antes de um eventual deploy público.

## Crítico

### 1. Chave anon do Supabase dá acesso amplo a dados de todo mundo, direto pelo navegador

A `NEXT_PUBLIC_SUPABASE_ANON_KEY` é, por convenção do Supabase, uma chave pública — ela **fica visível no bundle JS do frontend**, qualquer pessoa consegue extraí-la do navegador. Ela normalmente é segura porque o RLS (Row Level Security) restringe o que o role `anon` enxerga.

O problema: pra permitir que o bot (que não tem sessão de usuário Supabase) funcione, várias tabelas ganharam policies `FOR ALL`/`FOR SELECT` **`TO anon USING (true)`** — ou seja, sem filtro nenhum. Isso significa que qualquer pessoa com a anon key (extraída do próprio site) pode chamar a API REST do Supabase **diretamente, sem passar pelo backend**, e:

| Tabela | Policy | O que um atacante consegue |
|---|---|---|
| `conversations` | `conversations_bot_all` (002) | Ler/editar/apagar o histórico de conversa com o agente de **qualquer** usuário |
| `users` | `users_bot_read`/`insert`/`update`/`delete` (002/008/009) | Ler, criar, editar ou **apagar** o perfil de qualquer usuário |
| `group_members` | `group_members_bot_all` (007) | Mover qualquer pessoa de grupo, ou remover membros |
| `transactions` | `transactions_bot_all` (007) | Ler ou reescrever transações financeiras de qualquer grupo |
| `invites` | `invites_bot_select` (010) | Listar **todos os convites já criados, com o token** — permite aceitar convite de outra pessoa |
| `groups` | `groups_bot_select` (010) | Ler nome/id de todos os grupos |
| `telegram_link_codes` | `telegram_link_codes_bot_all` (006) | Ler/consumir o código de vínculo de outra pessoa antes dela — sequestra a conta Telegram dela |

**Por que isso existe:** o bot do Telegram não tem uma sessão Supabase (o usuário nunca fez login ali), então as primeiras interações (achar o usuário pelo `telegram_id`, salvar histórico, etc.) precisam rodar como algum role — e o projeto usa `anon` com policies permissivas em vez de um role de serviço.

**Correção recomendada:** usar a **service_role key** do Supabase (bypassa RLS) para as operações que o bot/backend fazem em nome do sistema (não em nome de um usuário logado), e **remover** as policies/grants permissivos para `anon`. Isso exige:
- Adicionar `SUPABASE_SERVICE_ROLE_KEY` ao `.env` do backend (nunca ao frontend).
- Um client Supabase separado (service role) usado só nos paths hoje sem token de usuário (`_get_or_create_user`, `auth_link.py`, alertas de limite).
- Migration revogando os grants/policies de `anon` criados em 002/006/007/008/009/010.

Não implementado ainda — é o item de maior prioridade de segurança do projeto.

## Alto

### 2. `invites_accept_update` aceita qualquer convite autenticado

Policy original (`001_initial_schema.sql`): `FOR UPDATE USING (true) WITH CHECK (accepted_at IS NOT NULL)`. Qualquer usuário autenticado pode marcar **qualquer** convite como aceito, não só o seu. Combinado com o item 1 (convites agora legíveis por `anon`), um atacante não-autenticado consegue listar tokens de convite e um usuário autenticado qualquer consegue aceitá-los.

### 3. `GET/POST /auth/telegram-link` não confirma que o telegram_id pertence a quem gerou o código

O fluxo confia que quem manda `/start <código>` no bot é a mesma pessoa que gerou o código no site. Não há verificação adicional (ex.: o código não é vinculado a nenhuma informação do dispositivo/sessão). Na prática, quem vê o código (ex.: print de tela, mensagem encaminhada) consegue vincular a própria conta Telegram a ele dentro da janela de 10 minutos.

## Médio

### 4. CORS liberado para qualquer origem

`app/main.py`: `allow_origins=["*"]` com `allow_credentials=True`. Qualquer site consegue chamar a API a partir do navegador de um usuário logado (mitigado parcialmente por a auth ser via header `Authorization`, não cookie — um site malicioso não tem como ler o token do usuário pra montar o header, mas ainda é uma configuração mais aberta do que o necessário). Restringir a origem do frontend em produção.

### 5. Secret JWT compartilhado entre Supabase e o bot

`SUPABASE_JWT_SECRET` é usado tanto pelo Supabase (para os poucos casos de fallback HS256) quanto pelo bot (`_generate_user_token`) para emitir tokens em nome de qualquer `user_id`. Se esse secret vazar, dá pra forjar um token válido para qualquer usuário. Risco inerente ao modelo (não há alternativa simples sem um serviço de auth próprio para o bot), mas o secret precisa ser tratado como código de altíssimo privilégio.

### 6. Senha mínima de 6 caracteres no cadastro via convite

`frontend/src/app/convite/[token]/page.tsx` pede `minLength={6}`. Fraco para uma senha de acesso a dados financeiros. Considerar aumentar o mínimo e/ou checar contra listas de senhas comuns (o próprio Supabase Auth tem essa opção configurável no dashboard).

## Baixo / observações

- Não há rate limiting em `/auth/telegram-link-code` — um usuário autenticado pode gerar códigos repetidamente (baixo impacto, só spam de linhas na tabela).
- `invites.email` é validado como `str` livre, não `EmailStr` (aceita qualquer texto).
- `?month=` em `/transactions` e `/summary` não valida formato — entrada malformada vira erro 500 em vez de 400.

## Já corrigido nesta sessão

- ~~`/debug/token` expunha o payload do JWT sem verificar assinatura~~ — endpoint removido depois de resolver o AUTH-01.
- ~~Backend validava só HS256, rejeitando os tokens assimétricos (ES256) do Supabase~~ — corrigido com verificação via JWKS.
