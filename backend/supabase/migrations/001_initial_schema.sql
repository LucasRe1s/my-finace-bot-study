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

-- Groups: owner can do everything; members can read
CREATE POLICY "groups_owner_all" ON public.groups
  FOR ALL USING (auth.uid() = owner_id);

CREATE POLICY "groups_members_select" ON public.groups
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.group_members gm
      WHERE gm.group_id = groups.id AND gm.user_id = auth.uid()
    )
  );

-- Group members: members can insert themselves (when accepting invite)
CREATE POLICY "group_members_insert_self" ON public.group_members
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Group members: owner can manage all members of their group
CREATE POLICY "group_members_owner_all" ON public.group_members
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM public.groups g
      WHERE g.id = group_members.group_id AND g.owner_id = auth.uid()
    )
  );

-- Invites: group members can read invites for their group
CREATE POLICY "invites_group_members_select" ON public.invites
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.group_members gm
      WHERE gm.group_id = invites.group_id AND gm.user_id = auth.uid()
    )
  );

-- Invites: group owner can insert invites
CREATE POLICY "invites_owner_insert" ON public.invites
  FOR INSERT WITH CHECK (auth.uid() = invited_by);

-- Invites: invited user can update (mark as accepted) using token
CREATE POLICY "invites_accept_update" ON public.invites
  FOR UPDATE USING (true)
  WITH CHECK (accepted_at IS NOT NULL);
