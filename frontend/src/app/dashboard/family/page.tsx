import { createSupabaseServerClient } from "@/lib/supabase-server";
import { getGroupMembers } from "@/lib/api";
import { InviteForm } from "@/components/invite-form";
import { CreateGroupForm } from "@/components/create-group-form";
import { TelegramLinkCodeCard } from "@/components/telegram-link-code";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default async function FamilyPage() {
  const supabase = await createSupabaseServerClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token ?? "";

  const members = token ? await getGroupMembers(token).catch(() => [] as import("@/lib/api").GroupMember[]) : [];
  const hasGroup = members.length > 0;

  if (!hasGroup) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-gray-900">Grupo Familiar</h1>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Criar Grupo</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500 mb-4">
              Você ainda não tem um grupo financeiro. Crie um para começar a
              registrar transações, definir limites e convidar familiares.
            </p>
            <CreateGroupForm token={token} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Vincular Telegram</CardTitle>
          </CardHeader>
          <CardContent>
            <TelegramLinkCodeCard token={token} />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900">Grupo Familiar</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {members.length} {members.length === 1 ? "membro" : "membros"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {members.map((m) => (
            <div
              key={m.user_id}
              className="flex items-center justify-between py-1"
            >
              <span className="text-sm text-gray-600 font-mono">
                {m.user_id.slice(0, 8)}...
              </span>
              <Badge variant={m.role === "owner" ? "default" : "secondary"}>
                {m.role === "owner" ? "Proprietario" : "Membro"}
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Convidar Familiar</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500 mb-4">
            Envie um convite por email para adicionar um familiar ao seu grupo
            financeiro. O convidado recebera acesso ao painel compartilhado apos
            aceitar o convite.
          </p>
          <InviteForm token={token} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Vincular Telegram</CardTitle>
        </CardHeader>
        <CardContent>
          <TelegramLinkCodeCard token={token} />
        </CardContent>
      </Card>
    </div>
  );
}
