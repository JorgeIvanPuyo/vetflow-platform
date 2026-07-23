# Guía de agentes de Vetflow

Vetflow es un monorepo con FastAPI en `apps/api` y Next.js en `apps/web`.

## Fuentes de verdad

- No leas `docs/` por defecto. Es documentación para personas y puede contener propuestas, planes o información histórica.
- Usa el código, las pruebas, las migraciones y los manifests con sus lockfiles como fuentes técnicas de verdad.
- Para backend, inspecciona el módulo afectado en `apps/api/app`, sus migraciones y sus pruebas.
- Para frontend, inspecciona la ruta o feature afectada en `apps/web`, sus servicios, tipos y pruebas.
- Consulta un documento humano sólo si el usuario lo menciona, la tarea modifica ese documento o una decisión de producto no puede deducirse del código. Valida sus afirmaciones técnicas contra el repositorio.

## Reglas siempre aplicables

- Trabaja en una rama; no modifiques `main` directamente.
- Antes de editar, revisa `git status --short` y preserva cambios ajenos.
- No hagas `push`, `commit`, merge ni despliegues sin una solicitud explícita.
- Usa `uv` con `apps/api/pyproject.toml` y `apps/api/uv.lock`; usa `pnpm` con `apps/web/package.json` y `apps/web/pnpm-lock.yaml`.
- Toda entidad y consulta tenant-owned debe filtrar por `tenant_id`. Los accesos cross-tenant requieren protección explícita.
- Revisa las migraciones existentes antes de cambiar persistencia y acompaña todo cambio de modelo con una migración revisada.
- Conserva la compatibilidad de los contratos API o actualiza de forma coordinada backend, frontend y pruebas.
- No subas secretos, archivos `.env` ni credenciales de Firebase. No uses producción para validación local.
- Añade o ajusta pruebas cuando cambie el comportamiento.
- Ejecuta la validación más focalizada posible y amplíala cuando cambies contratos, persistencia, auth, aislamiento de tenants o CI/CD.
- Detén procesos y contenedores que hayas iniciado.

## Comandos habituales

- Backend: `cd apps/api && uv run pytest`
- Frontend: `cd apps/web && pnpm exec tsc --noEmit && pnpm run lint && pnpm run build`
- Ejecuta `uv sync --frozen` o `pnpm install --frozen-lockfile` sólo si faltan dependencias o cambiaron los manifests o lockfiles.
