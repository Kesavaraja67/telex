import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get("code");
  const state = searchParams.get("state") || "";

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "https://telex-api.onrender.com";

  if (!code) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  // Forward to backend auth callback to exchange code and set session cookie
  const targetUrl = new URL(`${apiUrl}/api/auth/github/callback`);
  targetUrl.searchParams.set("code", code);
  if (state) {
    targetUrl.searchParams.set("state", state);
  }

  return NextResponse.redirect(targetUrl.toString());
}
