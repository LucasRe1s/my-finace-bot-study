-- Corrige "infinite recursion detected in policy for relation group_members" (42P17).
--
-- A policy "group_members_see_own_group" (001_initial_schema.sql) consulta
-- public.group_members dentro da própria policy de public.group_members.
-- O Postgres reaplica RLS na subquery, entra em loop e recusa a query.
--
-- Solução: mover a checagem para uma function SECURITY DEFINER, que roda com
-- os privilégios do dono da function e por isso não reaplica RLS na consulta
-- interna, quebrando o ciclo.

CREATE OR REPLACE FUNCTION public.is_group_member(p_group_id UUID, p_user_id UUID)
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.group_members
    WHERE group_id = p_group_id AND user_id = p_user_id
  );
$$;

DROP POLICY IF EXISTS "group_members_see_own_group" ON public.group_members;

CREATE POLICY "group_members_see_own_group" ON public.group_members
  FOR SELECT USING (
    auth.uid() = user_id OR
    public.is_group_member(group_members.group_id, auth.uid())
  );
