export const API_BASE = "http://localhost:8000";

export async function api<T>(
  path: string,
  body?: unknown,
  method?: string,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(API_BASE + path, {
      method: method ?? (body === undefined ? "GET" : "POST"),
      signal,
      headers:
        body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new Error(
      "Backend not running or unreachable. Start scripts/run_backend.ps1 and retry.",
    );
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). Check the inputs and retry.`,
    );
  }
  return response.json();
}

export async function reportText(
  id: string,
  rulesOnly = false,
): Promise<string> {
  const response = await fetch(
    `${API_BASE}/api/alerts/${id}/report.md?rules_only=${rulesOnly}`,
  );
  if (!response.ok)
    throw new Error("Report export failed. Check the backend and retry.");
  return response.text();
}
