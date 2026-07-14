type FetchOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
};

export type ApiError = {
  code: string;
  message: string;
};

export class ApiResponseError extends Error {
  status: number;
  error: ApiError;

  constructor(status: number, error: ApiError) {
    super(error.message);
    this.status = status;
    this.error = error;
  }
}

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem("wispgen_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiFetch<T = unknown>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { method = "GET", body, headers = {} } = options;

  const url = `/api/v1${path}`;

  const response = await fetch(url, {
    method,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const data = (await response.json().catch(() => ({}))) as {
    error?: ApiError;
  };

  if (!response.ok) {
    const error = data.error || { code: "unknown", message: "Request failed" };
    throw new ApiResponseError(response.status, error);
  }

  return data as T;
}
