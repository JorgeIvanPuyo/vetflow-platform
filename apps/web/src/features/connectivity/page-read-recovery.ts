import { ApiClientError, isTransientApiError } from "@/lib/api";

export type ReadRecoveryState = {
  phase: "idle" | "waiting" | "retrying" | "failed";
  seconds: number;
};
const IDLE: ReadRecoveryState = { phase: "idle", seconds: 0 };
const RETRY_MS = 5_000;
const DEADLINE_MS = 40_000;
const MAX_ATTEMPTS = 8;
type Job = {
  read: (signal: AbortSignal) => Promise<unknown>;
  promise: Promise<unknown>;
  resolve: (value: unknown) => void;
  reject: (error: unknown) => void;
  controller: AbortController | null;
  running: boolean;
  attempts: number;
};

/** One recovery cycle/timer per mounted route; only failed GETs are replayed. */
export class PageReadRecovery {
  private jobs = new Map<string, Job>();
  private listeners = new Set<(state: ReadRecoveryState) => void>();
  private state: ReadRecoveryState = IDLE;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private startedAt = 0;
  private retryAt: number | null = null;
  private batch = 0;
  private retrying = false;
  private disposed = false;

  subscribe(listener: (state: ReadRecoveryState) => void) {
    this.listeners.add(listener);
    listener(this.state);
    return () => { this.listeners.delete(listener); };
  }

  run = <T>(key: string, read: (signal: AbortSignal) => Promise<T>): Promise<T> => {
    if (this.disposed) return Promise.reject(new DOMException("Navigation cancelled", "AbortError"));
    const existing = this.jobs.get(key);
    if (existing) return existing.promise as Promise<T>;
    if (!this.jobs.size) this.startedAt = Date.now();
    let resolve!: Job["resolve"], reject!: Job["reject"];
    const promise = new Promise<unknown>((yes, no) => { resolve = yes; reject = no; });
    const job: Job = { read, promise, resolve, reject, controller: null, running: false, attempts: 0 };
    this.jobs.set(key, job);
    if (this.state.phase !== "failed") {
      void this.attempt(key, job);
      this.scheduleTick();
    }
    return promise as Promise<T>;
  };

  private publish(state: ReadRecoveryState) {
    this.state = state;
    this.listeners.forEach(listener => listener(state));
  }

  private async attempt(key: string, job: Job) {
    if (this.disposed || job.running || this.state.phase === "failed") return;
    job.running = true;
    job.attempts += 1;
    const controller = new AbortController();
    job.controller = controller;
    let abort!: () => void;
    try {
      const cancelled = new Promise<never>((_, reject) => {
        abort = () => reject(controller.signal.reason);
        controller.signal.addEventListener("abort", abort, { once: true });
      });
      const result = await Promise.race([job.read(controller.signal), cancelled]);
      if (controller.signal.aborted || this.disposed) return;
      this.jobs.delete(key);
      job.resolve(result);
    } catch (error) {
      if (controller.signal.aborted || this.disposed) return;
      if (!isTransientApiError(error)) {
        this.jobs.delete(key);
        job.reject(error);
      } else if (job.attempts >= MAX_ATTEMPTS) {
        this.exhaust();
      } else if (!this.retrying && this.retryAt === null) {
        this.retryAt = Date.now() + RETRY_MS;
        this.publish({ phase: "waiting", seconds: 5 });
      }
    } finally {
      controller.signal.removeEventListener("abort", abort);
      if (job.controller === controller) job.running = false;
      if (!this.jobs.size && !this.disposed) this.reset();
    }
  }

  private scheduleTick() {
    if (this.timer !== undefined || !this.jobs.size || this.disposed || this.state.phase === "failed") return;
    this.timer = setTimeout(() => {
      this.timer = undefined;
      if (Date.now() - this.startedAt >= DEADLINE_MS) { this.exhaust(); return; }
      if (this.retryAt !== null) {
        const seconds = Math.max(0, Math.ceil((this.retryAt - Date.now()) / 1000));
        if (seconds === 0) void this.retryNow();
        else this.publish({ phase: "waiting", seconds });
      }
      this.scheduleTick();
    }, Math.min(1000, Math.max(0, DEADLINE_MS - (Date.now() - this.startedAt))));
  }

  retryNow = async () => {
    if (this.disposed || this.retrying || !this.jobs.size) return;
    if (this.state.phase === "failed") {
      this.startedAt = Date.now();
      this.jobs.forEach(job => { job.attempts = 0; });
    } else if (Date.now() - this.startedAt >= DEADLINE_MS) {
      this.exhaust(); return;
    }
    const batch = ++this.batch;
    this.retrying = true;
    this.retryAt = null;
    this.publish({ phase: "retrying", seconds: 0 });
    this.scheduleTick();
    try {
      // Initial page reads may run concurrently; recovery attempts are sequential.
      for (const [key, job] of [...this.jobs]) {
        if (batch !== this.batch || this.disposed || this.state.phase === "failed") break;
        if (!job.running) await this.attempt(key, job);
      }
    } finally {
      if (batch === this.batch) {
        this.retrying = false;
        if (this.jobs.size && !this.disposed && this.state.phase !== "failed") {
          this.retryAt = Date.now() + RETRY_MS;
          this.publish({ phase: "waiting", seconds: 5 });
          this.scheduleTick();
        }
      }
    }
  };

  private exhaust() {
    this.batch += 1;
    this.retrying = false;
    this.retryAt = null;
    clearTimeout(this.timer); this.timer = undefined;
    this.publish({ phase: "failed", seconds: 0 });
    this.jobs.forEach(job => { job.controller?.abort(); job.running = false; });
    // Pending readers stay mounted; manual retry can still complete their original load.
  }

  private reset() {
    clearTimeout(this.timer); this.timer = undefined;
    this.retryAt = null;
    this.publish(IDLE);
  }

  dispose() {
    this.disposed = true;
    this.batch += 1;
    clearTimeout(this.timer); this.timer = undefined;
    this.jobs.forEach(job => {
      job.controller?.abort();
      job.reject(new ApiClientError("Carga cancelada al cambiar de sección.", 0, "read_cancelled"));
    });
    this.jobs.clear();
    this.listeners.clear();
  }
}
