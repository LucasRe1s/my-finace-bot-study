-- Grants necessários para o bot (role anon) acessar as tabelas diretamente
GRANT SELECT, INSERT ON public.users TO anon;
GRANT SELECT, INSERT, UPDATE ON public.conversations TO anon;

-- Role authenticated também precisa para operações via JWT do bot
GRANT SELECT, INSERT, UPDATE, DELETE ON public.users TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.conversations TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.groups TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.group_members TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.transactions TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.category_limits TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.invites TO authenticated;
