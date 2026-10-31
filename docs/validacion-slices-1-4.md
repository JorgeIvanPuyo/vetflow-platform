# Cierre de inventario y compras — slices 1–4

## Validación posterior a 0062 — 2026-10-31

Rama `fix/tests-post-0062`. Esta sección sustituye las conclusiones y comandos históricos de publicación siguientes. Iván informó que aplicó las migraciones en producción; **no se consultó producción ni se ejecutó ninguna operación allí**. No se modificaron 0060/0061/0062 ni `docker-compose.yml` (su cambio local previo permanece fuera de este trabajo).

Causas comprobadas: se reprodujeron los 37 fallos backend informados. Los helpers de preferencias/consultas/documentos creaban precios fijos incompatibles; ahora comparten entradas calculables mediante `app/tests/catalog_pricing.py`. Las fixtures de límites conservan los máximos originales y la simulación deliberada de historia inválida. Tres aserciones confundían head actual con revisión histórica; head es 0062, mientras cada prueba de transformación/downgrade apunta a su revisión específica (0050–0055), sin atravesar el downgrade irreversible de 0060. En frontend, `changed` es estado interno: se conservan atributos/resaltado y se comprueban las etiquetas humanas Aplicada/Revertida/Conflicto.

Correcciones grupales: aumentar/disminuir aplican el ajuste a la venta vigente y eligen el resultado calculado más cercano con porcentaje de dos decimales, rango 0–1000 y redondeo vigente, evaluando como máximo seis candidatos. Se comparó el resolver de HEAD con el corregido en Docker sin base/red: costo 1000, IVA 21%, porcentaje 30%, redondeo 50 y venta 1550; los objetivos ±10% (1705/1395) antes fallaban por exactitud y ahora producen 1700/40,91% y 1400/15,29%. No producen una venta contraria a la dirección pedida. La simulación muestra objetivo, diferencia, porcentaje/venta resultantes y venta sin cambios; un cambio sólo de porcentaje sigue siendo aplicable. Establecer precio final mantiene exactitud. Datos incompletos, base cero incompatible, margen negativo/fuera de rango e importes imposibles mantienen motivos específicos; no se cambian costo/IVA ni se escribe modo fijo.

Proveedor grupal: selector paginado de registros activos del tenant, con UUID y nombre guardados juntos. Backend verifica existencia/tenant/actividad y revalida al confirmar; no acepta texto arbitrario. Quitar proveedor requiere confirmación explícita y limpia ambas referencias; reversión conserva snapshots y detecta conflictos. Operaciones antiguas pendientes con proveedor textual requieren una nueva simulación con el selector. Las restantes acciones y los controles de selección, páginas, exclusiones, conflictos y reversión conservan su cobertura.

| Validación final | Resultado | Alcance y omisiones |
| --- | --- | --- |
| Backend ordinario completo | 1826 PASS / 0 FAIL / 148 SKIP | SQLite aislado; los 148 skips requieren opt-ins PostgreSQL y se cubren por separado abajo; incluye regresiones de compras/descuento/devolución acordada, cero e idempotencia |
| Archivos con opt-ins PostgreSQL | 288 PASS / 0 FAIL / 0 SKIP | Instancia PostgreSQL 17 desechable: una base de integridad migrada a 0062 y seis bases vacías independientes para migraciones históricas; incluye también casos SQLite de esos archivos |
| PostgreSQL con fixtures heredadas | 267 PASS / 0 FAIL / 0 SKIP | Seis archivos adicionales detectados al contrastar los skips ordinarios con la selección por variables; instancia nueva desechable, sin datos de negocio |
| Frontend completo | 461 PASS / 0 FAIL / 0 SKIP, 31 archivos | Descubrimiento con `rg`, incluye pruebas no seguidas; runner Node por archivo, sin llamadas reales |
| TypeScript / lint / build | PASS / PASS / PASS | `tsc --noEmit`, `next lint` sin avisos, `next build` con 80 páginas generadas |
| Diff y preservación | PASS | SHA-256 de Compose y 0060/0061/0062 conservados |

No sumar los conteos backend como casos únicos: los archivos opt-in repiten parte de la cobertura ordinaria. Aviso backend existente: Starlette recomienda `python_multipart`. Los resultados completos están en `/tmp/vetflow-post0062-{backend-full,postgresql,postgresql-inherited,frontend-full,types,lint,build}.log`.

Comandos reproducibles desde Bash; imagen local instalada `api-api:latest`, fuentes y Alembic del checkout montados en sólo lectura. No instalar dependencias. Suite ordinaria (ningún opt-in hereda un destino externo):

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/api
set -o pipefail
docker run --rm --pull never --network none \
  -v "$PWD/app:/app/app:ro" -v "$PWD/alembic:/app/alembic:ro" \
  api-api:latest env DATABASE_URL=sqlite:// TEST_DATABASE_URL= \
  SERVICE_PRICING_MIGRATION_DATABASE_URL= SECRETARY_MIGRATION_DATABASE_URL= \
  PAYMENT_IDEMPOTENCY_MIGRATION_DATABASE_URL= PAYMENT_BATCH_MIGRATION_DATABASE_URL= \
  RECEIVABLES_MIGRATION_DATABASE_URL= SALE_PRICE_MODE_MIGRATION_DATABASE_URL= \
  ARCA_HOMOLOGATION_ENABLED=false ARCA_LOCAL_CREDENTIALS_ENABLED=false \
  sh -c 'uv run --frozen --no-sync python -c "import os; from app.core.config import get_settings; from sqlalchemy.engine import make_url; assert make_url(get_settings().database_url).drivername == \"sqlite\"; assert all(not v for k, v in os.environ.items() if k == \"TEST_DATABASE_URL\" or k.endswith(\"_MIGRATION_DATABASE_URL\"))" && uv run --frozen --no-sync pytest app/tests -q -ra --tb=short' \
  2>&1 | tee /tmp/vetflow-post0062-backend-full.log
```

PostgreSQL: estos comandos se limitan al contenedor **nuevo y desechable** indicado, sin puertos publicados ni volúmenes de negocio. No apuntar estas variables a ninguna otra base. Crear recursos con nombres libres; si ya existen, detenerse y comprobar su origen.

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/api
(
set -e
docker network create --internal --label vetflow.task=post0062-tests vetflow-post0062-tests &&
docker run -d --rm --pull never --name vetflow-post0062-postgres \
  --label vetflow.task=post0062-tests --network vetflow-post0062-tests \
  --tmpfs /var/lib/postgresql/data:rw \
  -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=vetflow_tests postgres:17
# Esperar disponibilidad antes de crear bases; pg_isready sólo consulta este contenedor.
for vetflow_attempt in {1..30}; do
  docker exec vetflow-post0062-postgres pg_isready -U postgres -d vetflow_tests && break
  sleep 1
done
docker exec vetflow-post0062-postgres pg_isready -U postgres -d vetflow_tests
for vetflow_db in migration_service migration_secretary migration_idempotency migration_batch migration_receivables migration_price_mode; do
  docker exec vetflow-post0062-postgres createdb -U postgres "$vetflow_db"
done
docker run --rm --pull never --network vetflow-post0062-tests \
  -v "$PWD/app:/app/app:ro" -v "$PWD/alembic:/app/alembic:ro" \
  api-api:latest env DATABASE_URL=postgresql://postgres@vetflow-post0062-postgres/vetflow_tests \
  ARCA_HOMOLOGATION_ENABLED=false ARCA_LOCAL_CREDENTIALS_ENABLED=false \
  uv run --frozen --no-sync alembic upgrade 0062_purchase_return_agreed
)
```

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/api
mapfile -t vetflow_pg_files < <(rg -l 'postgres_test_session_factory|TEST_DATABASE_URL|MIGRATION_DATABASE_URL' app/tests -g 'test_*.py' | sort)
set -o pipefail
docker run --rm --pull never --network vetflow-post0062-tests \
  -v "$PWD/app:/app/app:ro" -v "$PWD/alembic:/app/alembic:ro" \
  api-api:latest env DATABASE_URL=sqlite:// \
  TEST_DATABASE_URL=postgresql://postgres@vetflow-post0062-postgres/vetflow_tests \
  SERVICE_PRICING_MIGRATION_DATABASE_URL=postgresql://postgres@vetflow-post0062-postgres/migration_service \
  SECRETARY_MIGRATION_DATABASE_URL=postgresql://postgres@vetflow-post0062-postgres/migration_secretary \
  PAYMENT_IDEMPOTENCY_MIGRATION_DATABASE_URL=postgresql://postgres@vetflow-post0062-postgres/migration_idempotency \
  PAYMENT_BATCH_MIGRATION_DATABASE_URL=postgresql://postgres@vetflow-post0062-postgres/migration_batch \
  RECEIVABLES_MIGRATION_DATABASE_URL=postgresql://postgres@vetflow-post0062-postgres/migration_receivables \
  SALE_PRICE_MODE_MIGRATION_DATABASE_URL=postgresql://postgres@vetflow-post0062-postgres/migration_price_mode \
  ARCA_HOMOLOGATION_ENABLED=false ARCA_LOCAL_CREDENTIALS_ENABLED=false \
  uv run --frozen --no-sync pytest "${vetflow_pg_files[@]}" -q -ra --tb=short \
  2>&1 | tee /tmp/vetflow-post0062-postgresql.log
```

Los siguientes seis archivos heredan fixtures PostgreSQL y no contienen directamente el nombre de las variables. También se ejecutaron, en una segunda instancia efímera nueva preparada como arriba (basta la base `vetflow_tests` migrada a 0062), sin repetir los archivos aprobados:

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/api
set -o pipefail
docker run --rm --pull never --network vetflow-post0062-tests \
  -v "$PWD/app:/app/app:ro" -v "$PWD/alembic:/app/alembic:ro" \
  api-api:latest env DATABASE_URL=sqlite:// \
  TEST_DATABASE_URL=postgresql://postgres@vetflow-post0062-postgres/vetflow_tests \
  SERVICE_PRICING_MIGRATION_DATABASE_URL= SECRETARY_MIGRATION_DATABASE_URL= \
  PAYMENT_IDEMPOTENCY_MIGRATION_DATABASE_URL= PAYMENT_BATCH_MIGRATION_DATABASE_URL= \
  RECEIVABLES_MIGRATION_DATABASE_URL= SALE_PRICE_MODE_MIGRATION_DATABASE_URL= \
  ARCA_HOMOLOGATION_ENABLED=false ARCA_LOCAL_CREDENTIALS_ENABLED=false \
  uv run --frozen --no-sync pytest \
  app/tests/test_owner_account.py app/tests/test_owner_receivables.py \
  app/tests/test_receivable_signals.py app/tests/test_receivables_foundation.py \
  app/tests/test_sale_confirmation_batch.py app/tests/test_sale_confirmation_payment.py \
  -q -ra --tb=short 2>&1 | tee /tmp/vetflow-post0062-postgresql-inherited.log
```

Cerrar sólo los recursos propios anteriores al terminar, también si hubo fallos; conservar antes el código de salida del runner. No borrar volúmenes:

```bash
docker stop vetflow-post0062-postgres
docker network rm vetflow-post0062-tests
```

Frontend y comprobaciones (ejecutar cada bloque y revisar su código de salida):

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/web
vetflow_result=0
vetflow_count=0
while IFS= read -r -d '' vetflow_test; do
  vetflow_count=$((vetflow_count + 1))
  pnpm exec node "$vetflow_test" || vetflow_result=1
done < <(rg --files -0 -g '*.test.cjs' src) > /tmp/vetflow-post0062-frontend-full.log 2>&1
if [ "$vetflow_count" -eq 0 ]; then vetflow_result=1; fi
printf 'Files: %s; exit: %s\n' "$vetflow_count" "$vetflow_result"
(exit "$vetflow_result")
```

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/web
set -o pipefail
pnpm exec tsc --noEmit 2>&1 | tee /tmp/vetflow-post0062-types.log &&
pnpm run lint 2>&1 | tee /tmp/vetflow-post0062-lint.log &&
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
NEXT_PUBLIC_AI_FEATURES_ENABLED=false pnpm run build 2>&1 | tee /tmp/vetflow-post0062-build.log
```

El build usa la configuración pública de desarrollo existente en `.env.local`, sin imprimir valores ni inventar credenciales. No ejecuta flujos Firebase/ARCA/buckets ni necesita autenticación externa. No se cambiaron dependencias/lockfiles. Diff:

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform
git diff --check
```

Checklist manual pendiente de Iván, sólo con productos propios locales:

| Acción | Comprobar |
| --- | --- |
| Aumentar y disminuir % con IVA, margen no cero y redondeo | Simulación muestra objetivo/diferencia; confirmar y reabrir conserva exactamente el precio y porcentaje mostrados. Sin IVA: 1000/1300 ±10% → 1430/43% o 1170/17%. Con IVA 21%, margen 30 y redondeo 50: venta 1550, +10% objetivo 1705 → 1700; −10% objetivo 1395 → 1400. No modificar preferencias de negocio para ajustar ejemplos. |
| Establecer margen y precio final | 40% → 1400 y precio 1500 → 50% en la base anterior sin IVA/redondeo. Un precio que requiera margen negativo o no sea representable explica el rechazo por fila. |
| Establecer proveedor | Elegir activo existente (también de otra página del selector), confirmar y reabrir; nombre/relación coinciden. Quitar sólo con confirmación explícita; coste, impuestos y stock intactos. |
| Marca, stock mínimo, activar e inactivar | Cambia sólo el campo solicitado, incluso en productos pendientes. Simulación/guardado/lectura coinciden. |
| Selección y recuperación | Seleccionar entre páginas, filtrar marca/categoría y excluir una fila; comprobar conjunto y contadores. Probar conflicto tras simular, doble confirmación, reversión y guardar/cerrar modal sin repetir PATCH. |

Listo para revisión previa al despliegue, sin bloqueos automatizados pendientes. Los 148 casos saltados en SQLite se cubrieron habilitando PostgreSQL en los archivos correspondientes (288 y 267 PASS, con casos SQLite repetidos entre fases). Pendiente la aceptación manual grupal de Iván; no se declara realizada. Las dos instancias efímeras y sus redes fueron cerradas; no quedan contenedores/procesos propios y se preservó el entorno preexistente. No se hicieron commit/push/merge/PR ni despliegues. Las secciones siguientes son registro histórico y no autorizan reaplicar migraciones de negocio.

---

Fecha: 2026-10-30. Rama: `feature/arca1-fiscal-proposals`.

> Actualización posterior: se aprobó sustituir el bloqueo de devoluciones descontadas por un importe acordado con el proveedor, requerido al confirmar (cero válido). El head de código ahora es `0062_purchase_return_agreed`, **pendiente de aplicar**. Las referencias a head 0061, restricción pendiente y lista de publicación siguientes corresponden al cierre anterior y requieren actualizarse antes de publicar; no son instrucciones vigentes de publicación.

**Dictamen: listo para validación final de Iván.** El trabajo sigue sin commit ni push. No se declara aprobado para producción. Los bloques pendientes de este documento son instrucciones propuestas: no se ejecutaron suites completas, build general, migraciones ni publicación en el slice 4.

## Resultado de la revisión acotada

Se revisaron los escritores y lectores modificados, sin ampliar la auditoría a todo inventario o ARCA. El backend calcula el catálogo; las acciones grupales guardan porcentaje equivalente y contexto; la recepción compara costos unitarios originales, conserva el mayor y suma stock una sola vez. El descuento conserva bruto, impuestos y líneas; el dinero comprometido usa el neto explícito. Los cambios de catálogo no reescriben documentos históricos. Los filtros de pendientes incluyen inactivos y otras páginas; no se completaron datos por suposición.

Correcciones nuevas:

- La salida manual de inventario usaba `precio_explícito or precio_catálogo`, perdiendo un cero legítimo. Ahora distingue `None` de cero y evita usar como precio vigente una referencia legada pendiente de datos; conserva la salida de stock y el catálogo.
- Una prueba histórica aún exigía que `0055_inventory_sale_price_mode` fuera el head. Ahora comprueba su pertenencia a la cadena convergida y su padre original; las pruebas de 0060/0061 conservan la comprobación del head actual. No se modificaron migraciones.
- Se añadió una regresión conjunta: costo 1000/margen 30/stock 0 → recibir 2×1200 con descuento 10% (2400/240/2160, venta 1560) → aumento grupal 10% (margen 43, venta 1716) → costo manual 900 (1287) → recibir 950 (1358,50, stock 3). Comprueba historial de la primera compra intacto, costos originales, rechazo de recepción repetida y ausencia de modo fijo.

Las devoluciones con descuento monetario positivo se rechazan antes de mutar existencias en crear/editar/confirmar; la UI explica el motivo y no ofrece registrar la devolución. Las cancelaciones de devoluciones y la reversión de recepción conservan sus rutas y controles propios. Se añadió un caso de devolución operativa con descuento porcentual cero. Los filtros de tenant, permisos y mecanismos existentes de bloqueo/idempotencia se conservaron.

## Evidencia y límites

| Alcance | Evidencia disponible | Estado |
| --- | --- | --- |
| Slice 1 | 143 casos backend informados; tipos y tres archivos frontend pertinentes | Aprobados en el slice; no repetidos completos aquí |
| Slice 2 | 82 casos backend informados; tipos, navegación, recuperación y modal | Aprobados en el slice; seis casos de modal con componentes reales y hooks/fetch controlados, sin aceptación en navegador |
| Slice 3 | 87 casos backend informados; tipos y dos archivos frontend, incluidos 15 escenarios de descuento | Aprobados en el slice; no repetidos completos aquí |
| Slice 4 | Nueva regresión conjunta + tres variantes de salida manual + devolución con descuento cero + prueba histórica del grafo | **6 passed**, un aviso existente de Starlette (`python_multipart`); SQLite aislado en Docker sin red |
| Grafo de archivos | `ScriptDirectory`: head único `0061_purchase_global_discount`, merge ARCA/inventario correcto | Comprobado sin conexión a base ni ejecución de migraciones |
| Diff | Revisión acotada y `git diff --check` | Sin errores de espacios; cambios anteriores preservados |
| Persistencia local anterior | 0060 aplicada en slice 1: 19 convertidos, 69 pendientes entre 478 productos; 0061 aplicada una vez desde 0060 en slice 3: siete compras históricas sin descuento y agregados preservados | Evidencia histórica local; no se reaplicó ni consultó la base en slice 4. No acredita conteos productivos |
| Suite ordinaria completa backend, suite frontend y build de producción local | Comandos siguientes | Pendientes de Iván |
| PostgreSQL opt-in y pruebas que ejecutan migraciones | Excluidos de la validación ordinaria indicada abajo | No acreditados por una suite SQLite aprobada |
| Navegador autenticado | Checklist siguiente | Pendiente de Iván; no se utilizó una sesión de navegador |
| Producción | Sin conexiones ni lecturas | Revisión actual y condiciones operativas pendientes del operador |

Los conteos 143/82/87 pueden solaparse: **no se suman como pruebas únicas**. Los informes originales siguen en `/tmp/vetflow-slice1-validation.md`, `/tmp/vetflow-slice2-validation.md` y `/tmp/vetflow-slice3-validation.md`; este archivo conserva el resumen durable.

Limitaciones funcionales que requieren revisión:

- **Pendiente de aceptación explícita:** no se permite la devolución automática de una compra con descuento monetario positivo hasta acordar cómo calcular su importe. No hay prorrateo ni devolución automática por el bruto. No está aceptada por Iván todavía; si no se acepta, la publicación espera una política e implementación posteriores.
- Un precio objetivo debe poder representarse exactamente con porcentaje de 0 a 1000, dos decimales y el redondeo vigente. De lo contrario se rechaza la fila en previsualización, sin cambiar costo, IVA o preferencias para forzarlo.
- Un producto incompleto sigue pendiente; un importe legado puede conservarse sólo como referencia. Cero válido y ausencia de datos son distintos. Completar los 69 pendientes locales no forma parte de este cierre.
- No existe módulo de pagos/caja/cuentas a pagar de compras; no se añadió ni se atribuye al descuento un movimiento financiero.

## Regresión focalizada ejecutada en este slice

Registro: `/tmp/vetflow-slice4-targeted.log`. Comando reproducible; no hace falta repetirlo antes de la suite ordinaria:

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/api
set -o pipefail
docker run --rm --pull never --network none \
  -v "$PWD/app:/app/app:ro" -v "$PWD/alembic:/app/alembic:ro" \
  api-api:latest env DATABASE_URL=sqlite:// TEST_DATABASE_URL= \
  ARCA_HOMOLOGATION_ENABLED=false ARCA_LOCAL_CREDENTIALS_ENABLED=false \
  uv run --frozen --no-sync pytest \
  app/tests/test_inventory_purchase_slices_integration.py \
  app/tests/test_inventory_sale_price_mode_migration.py::test_sale_price_mode_migration_is_in_merged_chain \
  -q --tb=short 2>&1 | tee /tmp/vetflow-slice4-targeted.log
```

## Validación completa de Iván — no ejecutada aquí

Usar Bash. Ejecutar y revisar cada bloque antes de continuar; `pipefail` conserva un fallo del runner aunque `tee` termine bien. No instalar dependencias: la imagen y `node_modules` existentes se reutilizan; manifests/lockfiles no cambiaron.

### Backend ordinario, sin base de negocio ni red

La imagen local comprobada es `api-api:latest`, directorio `/app`, con uv y dependencias instaladas. Los mounts leen **el checkout actual**, incluidos archivos sin seguimiento, en lugar de la copia vieja de la imagen. No monta credenciales, `.env`, sockets Docker ni volúmenes de aplicación. `--network none` impide conexiones externas. Las fixtures ordinarias crean SQLite en memoria por caso; los opt-ins PostgreSQL no recurren a `DATABASE_URL` cuando `TEST_DATABASE_URL` está vacío.

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/api
set -o pipefail
docker image inspect api-api:latest --format '{{.Id}} {{.Config.WorkingDir}}' &&
docker run --rm --pull never --network none \
  -v "$PWD/app:/app/app:ro" \
  -v "$PWD/alembic:/app/alembic:ro" \
  api-api:latest env \
  DATABASE_URL=sqlite:// TEST_DATABASE_URL= \
  SERVICE_PRICING_MIGRATION_DATABASE_URL= SECRETARY_MIGRATION_DATABASE_URL= \
  PAYMENT_IDEMPOTENCY_MIGRATION_DATABASE_URL= PAYMENT_BATCH_MIGRATION_DATABASE_URL= \
  RECEIVABLES_MIGRATION_DATABASE_URL= SALE_PRICE_MODE_MIGRATION_DATABASE_URL= \
  ARCA_HOMOLOGATION_ENABLED=false ARCA_LOCAL_CREDENTIALS_ENABLED=false \
  uv run --frozen --no-sync pytest app/tests -q -ra \
  --deselect=app/tests/test_catalog_pricing_migration.py::test_upgrade_two_tenants_pending_zero_and_idempotence \
  --deselect=app/tests/test_purchase_discount_migration.py::test_historical_defaults_old_writers_constraints_and_guarded_downgrade \
  2>&1 | tee /tmp/vetflow-slice4-backend.log
```

Alcance exacto: suite ordinaria completa **sin ejecutar cuerpos de migración**. Se deseleccionan explícitamente esos dos casos SQLite porque llaman `upgrade`/`downgrade` en sus fixtures; ya tienen evidencia focalizada en slices 1/3. Las pruebas de grafo permanecen incluidas. Las seis variables vacías saltan las pruebas históricas de migración PostgreSQL; `TEST_DATABASE_URL` vacío salta las de integridad/concurrencia PostgreSQL. Los helpers puros de conversión de pasos históricos no ejecutan DDL y permanecen incluidos. No hay `upgrade`, `downgrade`, `stamp`, restauración o recreación de una base como preparación de pytest.

No se cambiaron mecanismos de bloqueo y no se identificó una regresión PostgreSQL adicional indispensable para estas correcciones. Esa cobertura opt-in queda pendiente, no aprobada implícitamente. No habilitar toda la batería sobre `db/vetflow`: algunas fixtures no aíslan un esquema privado. Si después se exige PostgreSQL, seleccionar una base de pruebas ya verificada y sólo archivos con aislamiento demostrado; `test_purchase_filter_options.py` usa esquema UUID dentro de transacción y `test_sale_transaction_composition.py` usa esquema UUID y `schema_translate_map` para todas sus sesiones. Este cierre no crea esa base ni entrega un comando contra un destino aún desconocido.

### Frontend: runner existente y build de producción local

No hay script `test` en `package.json`: se usa Node. `rg --files` incluye pruebas nuevas no confirmadas, entre ellas las del modal y descuento; no depende de `git ls-files`. La lista se pasa como argumentos separados, incluso con espacios en rutas.

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/web
set -o pipefail
mapfile -d '' vetflow_test_files < <(rg --files -0 -g '*.test.cjs' src)
if [ "${#vetflow_test_files[@]}" -eq 0 ]; then
  printf '%s\n' 'No se encontraron pruebas frontend.' >&2
  false
else
  pnpm exec node --test "${vetflow_test_files[@]}" \
    2>&1 | tee /tmp/vetflow-slice4-frontend.log
fi
```

El `.env.local` existente debe contener la configuración pública real del proyecto de autenticación de desarrollo: `NEXT_PUBLIC_FIREBASE_API_KEY`, `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`, `NEXT_PUBLIC_FIREBASE_PROJECT_ID`, `NEXT_PUBLIC_FIREBASE_APP_ID`, `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET`, `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`. No copiar credenciales privadas ni inventar valores. `NEXT_PUBLIC_API_BASE_URL` y `NEXT_PUBLIC_AI_FEATURES_ENABLED` se fijan en el comando para apuntar al API local. Firebase se inicializa en el cliente; el build no necesita iniciar sesión ni contactar Firebase, ARCA o buckets. No se añadió descarga de fuentes ni llamadas de build a esos servicios.

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/web
set -o pipefail
test -f .env.local &&
NEXT_TELEMETRY_DISABLED=1 \
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
NEXT_PUBLIC_AI_FEATURES_ENABLED=false \
pnpm run build 2>&1 | tee /tmp/vetflow-slice4-build.log
```

Next 14.2.15 con `next.config.mjs` actual ejecuta lint y comprobación de tipos en `next build`; no se proponen `tsc`/lint duplicados. Si falta configuración o falla el build, compartir el error; no instalar paquetes ni reemplazar credenciales para ocultarlo.

Compartir: comando ejecutado, código de salida, resumen de pasados/fallidos/saltados/deseleccionados, nombres y motivos de los skips (`-ra`), y resultado/error del build. Indicar también si el runner frontend informa resultados por archivo y escenarios internos. Adjuntar sólo logs revisados, sin tokens, credenciales ni URLs de conexión privadas. Un resultado con skips no acredita PostgreSQL ni ejecución nueva de migraciones.

## Arranque local mínimo para aceptación — propuesto

La base local ya está en 0061 según el slice 3: **no reaplicar migraciones**. Compose monta credenciales/almacenamiento, pero no las fuentes del API, por lo que se propone una sola reconstrucción del API tras cerrar el código. Ambos volúmenes existentes fueron comprobados por nombre; las comprobaciones siguientes impiden continuar si faltan. No reconstruir PostgreSQL, no ejecutar `down -v`, no crear/restaurar bases ni volúmenes. Si hay procesos previos usando los puertos, conservarlos y resolver su uso deliberadamente.

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/api
docker volume inspect api_postgres_vetflow_data api_local_vetflow_storage \
  --format '{{.Name}}' &&
docker compose -p api up -d --no-recreate --no-build --pull never db &&
docker compose -p api build api &&
docker compose -p api up -d --no-deps --no-build --pull never api &&
curl --fail --show-error --retry 15 --retry-connrefused --retry-delay 1 \
  http://127.0.0.1:8000/health
```

Compose mantiene AI apagada y bucket vacío; no pasa flags ARCA, cuyo valor por defecto es deshabilitado. Conserva la configuración Firebase de desarrollo existente para la sesión real. No pegar secretos en consola ni iniciar sesión externa como parte del build.

Tras un build correcto, en otra terminal se puede servir ese mismo build para el checklist:

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/web
NEXT_TELEMETRY_DISABLED=1 \
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
NEXT_PUBLIC_AI_FEATURES_ENABLED=false \
pnpm run start --hostname 127.0.0.1 --port 3000
```

Alternativa durante desarrollo (elegir uno, no ocupar el puerto dos veces):

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform/apps/web
NEXT_TELEMETRY_DISABLED=1 \
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
NEXT_PUBLIC_AI_FEATURES_ENABLED=false \
pnpm run dev --hostname 127.0.0.1 --port 3000
```

Abrir `http://localhost:3000` con la sesión real de desarrollo de Iván y el tenant/rol habitual, sin bypass de auth. Al terminar, Ctrl-C al servidor propio. Como no había contenedores en ejecución al cerrar este slice, si Iván inicia ambos exclusivamente para esta aceptación puede detenerlos con `docker compose -p api stop api db` desde `apps/api`; no eliminar contenedores, redes o volúmenes ni detener servicios ajenos.

## Checklist manual pendiente

Crear sólo datos propios identificables con prefijo `S4-20261030-`; no editar los pendientes ni documentos ajenos. Usar un proveedor de prueba propio. Las cifras de referencia presuponen IVA cero y ausencia de redondeo adicional; si la clínica tiene redondeo configurado, contrastar con la fórmula/previsualización vigente **sin cambiar preferencias para ajustar el ejemplo**. Los escenarios de centavos ya tienen cobertura aislada.

| Recorrido | Acción breve | Resultado esperado |
| --- | --- | --- |
| Costo vigente y nueva referencia | Producto propio costo 1000/margen 30/stock 0; recibir 2×1200 con descuento 10%; editar costo a 900 y recibir 1×950. En otro producto, recibir un costo inferior al vigente. | Primera compra 2400/240/2160; costos originales sin descuento. Catálogo sube a 1200, conserva un costo mayor ante recepción menor y usa 900 como nueva referencia tras edición. Stock suma sólo las unidades recibidas; descuento no cambia costo/IVA del catálogo. Venta según margen y redondeo actuales. |
| Modal y URL | Con filtro y página distinta de 1, abrir producto propio, editar costo o marca, guardar y cerrar; volver a abrir. Repetir con red lenta. | Datos persistidos visibles sin recargar página ni `read_cancelled`; filtros/página conservados. Si deja de cumplir el filtro, desaparece; una respuesta vieja no repone datos anteriores. |
| Recuperación de lectura | En DevTools fallar deliberadamente una lectura posterior a guardar; usar reintento de lectura. Por separado, fallar PATCH. | Tras guardado se explica que ya se guardó y se recupera leyendo, sin repetir PATCH. PATCH fallido conserva edición para corregir/reintentar intencionalmente. |
| Cuatro acciones de precio | Sobre productos propios completos, previsualizar/confirmar y deshacer cada una: aumentar venta 10%, disminuir 10%, establecer margen 40%, establecer precio representable. Revisar detalle persistido. | Con base 1000/30 sin IVA/redondeo: 1430/43%, 1170/17%, 1400/40%, objetivo 1500/50%. Costo, cantidades e impuestos intactos. Preview, confirmación y lectura coinciden; deshacer recalcula sin modo fijo. |
| Otras cinco acciones | Establecer marca, proveedor textual y stock mínimo; inactivar y activar. Ver preview y lectura después de cada acción. | Sólo cambia el campo pedido; precios, costo, cantidades e impuestos ajenos se conservan. Se puede deshacer sin pisar cambios posteriores. |
| Selección y conflictos | Crear los productos propios necesarios para dos páginas y filtrar por su prefijo. Seleccionar entre páginas; probar seleccionar todo filtrado con una exclusión. En otra pestaña cambiar un seleccionado tras preview e intentar confirmar. | No se pierden selecciones ni exclusiones; afecta sólo el conjunto esperado. El cambio concurrente produce conflicto sin aplicación parcial del grupo válido; reabrir/previsualizar antes de confirmar. |
| Objetivo imposible | Producto propio con costo positivo 1000, IVA cero: pedir precio 500, que exigiría margen negativo. | Fila inválida en preview con explicación comprensible; no cambia costo, impuestos o preferencias ni aplica ese precio. |
| Borrador con descuento | Crear compra propia de 1000 con 10%; guardar/reabrir. Cambiar a importe 150, modificar líneas, quitar descuento. Probar cero y 100%. | Original/descuento/neto 1000/100/900; fijo 150 conservado al editar líneas y rechazado si supera bruto; quitar deja none/0 y neto=bruto. Cero y neto cero válidos; reabrir conserva modalidad/valor. Lista, detalle, resumen filtrado y dashboard usan bruto/neto con etiquetas correctas. |
| Recepción e historial | Recibir una compra descontada; intentar repetir recepción y editar descuento. Después editar costo/margen del producto. | Una recepción, stock correcto y costo unitario original; descuento bloqueado por estado. Compra y venta histórica propia conservan costos/precios/importes originales tras editar catálogo. |
| Pendientes y cero | Crear producto propio incompleto e inactivo; hallarlo con filtro de pendientes y actividad que incluya inactivos, también en otra página. Completar costo/margen; probar además un costo/precio cero válido. | Aparece pendiente aun con importe legado; completar produce precio calculado y sale del filtro al guardar. Cero no se presenta como ausencia de datos. No se completa masivamente el inventario existente. |
| Devoluciones | Compra propia recibida sin descuento: devolver normalmente. Repetir con descuento monetario cero. En compra con descuento positivo, revisar el acceso a devolución y stock antes/después. | Las dos primeras funcionan; la positiva explica que la devolución automática requiere definir su importe y no ofrece completarla. Ninguna devolución confirmada ni cambio de stock por el intento bloqueado; API responde 409 antes de mutar. |
| Reversiones distintas | En documentos propios sin devoluciones confirmadas y sin cambios posteriores incompatibles, cancelar un borrador/revertir recepción o acción grupal usando sus controles habituales. | Conservan sus reglas previas; no quedan bloqueadas por la protección de devolución con descuento. Conflictos legítimos no sobrescriben cambios posteriores. |

Anotar por fila aprobado/fallido/omitido con motivo y mensajes visibles. La restricción positiva requiere además una decisión explícita de aceptación; observar que bloquea correctamente no equivale a aceptarla como producto.

## Grafo y publicación conjunta — preparar, no ejecutar

Grafo comprobado desde archivos (sin `current` productivo):

```text
0054_receivables_foundation
  ├─ 0055_arca_fiscal_configuration
  │    → 0056_arca_fiscal_proposals → 0057_arca_auth → 0058_arca_emission ─┐
  └─ 0055_inventory_sale_price_mode ────────────────────────────────────┤
                                                                      ↓
                                                   0059_merge_arca_inventory
                                                       → 0060_inventory_calculated_prices
                                                       → 0061_purchase_global_discount (único head)
```

0060 transforma precios manuales completos sin archivar sus valores previos y aborta el downgrade. 0061 añade descuentos y protege su downgrade cuando hay datos de descuento. Publicar el esquema ARCA no habilita emisión fiscal ni acredita homologación.

El workflow real `.github/workflows/deploy-api.yml` corre por push a **main** que afecte `apps/api/**` o el propio workflow; también admite disparo manual. Ejecuta pytest, construye/push de imagen y despliega `vetflow-api` en Cloud Run, proyecto `vet-flow-494319`, región `us-central1`, imagen `us-central1-docker.pkg.dev/vet-flow-494319/vetflow/vetflow-api:<SHA del merge>`. **No ejecuta Alembic.** El Dockerfile tampoco migra al arrancar. No se encontró pipeline/configuración de publicación frontend en el repositorio; no se presupone Vercel, Firebase Hosting ni otro proveedor.

Orden y responsabilidades, después de los resultados y autorización posterior:

1. **Iván:** compartir suites/build/checklist, revisar fallos/skips y aceptar explícitamente o rechazar la limitación de devolución positiva. Revisar el diff completo, incluidos los archivos nuevos. Sólo después preparar commit/PR con los comandos de la sección siguiente; aún no mergear.
2. **Operador de publicación:** identificar el proveedor/pipeline frontend y su control de publicación; confirmar un runtime seguro ya aprobado que pueda ejecutar el candidato con sus migraciones/dependencias y acceder al destino productivo. La revisión/host/base de producción son **desconocidos en este cierre** y deben verificarse allí, sin compartir credenciales. No usar un contenedor de código viejo sin 0060/0061 ni la copia local de negocio.
3. **Operador:** reservar una ventana con escrituras detenidas en todas las revisiones/instancias y clientes antiguos, incluidas pestañas abiertas; controlar también la publicación automática frontend. Mantener esa ventana durante migración, pipeline backend y frontend. El workflow actual no implementa un bloqueo de escrituras ni coordina frontend: son prerrequisitos operativos, no resueltos por el merge. Si no se pueden garantizar, no mergear/publicar. El cambio mínimo pendiente es acordar la ventana y el paso manual seguro de Alembic antes del despliegue; si hace falta un gate de pipeline, se debe aprobar aparte, sin rediseñarlo en este slice.
4. **Operador, dentro de la ventana:** verificar que ARCA externo y credenciales locales estén apagados. El workflow no establece esas dos variables y `--update-env-vars` conserva valores previos; no se presupone su estado. Si hace falta fijarlas, el comando futuro es el siguiente (genera una revisión; nunca ejecutado aquí):

   ```bash
   gcloud run services update vetflow-api \
     --project vet-flow-494319 --region us-central1 \
     --update-env-vars ARCA_HOMOLOGATION_ENABLED=false,ARCA_LOCAL_CREDENTIALS_ENABLED=false
   ```

   Mantener emisión fiscal deshabilitada y no ejecutar flujos ARCA, WSAA, WSFE ni homologación como smoke. Las barreras de entorno fiscal de la aplicación también se conservan.

5. **Operador, runtime aprobado del candidato con WORKDIR `/app`:** comprobar destino y revisión antes de una única actualización incremental. Los comandos siguientes son futuros y requieren que esa sesión exista, tenga el candidato validado y `DATABASE_URL` configurada por el mecanismo seguro habitual; este repo no identifica ese runner y no se inventó uno. Primero, mostrar sólo host/puerto/base, cotejarlos con el destino aprobado y consultar revisión:

   ```bash
   cd /app
   uv run --frozen --no-sync python -c 'from sqlalchemy.engine import make_url; from app.core.config import get_settings; u=make_url(get_settings().database_url); print({"host": u.host, "port": u.port, "database": u.database})'
   uv run --frozen --no-sync alembic heads
   uv run --frozen --no-sync alembic current
   ```

   Si el destino o revisión no corresponde, detenerse. Si ya está en 0061, no reaplicar. Si la revisión verificada es un ancestro esperado del grafo y se autoriza avanzar, ejecutar **una vez**:

   ```bash
   cd /app
   uv run --frozen --no-sync alembic upgrade head
   uv run --frozen --no-sync alembic current
   ```

   Confirmar único head 0061; nunca usar `stamp` para omitir migraciones. Este paso no forma parte de pytest ni se ejecuta sobre la base local en este cierre.

6. **Iván/operador:** con migración verificada y escrituras aún detenidas, mergear el PR a main. El workflow existente ejecuta tests/build/push/deploy backend; esperar éxito y confirmar la revisión/imagen del SHA resultante. Si se usa disparo manual, hacerlo deliberadamente sobre la referencia revisada y evitar despliegues duplicados. No hay una etapa automática de Alembic que deba repetirse.
7. **Responsable frontend:** publicar el frontend del mismo cambio mediante el proveedor real identificado antes de la ventana, después del backend compatible con 0061; confirmar URL/API/env correctos. El comando concreto de ese proveedor queda pendiente de identificarlo, no de sustituirlo por una herramienta inventada. Evitar que una integración externa publique antes de tiempo al mergear.
8. **Operador:** smoke de sólo salud, sesión/roles/tenant y lecturas reales de inventario/compras (bruto/descuento/neto y pendientes). Usar `/health` en la URL efectiva del servicio y lecturas desde la app; no crear compras ficticias, devoluciones ni certificados productivos. Verificar flags ARCA apagados, conservar resultados y recién entonces reabrir escrituras/renovar clientes antiguos.

Contingencia: ante fallo de migración, tests del pipeline, backend, frontend o smoke, mantener escrituras detenidas y diagnosticar/corregir hacia adelante. No hacer downgrade de 0060 ni volver automáticamente a código anterior que ignore descuentos registrados. Preservar el backup manual existente sin restaurarlo ni probarlo aquí. Un fallo parcial no autoriza repetir a ciegas una transformación: primero comprobar revisión y causa en el runtime aprobado.

## Commit, push y PR posteriores — no ejecutados

El estado publicable incluye el diff de trabajo y los archivos nuevos; HEAD por sí solo no los contiene. La lista explícita siguiente incluye los cambios recibidos de slices 1–3 y este cierre, sin secretos, `.env`, credenciales ni lockfiles. Revisarla contra `git status` en el momento de usarla. Detenerse si se está en otra rama o aparecen cambios ajenos nuevos.

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform
git status --short
test "$(git branch --show-current)" = "feature/arca1-fiscal-proposals" &&
git diff --check &&
git add -- \
  apps/api/alembic/versions/0060_inventory_calculated_prices.py \
  apps/api/alembic/versions/0061_purchase_global_discount.py \
  apps/api/app/core/inventory_pricing.py \
  apps/api/app/core/purchase_discount.py \
  apps/api/app/models/inventory_item.py \
  apps/api/app/models/purchase.py \
  apps/api/app/repositories/inventory.py \
  apps/api/app/repositories/purchase.py \
  apps/api/app/repositories/purchase_dashboard.py \
  apps/api/app/schemas/inventory.py \
  apps/api/app/schemas/purchase.py \
  apps/api/app/schemas/purchase_dashboard.py \
  apps/api/app/services/clinic.py \
  apps/api/app/services/inventory.py \
  apps/api/app/services/inventory_bulk_operation.py \
  apps/api/app/services/inventory_import.py \
  apps/api/app/services/purchase.py \
  apps/api/app/services/purchase_dashboard.py \
  apps/api/app/services/purchase_return.py \
  apps/api/app/services/sale.py \
  apps/api/app/tests/test_catalog_pricing_migration.py \
  apps/api/app/tests/test_inventory.py \
  apps/api/app/tests/test_inventory_bulk_operations.py \
  apps/api/app/tests/test_inventory_imports.py \
  apps/api/app/tests/test_inventory_purchase_slices_integration.py \
  apps/api/app/tests/test_inventory_sale_price_mode_migration.py \
  apps/api/app/tests/test_purchase_dashboard.py \
  apps/api/app/tests/test_purchase_discount_migration.py \
  apps/api/app/tests/test_purchase_discounts.py \
  apps/api/app/tests/test_purchase_receipts.py \
  apps/api/app/tests/test_purchase_returns.py \
  apps/api/app/tests/test_purchases.py \
  apps/api/app/tests/test_sales.py \
  apps/web/src/features/inventory/components/inventory-bulk-operation-detail.tsx \
  apps/web/src/features/inventory/components/inventory-bulk-values.ts \
  apps/web/src/features/inventory/components/inventory-create-screen.tsx \
  apps/web/src/features/inventory/components/inventory-detail-modal.tsx \
  apps/web/src/features/inventory/components/inventory-detail.tsx \
  apps/web/src/features/inventory/components/inventory-helpers.tsx \
  apps/web/src/features/inventory/components/inventory-item-form.tsx \
  apps/web/src/features/inventory/components/inventory-screen.tsx \
  apps/web/src/features/inventory/inventory-modal-refresh.test.cjs \
  apps/web/src/features/inventory/inventory-navigation.test.cjs \
  apps/web/src/features/inventory/inventory-pricing.test.cjs \
  apps/web/src/features/purchases/components/purchase-dashboard-screen.tsx \
  apps/web/src/features/purchases/components/purchase-detail-screen.tsx \
  apps/web/src/features/purchases/components/purchase-discount.ts \
  apps/web/src/features/purchases/components/purchase-form-screen.tsx \
  apps/web/src/features/purchases/components/purchase-helpers.ts \
  apps/web/src/features/purchases/components/purchase-return-form-screen.tsx \
  apps/web/src/features/purchases/components/purchases-screen.tsx \
  apps/web/src/features/purchases/purchase-discount.test.cjs \
  apps/web/src/features/sales/components/sale-form-screen.tsx \
  apps/web/src/features/sales/sale-draft.test.cjs \
  apps/web/src/lib/api.ts \
  apps/web/src/services/inventory.ts \
  apps/web/src/types/api.ts \
  docs/validacion-slices-1-4.md &&
git diff --cached --check &&
git diff --cached --stat &&
git diff --cached
```

Sólo después de revisar el contenido staged y con aprobación posterior para confirmarlo/publicarlo:

```bash
cd /home/ivanpuyo/Quark/projects/vetflow-platform
test "$(git branch --show-current)" = "feature/arca1-fiscal-proposals" &&
git commit -m "Calculate inventory prices and add global purchase discounts" &&
git push -u origin feature/arca1-fiscal-proposals
```

Después del push, abrir el PR de `feature/arca1-fiscal-proposals` hacia `main` desde la interfaz del repositorio. `gh` no está instalado en este entorno, por eso no se supone ese CLI. Descripción propuesta:

> El catálogo calcula el precio a partir de costo/IVA/margen y las recepciones conservan el costo vigente mayor. Las nueve acciones grupales usan porcentajes equivalentes y el modal recupera lecturas tras guardar. Compras conserva el bruto y añade descuento global y neto, sin alterar costos originales ni documentos históricos. Las devoluciones con descuento positivo quedan protegidas, sujetas a aceptación explícita. Incluye migraciones 0060/0061 y requiere ventana de escrituras y Alembic manual antes del despliegue; el workflow no migra. Adjuntar aquí los resultados reales de suites/build/checklist antes de solicitar publicación.

No mergear ni disparar workflows hasta completar las condiciones operativas anteriores. El cierre operativo continúa cuando Iván aporte resultados y se revisen las decisiones pendientes.

## Recursos al cierre

Los contenedores de regresión y lectura del grafo usaron `--rm` y red deshabilitada. No quedaron contenedores en ejecución; no se iniciaron servicios Compose, servidores ni navegadores persistentes en este slice. Volúmenes previos y cambios de trabajo preservados. No hubo conexiones a producción ni servicios externos, instalaciones, cambios de lockfiles, operaciones sobre backups ni ejecución de migraciones, commit/push/merge/despliegue. Los comandos de arranque/publicación anteriores quedan propuestos para sus responsables.
