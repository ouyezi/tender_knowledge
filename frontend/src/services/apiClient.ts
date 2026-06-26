const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const OPERATOR_ID = "admin";

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  trace_id: string;
}

interface SuccessEnvelope<T> {
  data: T;
  trace_id: string;
}

export class ApiError extends Error {
  code: string;
  details?: Record<string, unknown>;

  constructor(message: string, code: string, details?: Record<string, unknown>) {
    super(message);
    this.code = code;
    this.details = details;
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, headers, ...restOptions } = options;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...restOptions,
    headers: {
      "Content-Type": "application/json",
      "X-Operator-Id": OPERATOR_ID,
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const json = (await response.json()) as SuccessEnvelope<T> | ErrorEnvelope | T;

  if (!response.ok) {
    const err = json as ErrorEnvelope;
    if (err?.error) {
      throw new ApiError(err.error.message, err.error.code, err.error.details);
    }
    const detail = (json as { detail?: unknown }).detail;
    if (Array.isArray(detail)) {
      const message = detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            const loc = "loc" in item && Array.isArray(item.loc) ? item.loc.join(".") : "";
            return loc ? `${loc}: ${String(item.msg)}` : String(item.msg);
          }
          return String(item);
        })
        .join("; ");
      throw new Error(message || `Request failed: ${response.status}`);
    }
    throw new Error(`Request failed: ${response.status}`);
  }

  if (json && typeof json === "object" && "data" in json) {
    return (json as SuccessEnvelope<T>).data;
  }

  return json as T;
}
