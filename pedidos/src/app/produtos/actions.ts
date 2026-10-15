"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireUser } from "@/lib/auth";
import { getDeps } from "@/lib/deps";

export async function saveProductAction(formData: FormData) {
  await requireUser();
  const name = String(formData.get("name") ?? "").trim();
  const units = Number(formData.get("units_per_box"));
  if (!name || !Number.isInteger(units) || units <= 0) {
    redirect("/produtos?erro=" + encodeURIComponent("Informe nome e unidades por caixa (número inteiro maior que zero)"));
  }

  const id = String(formData.get("id") ?? "") || undefined;
  await getDeps().repo.saveProduct({
    id,
    name,
    description: String(formData.get("description") ?? "").trim(),
    units_per_box: units,
  });
  revalidatePath("/produtos");
  redirect("/produtos?msg=" + encodeURIComponent(id ? "Produto atualizado" : "Produto cadastrado"));
}

export async function toggleProductAction(formData: FormData) {
  await requireUser();
  await getDeps().repo.setProductActive(
    String(formData.get("id")),
    formData.get("active") === "true",
  );
  revalidatePath("/produtos");
  redirect("/produtos");
}
