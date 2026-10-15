import { describe, expect, it } from "vitest";
import { isFinal, nextStatus } from "@/lib/status";

describe("nextStatus", () => {
  it.each([
    ["erro_envio", "reenviar", "web", "enviado"],
    ["enviado", "aceitar", "granja", "aceito"],
    ["enviado", "recusar", "granja", "recusado"],
    ["aceito", "sair_entrega", "granja", "em_entrega"],
    ["em_entrega", "entregar", "web", "entregue"],
    ["enviado", "cancelar", "web", "cancelado"],
    ["aceito", "cancelar", "web", "cancelado"],
    ["em_entrega", "cancelar", "web", "cancelado"],
    ["erro_envio", "cancelar", "web", "cancelado"],
  ] as const)("%s + %s (%s) -> %s", (from, action, actor, to) => {
    expect(nextStatus(from, action, actor)).toEqual({ ok: true, to });
  });

  it("rejeita ator errado", () => {
    expect(nextStatus("enviado", "aceitar", "web").ok).toBe(false);
    expect(nextStatus("em_entrega", "entregar", "granja").ok).toBe(false);
  });

  it("explica quando o pedido já está em status final", () => {
    expect(nextStatus("cancelado", "aceitar", "granja")).toEqual({
      ok: false,
      reason: "Pedido já cancelado",
    });
    expect(nextStatus("entregue", "cancelar", "web").ok).toBe(false);
  });

  it("explica clique repetido", () => {
    expect(nextStatus("aceito", "aceitar", "granja")).toEqual({
      ok: false,
      reason: "Pedido já aceito",
    });
  });

  it("rejeita pular etapas", () => {
    expect(nextStatus("enviado", "sair_entrega", "granja").ok).toBe(false);
  });
});

describe("isFinal", () => {
  it("identifica status finais", () => {
    expect(isFinal("entregue")).toBe(true);
    expect(isFinal("recusado")).toBe(true);
    expect(isFinal("cancelado")).toBe(true);
    expect(isFinal("aceito")).toBe(false);
  });
});
