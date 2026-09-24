import { ApiClientError, isConfirmedAuthenticationError } from "@/lib/api";

export type SessionStatus = "validating-session" | "waiting-for-server" | "authenticated" |
  "authentication-failed" | "authorization-failed" | "connection-failed";
export const SESSION_TIMEOUT_MS = 40_000;
export const SESSION_RETRY_MS = 5_000;
export const SESSION_MAX_FAILURES = 8;

function firebaseAuthInvalid(error: unknown) {
  const code = (error as { code?: string } | null)?.code;
  return ["auth/user-token-expired", "auth/invalid-user-token", "auth/user-disabled"].includes(code ?? "");
}

function transient(error: unknown) {
  if (error instanceof ApiClientError) {
    return error.status === 0 || [408, 425, 429].includes(error.status) || error.status >= 500;
  }
  return error instanceof TypeError || (error as { code?: string })?.code === "auth/network-request-failed";
}

// Includes token acquisition and response parsing in the global deadline.
function abortable<T>(task: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const abort = () => reject(signal.reason);
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) abort();
    task.then(resolve, reject).finally(() => signal.removeEventListener("abort", abort));
  });
}

function wait(signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(signal.reason); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, SESSION_RETRY_MS);
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) abort();
  });
}

export async function validateSession<T>({ request, refreshToken, signal, onStatus }: {
  request: (signal: AbortSignal) => Promise<T>;
  refreshToken: () => Promise<unknown>;
  signal: AbortSignal;
  onStatus: (status: SessionStatus) => void;
}): Promise<{ status: SessionStatus; data?: T } | null> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal.addEventListener("abort", cancel, { once: true });
  if (signal.aborted) cancel();
  const deadline = setTimeout(() => controller.abort(), SESSION_TIMEOUT_MS);
  const connecting = setTimeout(() => {
    if (!controller.signal.aborted) onStatus("waiting-for-server");
  }, SESSION_RETRY_MS);
  let refreshed = false;
  let failures = 0;
  try {
    if (controller.signal.aborted) return null;
    onStatus("validating-session");
    while (!controller.signal.aborted) {
      try {
        const data = await abortable(request(controller.signal), controller.signal);
        return { status: "authenticated", data };
      } catch (error) {
        if (controller.signal.aborted) break;
        failures += 1;
        if (isConfirmedAuthenticationError(error)) {
          if (refreshed) return { status: "authentication-failed" };
          if (failures >= SESSION_MAX_FAILURES) break;
          refreshed = true;
          try {
            await abortable(refreshToken(), controller.signal);
          } catch (refreshError) {
            if (controller.signal.aborted) break;
            if (firebaseAuthInvalid(refreshError)) return { status: "authentication-failed" };
            if (!transient(refreshError)) return { status: "connection-failed" };
            onStatus("waiting-for-server");
            await wait(controller.signal);
          }
          continue;
        }
        if (firebaseAuthInvalid(error)) return { status: "authentication-failed" };
        if (error instanceof ApiClientError && error.status === 403) return { status: "authorization-failed" };
        if (!transient(error)) return { status: "connection-failed" };
        if (failures >= SESSION_MAX_FAILURES) break;
        onStatus("waiting-for-server");
        await wait(controller.signal);
      }
    }
    return signal.aborted ? null : { status: "connection-failed" };
  } catch {
    return signal.aborted ? null : { status: "connection-failed" };
  } finally {
    clearTimeout(deadline); clearTimeout(connecting);
    signal.removeEventListener("abort", cancel);
    controller.abort();
  }
}
