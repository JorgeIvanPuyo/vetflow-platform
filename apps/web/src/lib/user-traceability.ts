type TraceableRecord = Record<string, unknown>;

const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

const nameFields = ["full_name", "display_name", "name"] as const;

export function getTraceableUserName(
  record: unknown,
  relation: "attending" | "created_by" | "requested_by",
) {
  if (!isRecord(record)) {
    return null;
  }

  const directName = firstReadableName([
    record[`${relation}_user_full_name`],
    record[`${relation}_full_name`],
    record[`${relation}_user_name`],
    record[`${relation}_name`],
    record[`${relation}_user_email`],
    record[`${relation}_email`],
  ]);

  if (directName) {
    return directName;
  }

  const nestedUser = record[`${relation}_user`];
  if (!isRecord(nestedUser)) {
    return null;
  }

  return getUserTraceLabel(nestedUser);
}

export function getUserTraceLabel(trace: unknown) {
  if (!isRecord(trace)) {
    return null;
  }

  return firstReadableName([
    ...nameFields.map((field) => trace[field]),
    trace.email,
  ]);
}

function firstReadableName(values: unknown[]) {
  for (const value of values) {
    if (typeof value !== "string") {
      continue;
    }

    const trimmedValue = value.trim();
    if (trimmedValue && !uuidPattern.test(trimmedValue)) {
      return trimmedValue;
    }
  }

  return null;
}

function isRecord(value: unknown): value is TraceableRecord {
  return typeof value === "object" && value !== null;
}
