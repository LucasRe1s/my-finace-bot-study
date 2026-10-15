import { createServerClient } from "@supabase/ssr";
import { NextRequest, NextResponse } from "next/server";

// Proteção de navegação. Cada página/action ainda chama requireUser().
export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();
  const isLogin = request.nextUrl.pathname === "/login";

  if (!user && !isLogin) {
    return NextResponse.redirect(new URL("/login", request.nextUrl));
  }
  if (user && isLogin) {
    return NextResponse.redirect(new URL("/pedidos", request.nextUrl));
  }
  return response;
}

export const config = {
  // Webhook do Telegram fica de fora: autentica pelo secret token.
  matcher: ["/((?!api/telegram|_next/static|_next/image|favicon.ico).*)"],
};
