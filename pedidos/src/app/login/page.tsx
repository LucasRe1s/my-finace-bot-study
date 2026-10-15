"use client";

import { useActionState } from "react";
import { signIn } from "./actions";

export default function LoginPage() {
  const [error, action, pending] = useActionState(signIn, null);

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <form action={action} className="card w-full max-w-sm space-y-4">
        <h1 className="text-center text-lg font-semibold">Pedidos</h1>
        <label className="block space-y-1 text-sm">
          <span>Email</span>
          <input className="input" name="email" type="email" autoComplete="email" required />
        </label>
        <label className="block space-y-1 text-sm">
          <span>Senha</span>
          <input className="input" name="password" type="password" autoComplete="current-password" required />
        </label>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button className="btn-primary w-full" disabled={pending}>
          {pending ? "Entrando..." : "Entrar"}
        </button>
      </form>
    </main>
  );
}
