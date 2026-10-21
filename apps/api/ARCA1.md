# ARCA.1 implementado

Este bloque implementa configuración y revisión fiscal local. No ejecuta WSAA,
WSFEv1 ni emisión externa. Producción permanece bloqueada aunque se complete su
configuración. No se aceptan certificados, claves privadas, passwords fiscales ni
tokens: las únicas referencias de credenciales admitidas usan `opaque://...`.

## Dominio y decisiones

- Se reutiliza `FiscalIssuer`, su usuario responsable y los adjuntos históricos.
  CUIT, razón fiscal y condición fiscal nuevos son opcionales para históricos;
  no se derivan de `tax_id` ni se completan mediante valores inventados. El CUIT
  se normaliza y verifica con módulo 11; un resultado 10 se rechaza.
- La política es opt-in, inicialmente desactivada. `electronic_only` selecciona
  transferencias, tarjetas y billeteras; efectivo queda separado y `other`
  requiere revisión explícita. `all_payments` permite incluirlos. Excluir efectivo
  no declara una exención. La revisión contable registra actor, fecha, alcance,
  versión y nota; cambiar la política invalida la revisión corriente y conserva
  su historial.
- Una serie se identifica por tenant, CUIT real, ambiente, POS y tipo. El concepto
  no permite duplicar una numeración. CAE/CAEA son configuración y puntos de
  extensión, sin autorizaciones simuladas.
- Se conserva `PaymentMethod.type` y el snapshot de `SalePayment`. La referencia
  operativa y el emisor sugerido del método sólo orientan propuestas futuras;
  nunca confirman un emisor ni modifican imputaciones aprobadas.
- Las propuestas requieren ventas confirmadas ARS y cobros activos íntegros.
  Se agrupan por una serie explícita compatible; una selección automática
  ambigua no elige la primera serie. Se conservan la clasificación fiscal de
  medicamentos como servicios y los importes Decimal al centavo.
- No se prorratean cobros. Una selección parcial de una venta mixta queda
  bloqueada. Si una selección parcial de varias líneas de servicios necesita
  una descripción fiscal específica, se exige guardar una revisión explícita.
- Generar/revisar un borrador no reserva fondos ni toca la venta, el stock o los
  cobros. Aprobar reserva cada pago completo, conserva el contenido y no crea un
  documento fiscal. Se detectan cambios en venta, pagos y configuración antes
  de aprobar.
- La aprobación usa `Idempotency-Key` y un hash del contenido confirmado. La
  misma intención recupera su resultado; otra identidad o contenido genera
  conflicto. La cancelación conserva la aprobación y libera reservas con actor,
  fecha y motivo. Reaprobar requiere otra propuesta e intención.
- La exclusión mutua usa el lock de la venta, locks de pagos/configuración,
  unicidad de claves por tenant e índice único parcial de reserva activa por
  pago. Las relaciones de imputación a venta/pago/propuesta/documento tienen
  claves compuestas que incluyen tenant y venta.
- `fiscal_document` y sus rutas singulares siguen representando el adjunto manual
  activo. `fiscal_documents` y `fiscal_document_totals` son colecciones explícitas.
  Documentos manuales y futuros documentos ARCA tienen fuente/estado distintos.
  Un borrador o propuesta aprobada no marca una venta como documentada.
- Un comprobante manual activo sin imputación conocida bloquea nuevas
  aprobaciones. Su regularización exige seleccionar pagos completos cuya suma
  coincida exactamente con el total histórico y confirmar identidad. Incluye
  efectivo si corresponde al comprobante histórico, independientemente de la
  política de propuestas. Conserva archivo, snapshots e historial; después no
  permite reemplazar identidad/archivo por la ruta manual.
- Los documentos autorizados se protegen contra edición de identidad, borrado,
  degradación de autorización y desactivación. No existe anulación ARCA mediante
  `is_active=false`.

## Permisos y errores recuperables

Toda operación fiscal exige un actor activo real y un rol coincidente dentro del
tenant. `clinic_admin` y `contador` gestionan configuración y revisión;
`medico_veterinario` sólo revisa/aprueba su emisor vinculado; `secretaria` consulta.
No hay permiso por omisión ni excepción implícita para `superadmin`. Los IDs
ajenos se ocultan con 404. Adjuntos manuales aplican estas mismas reglas.

`fiscal_payment_reserved` y `fiscal_sale_reserved` devuelven 409: cancelar la
propuesta aprobada **aún no enviada** libera su reserva y permite volver a anular
el cobro o revertir la venta. Los estados enviados, inciertos o autorizados
requieren conciliación fiscal; no son cancelables como borrador. Una imputación
manual regularizada requiere revisión contable para corregirla y no se libera
desde una propuesta.

`fiscal_proposal_stale` requiere volver a cargar y guardar la revisión.
`fiscal_approval_idempotency_conflict` requiere una intención nueva para contenido
distinto. Los bloqueos por composición no admiten reparto automático del pago.

## API y pantallas

- `/api/v1/fiscal/configuration`: política, emisores, series, mapping y permisos.
- `/api/v1/sales/{id}/fiscal-review`: elegibilidad, pagos, propuestas, documentos,
  totales y acciones permitidas.
- `/api/v1/sales/{id}/fiscal-proposals`: generación, revisión, aprobación y
  cancelación explícitas.
- `/api/v1/sales/{id}/fiscal-documents/{document_id}/allocate`: regularización
  manual confirmada e idempotente.
- UI: `/settings/sales/fiscal`, emisores existentes y revisión dentro del detalle
  de venta. Muestra reservas, exclusiones, pendientes, recuperación y el límite
  de emisión externa ARCA.2, sin CAE ficticios.

## Validación realizada

Backend ejecutado exclusivamente con la imagen Docker local existente, código
actual montado en lectura, `uv run --frozen --no-sync`, credenciales externas
vacías y PostgreSQL Compose local verificado por proyecto/contenedor/red/alias.

- PASS: pasada focalizada de dominio, permisos y las regresiones fiscales/cobros
  indicadas en la solicitud: 290 casos, 14 excluidos por filtro PostgreSQL y un
  caso omitido (`test_concurrent_payments_cannot_overpay`, que requiere
  `TEST_DATABASE_URL` y pertenece a las pruebas anteriores).
- PASS: `pytest -q -p no:cacheprovider app/tests/test_arca1_proposals.py`: 19 casos.
- PASS: pasada final de `test_arca1_permissions.py`,
  `test_sale_fiscal_documents.py`, `test_role_permissions.py`: 147 casos tras
  cerrar los permisos de adjuntos manuales.
- PASS: `test_arca1_postgresql.py`: cuatro carreras reales de reservas,
  idempotencia, anulación y reversión. Todas las sesiones/threads usaron un
  esquema sintético `arca1_test_<uuid>` con `schema_translate_map`; se verificó su
  eliminación y la ausencia de fixtures en `public`.
- PASS: frontend `pnpm exec tsc --noEmit`, lint focalizado por archivo y las tres
  regresiones Node solicitadas. El flujo nuevo ejecutó sus 27 casos mediante
  `node src/features/sales/arca1-fiscal.test.cjs`, además de `node --test`.
- PASS: `git diff --check` e introspección de columnas, restricciones e índices.

Alembic local pasó de `0054_receivables_foundation` a
`0056_arca_fiscal_proposals` mediante un único `upgrade head` que aplicó 0055 y
0056. Se comprobaron los conteos y hashes agregados de IDs históricos antes y
después; no se inventaron identidades fiscales ni se activó la política de ningún
tenant. No se ejecutaron downgrade, stamp, restauraciones o pruebas que requieren
una base vacía. Se eliminaron contenedores efímeros propios y se devolvió el DB
existente al estado detenido que tenía antes de la tarea, conservando su volumen.

NO EJECUTADO: suites completas, build web, pruebas destructivas de migración y
comunicaciones externas, según el alcance ARCA.1. No se iniciaron servidores UI.
ARCA.2 deberá implementar WSAA/WSFEv1, credenciales referenciadas, conciliación de
resultados inciertos y emisión real; ARCA.3 cubrirá suites completas y hardening
integral. No hubo commits, push, merge, cambios CI/CD ni despliegues.

Comandos backend ejecutados dentro de los contenedores efímeros locales descritos
arriba (no con el Python del host):

```sh
uv run --frozen --no-sync alembic current
uv run --frozen --no-sync alembic heads
uv run --frozen --no-sync alembic upgrade head
uv run --frozen --no-sync alembic current

uv run --frozen --no-sync pytest -q -p no:cacheprovider --tb=short \
  app/tests/test_arca1_domain.py app/tests/test_arca1_permissions.py \
  app/tests/test_fiscal_issuers.py app/tests/test_sale_fiscal_documents.py \
  app/tests/test_payment_classification.py app/tests/test_sale_payments.py \
  app/tests/test_sale_payment_idempotency.py app/tests/test_sale_confirmation_batch.py \
  -k 'not postgresql and not postgres'
uv run --frozen --no-sync pytest -q -p no:cacheprovider --tb=short \
  app/tests/test_arca1_proposals.py
uv run --frozen --no-sync pytest -q -p no:cacheprovider --tb=short \
  app/tests/test_arca1_permissions.py app/tests/test_sale_fiscal_documents.py \
  app/tests/test_role_permissions.py -k 'not postgresql and not postgres'
uv run --frozen --no-sync pytest -q -p no:cacheprovider --tb=short \
  app/tests/test_arca1_postgresql.py
```

Sólo el último comando recibió `TEST_DATABASE_URL`, apuntando al mismo DB Docker
local validado, para crear/eliminar exclusivamente sus esquemas de prueba.

Frontend, desde `apps/web`, reutilizando dependencias existentes:

```sh
pnpm exec tsc --noEmit
node --test src/features/sales/sale-fiscal.test.cjs
node --test src/features/sales/payment-method-classification.test.cjs
node --test src/features/sales/sale-confirmation.test.cjs
node --test src/features/sales/arca1-fiscal.test.cjs
node src/features/sales/arca1-fiscal.test.cjs
```

El lint se ejecutó con `pnpm exec next lint --file <ruta>`, repitiendo `--file`
para cada archivo frontend modificado. La ejecución directa del archivo nuevo
confirma los 27 subcasos, además del resultado del proceso del runner Node.
