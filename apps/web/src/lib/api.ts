const PRIMARY_API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const FALLBACK_API_BASE =
  process.env.NEXT_PUBLIC_API_FALLBACK_BASE_URL ?? "http://localhost:18000";

function currentHostBases(): string[] {
  if (typeof window === "undefined") {
    return [PRIMARY_API_BASE, FALLBACK_API_BASE].filter(
      (base, index, arr) => Boolean(base) && arr.indexOf(base) === index
    );
  }
  const protocol = window.location.protocol;
  const hostname = window.location.hostname;
  const derivedPrimary = `${protocol}//${hostname}:8000`;
  const derivedFallback = `${protocol}//${hostname}:18000`;
  return [derivedPrimary, derivedFallback, PRIMARY_API_BASE, FALLBACK_API_BASE].filter(
    (base, index, arr) => Boolean(base) && arr.indexOf(base) === index
  );
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  let lastError: unknown;
  for (const base of currentHostBases()) {
    try {
      const res = await fetch(`${base}${path}`, {
        credentials: "include",
        headers: { "Content-Type": "application/json", ...options?.headers },
        ...options,
      });
      if (!res.ok) {
        throw new ApiError(
          res.status,
          `API error: ${res.status} ${res.statusText}`
        );
      }
      return res.json();
    } catch (err) {
      lastError = err;
    }
  }
  if (lastError instanceof ApiError) {
    throw lastError;
  }
  throw new ApiError(502, "API request failed on all configured endpoints");
}
