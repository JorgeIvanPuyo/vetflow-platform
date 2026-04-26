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
const AUTH_TOKEN_WAIT_ATTEMPTS = 30;
const AUTH_TOKEN_WAIT_MS = 100;
const REQUEST_RETRY_DELAYS_MS = [700, 1400];

let authTokenProvider: AuthTokenProvider | null = null;

function setAuthTokenProvider(provider: AuthTokenProvider | null) {
  authTokenProvider = provider;
}

async function request<T>(
  path: string,
  method: HttpMethod,
  options: RequestOptions = {},
): Promise<T> {
  const token = await waitForAuthToken();

  if (!token) {
    throw new ApiClientError(
      "Tu sesión está cargando. Intenta nuevamente en unos segundos.",
      0,
      "auth_token_pending",
    );
  }

  const headers = new Headers({
    Accept: "application/json",
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  });

  const requestInit: RequestInit = {
    method,
    headers,
    cache: "no-store",
    body: options.body ? JSON.stringify(options.body) : undefined,
  };

  const response = await fetchWithTransientRetry(
    `${API_BASE_URL}${path}`,
    requestInit,
  );

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

async function waitForAuthToken() {
  for (let attempt = 0; attempt < AUTH_TOKEN_WAIT_ATTEMPTS; attempt += 1) {
    const token = authTokenProvider ? await authTokenProvider() : null;

    if (token) {
      return token;
    }

    await sleep(AUTH_TOKEN_WAIT_MS);
  }

  return null;
}

async function fetchWithTransientRetry(url: string, init: RequestInit) {
  let lastError: unknown = null;

  for (let attempt = 0; attempt <= REQUEST_RETRY_DELAYS_MS.length; attempt += 1) {
    try {
      const response = await fetch(url, init);

      if (!isTransientStatus(response.status) || attempt === REQUEST_RETRY_DELAYS_MS.length) {
        return response;
      }
    } catch (error) {
      lastError = error;

      if (attempt === REQUEST_RETRY_DELAYS_MS.length) {
        break;
      }
    }

    await sleep(REQUEST_RETRY_DELAYS_MS[attempt]);
  }

  throw new ApiClientError(
    "Estamos cargando la información. Intenta nuevamente en unos segundos.",
    0,
    "network_error",
  );
}

function isTransientStatus(status: number) {
  return [408, 425, 429, 500, 502, 503, 504].includes(status);
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function getApiErrorMessage(error: unknown) {
  if (!(error instanceof ApiClientError)) {
    return "Estamos cargando la información. Intenta nuevamente en unos segundos.";
  }

  if (error.status === 401) {
    return "Tu sesión expiró. Vuelve a iniciar sesión.";
  }

  if (error.status === 403) {
    return "No tienes acceso a esta aplicación.";
  }

  if (
    error.status === 0 ||
    error.code === "network_error" ||
    error.code === "auth_token_pending" ||
    isTransientStatus(error.status)
  ) {
    return "Estamos cargando la información. Intenta nuevamente en unos segundos.";
  }

  return error.message;
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

export { ApiClientError, getApiErrorMessage, setAuthTokenProvider };
