-- Continuação da correção da 004.
--
-- Depois de aplicar a 004, "infinite recursion detected in policy for
-- relation group_members" (42P17) continuou ocorrendo. Causa: um segundo
-- ciclo, agora entre DUAS tabelas:
--
--   1. Ler group_members aciona a policy "group_members_owner_all", que
--      consulta public.groups para saber se o usuário é dono do grupo.
--   2. Ler groups aciona a policy "groups_members_select", que consulta
--      public.group_members de novo para saber se o usuário é membro.
--   3. Volta ao passo 1 -> recursão infinita.
--
-- Solução: mover a checagem de "group_members_owner_all" para uma function
-- SECURITY DEFINER, que roda com privilégios do dono da function (bypassa
-- RLS na consulta interna a public.groups) e quebra o ciclo.

CREATE OR REPLACE FUNCTION public.is_group_owner(p_group_id UUID, p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.groups
    WHERE id = p_group_id AND owner_id = p_user_id
  );
$$;

DROP POLICY IF EXISTS "group_members_owner_all" ON public.group_members;

CREATE POLICY "group_members_owner_all" ON public.group_members
  FOR ALL USING (
    public.is_group_owner(group_members.group_id, auth.uid())
  );
