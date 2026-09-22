// frontend/lib/backend.ts
// Server-only helper — never imported from a "use client" file. Route
// handlers under app/api/auth/* use this to reach Django directly
// (container-to-container in Docker, localhost in dev); the browser
// never talks to Django directly, only to these Next.js routes, which
// hold the JWTs in httpOnly cookies the browser can't read.

const BACKEND_API_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

export async function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${BACKEND_API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
}
