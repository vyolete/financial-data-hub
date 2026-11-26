import type { Operations } from "./schema";

export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`HTTP ${status}`);
  }
}

export async function get<K extends keyof Operations>(
  path: Operations[K]["path"],
  parameters: Operations[K]["params"],
  signal: AbortSignal,
): Promise<Operations[K]["result"]> {
  let resource: string = path;
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(parameters)) {
    if (value === undefined || value === "") continue;
    if (resource.includes(`{${key}}`)) {
      resource = resource.replace(`{${key}}`, encodeURIComponent(String(value)));
    } else {
      query.set(key, String(value));
    }
  }
  const suffix = query.size ? `?${query}` : "";
  const response = await fetch(resource + suffix, { signal });
  if (!response.ok) throw new ApiError(response.status);
  return response.json();
}
