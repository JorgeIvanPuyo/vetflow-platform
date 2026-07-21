# Vetflow Web

Responsive web frontend for Vetflow Platform.

## Dependency Source

Frontend dependencies are managed only with `pnpm`:

- `package.json`
- `pnpm-lock.yaml`
- `pnpm-workspace.yaml`

## Local Run

Create `.env.local` from `.env.example`.

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm run dev
```

## Validation

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm exec tsc --noEmit
pnpm run lint
pnpm run build
```

## Vercel

Use `apps/web` as the project root and `pnpm` as the package manager.
