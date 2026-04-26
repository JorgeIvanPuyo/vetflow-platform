type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE";

type RequestOptions = {
  body?: unknown;
};

type AuthTokenProvider = () => Promise<string | null>;

class ApiClientError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code = "request_failed") {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
  }
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

let authTokenProvider: AuthTokenProvider | null = null;

function setAuthTokenProvider(provider: AuthTokenProvider | null) {
  authTokenProvider = provider;
}

async function request<T>(
  path: string,
  method: HttpMethod,
  options: RequestOptions = {},
): Promise<T> {
  const token = authTokenProvider ? await authTokenProvider() : null;

  if (!token) {
    throw new ApiClientError(
      "No hay una sesión activa para llamar a la API",
      401,
      "missing_auth_token",
    );
  }

  const headers = new Headers({
    Accept: "application/json",
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  });

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    cache: "no-store",
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    const fallbackMessage = `Request failed with status ${response.status}`;

    try {
      const errorBody = (await response.json()) as {
        error?: { code?: string; message?: string };
      };

      throw new ApiClientError(
        errorBody.error?.message ?? fallbackMessage,
        response.status,
        errorBody.error?.code ?? "request_failed",
      );
    } catch (error) {
      if (error instanceof ApiClientError) {
        throw error;
      }

      throw new ApiClientError(fallbackMessage, response.status);
    }
  }

  return (await response.json()) as T;
}

export const api = {
  get<T>(path: string): Promise<T> {
    return request<T>(path, "GET");
  },
  post<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, "POST", { body });
  },
  patch<T>(path: string, body: unknown): Promise<T> {
    return request<T>(path, "PATCH", { body });
  },
  delete<T>(path: string): Promise<T> {
    return request<T>(path, "DELETE");
  },
};

export { ApiClientError, setAuthTokenProvider };
