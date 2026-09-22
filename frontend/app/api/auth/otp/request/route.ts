import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body) {
    return NextResponse.json({ detail: "Invalid request body." }, { status: 400 });
  }

  const backendResponse = await backendFetch("/api/auth/otp/request/", {
    method: "POST",
    body: JSON.stringify(body),
  });
  const data = await backendResponse.json().catch(() => ({}));
  return NextResponse.json(data, { status: backendResponse.status });
}
