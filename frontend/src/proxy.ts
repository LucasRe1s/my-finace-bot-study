import { createServerClient } from "@supabase/ssr";
import { NextRequest, NextResponse } from "next/server";

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtectedRoute = pathname.startsWith("/dashboard");
  const isPublicRoute =
    pathname === "/login" || pathname === "/signup" || pathname === "/";

  if (!isProtectedRoute && !isPublicRoute) {
    return NextResponse.next();
  }

  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (isProtectedRoute && !session) {
    return NextResponse.redirect(new URL("/login", request.nextUrl));
  }

  if (isPublicRoute && session && !pathname.startsWith("/dashboard")) {
    return NextResponse.redirect(new URL("/dashboard", request.nextUrl));
  }

  return response;
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\.png$).*)",
  ],
};
