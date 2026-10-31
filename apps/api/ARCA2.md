# ARCA.2: implementación local

Implementado sobre ARCA.1 en `feature/arca1-fiscal-proposals`, sin commits,
push, merge, CI/CD ni despliegues. **Homologación externa pendiente de accesos y
validación. Producción permanece bloqueada en servidor**, antes de resolver
material de credenciales o crear transporte. No se realizaron comunicaciones de
negocio con WSAA, WSFE, Secret Manager, Firebase, buckets ni otros servicios.

## Comportamiento y archivos

- `services/arca_credentials.py`, `arca_wsaa.py`, `arca_runtime.py`: registro de
  servidor `opaque://`, proveedores Secret Manager/local inyectables, validación
  de pareja RSA/vigencia/huella, TRA/CMS real y WSAA `loginCms` para `wsfe`.
  La firma usa OpenSSL disponible en la imagen con RSA/SHA-1, según el contrato
  WSAA; cryptography no permite ese algoritmo en su constructor PKCS7. La clave
  descifrada en memoria se entrega por descriptor anónimo; el password sólo se
  usa en memoria para abrirla, sin argumentos secretos ni archivos persistentes.
  No se cambian políticas TLS.
- `models/arca_auth.py`, `repositories/arca_auth.py`: TA cifrado AES-256-GCM,
  claves externas versionadas y AAD de identidad/ambiente/servicio/ámbito. El
  coordinador global de certificado evita renovar dos veces un mismo TA; los
  grants cifrados incorporan tenant/referencia/CUIT. Claims y fencing PostgreSQL
  coordinan procesos. Una respuesta WSAA incierta/alreadyAuthenticated programa
  recuperación conservadora; no hay bucles ni sleeps. Rotar huella afecta sólo
  su caché; rotar clave de cifrado reenvuelve perezosamente el ámbito consultado.
- `schemas/arca_emission.py`, `services/arca_wsfe.py`: serializador/parser SOAP
  real con httpx y XML seguro, límites, TLS, endpoints oficiales cerrados,
  sin redirects/proxies de entorno/reintentos automáticos. Implementa los seis
  parámetros solicitados, último autorizado, CAE y consulta exacta. Catálogos no
  acreditan habilitación efectiva de un contribuyente.
- `models/arca_emission.py`, `repositories/arca_emission.py`,
  `services/arca_emission.py`: intención explícita e idempotente por aprobación,
  snapshot completo, serie remota de propietario exclusivo y claims con fence.
  Antes del primer envío se revalidan política/emisor/serie/referencia. Se
  persisten número, payload y hash antes de enviar; ninguna transacción de
  negocio se mantiene abierta durante autenticación o HTTP. Otra clave no crea
  una segunda emisión para una propuesta comprometida.
- Un timeout, XML incompleto, caída antes del envío o fallo DB después del CAE
  conserva reservas y número. La recuperación consulta ese número después de
  reiniciar servicios. Un conflicto conserva el bloqueo de serie. Un reenvío
  requiere acción y confirmación separadas, consulta previa que informe ausencia
  y exactamente el mismo número/payload. Un rechazo definitivo se corrige con
  nueva intención y `supersedes_id`; no se modifica la anterior.
- Autorización/CAE/documento se confirman atómicamente. Generar o regenerar
  PDF/storage es posterior y recuperable; nunca vuelve a emitir. Las versiones
  conservan hash y rutas tenant/ambiente/emisor/documento. El PDF usa sólo el
  snapshot autorizado y la porción documentada, con Decimal exacto y QR oficial.
  WeasyPrint exige el QR cargado y dibujado; un error SVG impide aceptar el PDF.
- `templates/arca_invoice.html`, `services/arca_pdf.py`: marca visible
  **HOMOLOGACIÓN — SIN VALIDEZ FISCAL**, escape de texto y assets limitados al QR
  generado en memoria. Sin descarga de recursos elegidos por usuario.
- UI en Ajustes fiscales y detalle de venta: confirmación de identidad/receptor,
  preparación, emisión explícita, resultado incierto, consulta, corrección de
  rechazo, archivo pendiente, regeneración y versiones. Usa acciones del
  servidor y desactiva retries genéricos en POST fiscales. Ajustes diferencia
  consulta local y validación remota explícita.

Se conservan ventas, pagos, inventario, aprobación histórica y reservas ARCA.1.
Los documentos de homologación no documentan productivamente la venta. Las
colecciones y totales identifican su ambiente; el singular sigue siendo manual.
No hay excepción implícita para superadmin. Administrador/contador gestionan;
veterinario opera su emisor; secretaria consulta. IDs y versiones ajenos dan 404.

## API

Todas las rutas están bajo `/api/v1`, autenticadas y con tenant derivado del
actor. No aceptan recursos Secret Manager, rutas privadas ni tenants del cliente.

| Ruta | Operación |
| --- | --- |
| GET `/sales/{sale}/fiscal-emissions` | Estado durable, historial y acciones |
| POST misma ruta | Confirmar intención; exige `Idempotency-Key` |
| POST `.../{intent}/issue` | Emitir intención persistida, `{ "confirm": true }` |
| POST `.../{intent}/reconcile` | Consultar número exacto; sin reenvío por defecto |
| POST `.../{intent}/regenerate` | Recuperar archivo de autorización existente |
| GET `.../{intent}/file?version_id={uuid}` | PDF/version autenticada, sin URL pública |
| GET `/fiscal/emission-pending` | Entrada operativa para recuperar pendientes |
| GET `/fiscal/emission-readiness?series_id={uuid}` | Sólo metadatos locales |
| POST `/fiscal/emission-readiness/validate` | Validación remota explícita `{ "series_id": "..." }` |

El reenvío excepcional usa `{ "retry_same_request": true, "confirm": true }`
en reconcile. Una respuesta fallida de consulta no habilita ese reenvío. Ante
`processing` con claim vigente, esperar su vencimiento; no crear otra intención.
La API conserva la operación aunque se pierda la respuesta del navegador.

## Fuentes oficiales y límites

Consultadas el 2026-10-20, sólo para implementar el protocolo:

- [WSAA](https://www.afip.gob.ar/ws/documentacion/wsaa.asp) y
  [especificación 1.2.2](https://www.afip.gob.ar/ws/WSAA/Especificacion_Tecnica_WSAA_1.2.2.pdf):
  TRA, CMS RSA/SHA-1, `wsfe`, tiempos, `loginCms` y TA.
- [WSFE general](https://www.afip.gob.ar/ws/documentacion/ws-factura-electronica.asp):
  manual 4.7, historial 2026-09-01.
  [Homologación](https://www.afip.gob.ar/ws/documentacion/homologacion-externa.asp)
  enlaza manual 4.8, con fecha nominal 2026-12-01, posterior a la consulta.
  Se registra la especificación publicada; no se afirma activación productiva
  ni validación externa. Se usan los contratos de parámetros, CAE, consulta,
  último autorizado y fechas. No se copian umbrales de identificación recordados.
- [QR versión 1](https://www.afip.gob.ar/fe/qr/documentos/QRespecificaciones.pdf):
  tabla normativa con `https://www.arca.gob.ar/fe/qr/`, campos numéricos y JSON
  Base64. No se usa la URL AFIP antigua del ejemplo.
- [Contingencias](https://www.afip.gob.ar/fe/emision-autorizacion/contingencias.asp):
  CAEA completo queda pendiente; nunca se cambia automáticamente desde un CAE
  incierto. También quedan pendientes habilitación productiva por emisor, circuito
  fiscal de corrección/notas de crédito, devoluciones y hardening/suites ARCA.3.
  Revertir venta o anular cobro no genera notas ni desactiva documentos autorizados.

## Migraciones y runtime de esta ejecución

El DB Docker existente estaba detenido y se inició sólo `api-db-1`. Se validaron
labels Compose `api/db`, proyecto/directorio, imagen `postgres:17`, red
`api_default`, alias `db` y volumen `api_postgres_vetflow_data` antes de conectar.
No se heredó DATABASE_URL de `.env`. Código actual montado en lectura, claves
externas vacías y homologación desactivada. Todos los comandos backend/uv/pytest/
Alembic se ejecutaron dentro de contenedores efímeros etiquetados propios.

Se preparó una imagen incremental desde `api-api` con el lockfile congelado,
una sola vez, reutilizando dependencias. Se declararon cryptography, defusedxml,
google-cloud-secret-manager y qrcode; se conservaron versiones ajenas. OpenSSL,
Jinja2 y WeasyPrint ya estaban disponibles. Poppler se instaló únicamente en
contenedores efímeros para inspección visual; no se añadió al producto.

`alembic current`: **0056_arca_fiscal_proposals**; `heads`: **0058_arca_emission**.
Un solo `upgrade head` aplicó 0057 y 0058. `current` final: **0058_arca_emission**.
Introspección de columnas/índices/constraints/FK: PASS. Conteos y hashes agregados
de IDs de **42 tablas históricas** idénticos antes/después. Las siete tablas
ARCA.2 de public quedaron vacías; ningún fixture se escribió allí. No se
inventaron identidades ni se activaron políticas. No hubo downgrade, stamp,
restore, recreación de DB ni pruebas de migración destructivas.

## Validación

Comandos bajo el wrapper Docker local verificado descrito arriba; `vf_api`
representa ese contenedor con código actual y `uv run --frozen --no-sync`:

```sh
vf_api uv run --frozen --no-sync alembic current
vf_api uv run --frozen --no-sync alembic heads
vf_api uv run --frozen --no-sync alembic upgrade head
vf_api uv run --frozen --no-sync alembic current

vf_api uv run --frozen --no-sync pytest -q -p no:cacheprovider --tb=short \
  app/tests/test_arca2_wsaa.py app/tests/test_arca2_wsfe.py \
  app/tests/test_arca2_emission.py app/tests/test_arca2_pdf.py \
  app/tests/test_arca2_permissions.py app/tests/test_arca1_domain.py \
  app/tests/test_arca1_proposals.py app/tests/test_arca1_permissions.py \
  app/tests/test_sale_fiscal_documents.py \
  -k 'not postgresql and not postgres'

# Revalidaciones afectadas: guards WSAA/emisión/herramienta y mensaje productivo.
vf_api uv run --frozen --no-sync pytest -q -p no:cacheprovider --tb=short \
  app/tests/test_arca2_wsaa.py app/tests/test_arca2_emission.py \
  app/tests/test_arca2_homologation_tool.py
vf_api uv run --frozen --no-sync pytest -q -p no:cacheprovider --tb=short \
  app/tests/test_arca1_domain.py

# Sólo esta pasada recibió TEST_DATABASE_URL explícita al mismo DB Docker.
vf_api uv run --frozen --no-sync pytest -q -p no:cacheprovider --tb=short \
  app/tests/test_arca2_postgresql.py app/tests/test_arca1_postgresql.py
```

- Alcance final obligatorio: **343 casos cubiertos, sin fallos pendientes**.
  La última pasada completa focalizada obtuvo **342 PASS / 1 FAIL / 0 SKIP**:
  una aserción ARCA.1 esperaba el antiguo mensaje «disponible en ARCA.2».
  El mensaje ahora informa que producción permanece bloqueada. Se actualizó
  esa regresión y se repitió sólo su archivo: **36 PASS / 0 SKIP**.
- La herramienta opt-in tiene **8 pruebas de guards/HTTP sintético PASS**;
  no es una prueba real de homologación. Durante su desarrollo se corrigió una
  aserción de espacios JSON; también se alineó un test nuevo al contrato
  `409 arca_production_disabled`. Permisos final: **37 PASS**.
  Revalidaciones focalizadas de WSAA/emisión/herramienta: **68 PASS**;
  documentos/emisión/dominio para totales por ambiente: **125 PASS**.
  No se suman estas pasadas porque sus casos se superponen.
- PostgreSQL final: **11 PASS, 0 SKIP**: siete ARCA.2 y cuatro ARCA.1, incluyendo
  dos requests, dos propuestas/serie, respuesta perdida, fence vencido,
  cancelación incompatible, conflicto y un único login WSAA concurrente.
  Cada conexión/thread usó `schema_translate_map` y esquema privado
  `arca2_test_<uuid>`/`arca1_test_<uuid>`, eliminado en finally. Nunca create_all
  sobre public. Verificados esquemas sintéticos restantes: cero.
- Casos de recuperación muestran un único CAE/documento y una sola llamada de
  autorización tras perder la respuesta; reiniciar servicios recupera por
  consulta exacta. Fallar PDF/storage conserva autorización y permite regenerar
  sin otra llamada de emisión. CMS se firma y verifica con certificados generados
  por test; transportes ejecutan XML real y mantienen ledger remoto sintético.
- Tests normales ARCA.2 bloquean sockets/HTTP no inyectados. No incluyen ni
  ejecutan la prueba externa opt-in. Una advertencia existente de multipart no
  afecta los resultados.
- PDF real de tres líneas: **1 página / 37.362 bytes**. Descripción larga:
  **2 páginas / 38.506 bytes**. Ambos renderizados con WeasyPrint, convertidos
  con Poppler e inspeccionados visualmente: márgenes, continuación, total,
  CAE, marca homologación y QR visibles, sin cortes. Pruebas verifican el dibujo
  vectorial del QR, su URL/JSON/Decimal y fallo cerrado ante imagen inválida.
- Frontend: `pnpm exec tsc --noEmit`, lint focalizado y los tres archivos Node
  solicitados PASS. Ejecución directa final ARCA.2: **20 subcasos PASS**,
  incluyendo preparación y validación remota explícita. Comandos abajo.

```sh
# Desde apps/web, dependencias existentes.
pnpm exec tsc --noEmit
node --test src/features/sales/arca2-fiscal.test.cjs \
  src/features/sales/arca1-fiscal.test.cjs src/features/sales/sale-fiscal.test.cjs
node src/features/sales/arca2-fiscal.test.cjs
# pnpm exec next lint --file <ruta>, con --file para cada archivo modificado.
```

NO EJECUTADO: suites completas, build web, migraciones destructivas, emisión o
autenticación real, acceso real a secretos/buckets, homologación real y producción.
No se iniciaron servidores UI/API ni workers.

## Conectar un emisor de homologación cuando lleguen los accesos

Este procedimiento **no fue ejecutado**. Requiere un entorno/tenant de
homologación con datos sintéticos revisados; nunca usar clientes copiados para
emitir. Certificado presente o variables configuradas no disparan una emisión.

1. El contador confirma CUIT/razón fiscal/condición/domicilio, IIBB e inicio de
   actividades o nota contable explícita; tipos C habilitados y uso de Recibo C/
   Factura C. Provisiona homologación WSASS, asociación al servicio `wsfe`,
   delegación si corresponde y POS de Web Services de ese ambiente. El titular
   del certificado puede diferir del CUIT representado. Validar pareja y huella
   offline no prueba delegación ni habilitación fiscal.
2. El operador de servidor custodia certificado, clave y password fuera del
   repositorio, chats, argumentos y logs. Elegir Secret Manager con IAM mínimo
   para versiones concretas, o proveedor local de desarrollo con directorio
   externo montado **readonly**, archivos regulares sin symlinks y modo 0600.
   No montar `.env` ni cuentas productivas. Las rutas no se envían por API.
3. Crear un JSON de registro externo, p. ej. `/run/arca/registry.json`, readonly:

   ```json
   [{
     "reference": "opaque://arca/homologation/emisor-a",
     "tenant_id": "<UUID-del-tenant-de-homologacion>",
     "environment": "homologation",
     "represented_cuits": ["<CUIT-validado>"],
     "auth_scope": "homologation-certificado-a",
     "provider": "local",
     "certificate_resource": "emisor-a.crt",
     "private_key_resource": "emisor-a.key",
     "password_resource": null,
     "expected_fingerprint": "<SHA256-del-certificado-64-hex-minusculas>"
   }]
   ```

   Es un esquema con placeholders, no credenciales utilizables. Para Secret
   Manager cambiar `provider` a `secret_manager` y recursos a
   `projects/<proyecto>/secrets/<nombre>/versions/<version>`, sólo en servidor.
   Compartir certificado exige el mismo `auth_scope`; representados/tenants se
   autorizan explícitamente en el registro. Al rotar, fijar nueva versión/huella;
   no alterar solicitudes fiscales ya congeladas.
4. Provisionar fuera de DB/repositorio `/run/arca/ticket-keyring.json`, modo 0600,
   readonly, con `{"active_version":"v1","keys":{"v1":{"scope":"homologacion-local","key_b64":"<clave-aleatoria-32-bytes-en-Base64>"}}}`.
   Generar 32 bytes con CSPRNG directamente al almacén seguro, sin imprimirlos.
   No derivar la clave de CUIT, tenant o password, ni usar defaults de tests.
   Conservar versiones previas mientras haya TA que deban descifrarse.
5. Configurar únicamente en el proceso/contendor de API de homologación:
   `ARCA_CREDENTIAL_REGISTRY_FILE=/run/arca/registry.json`,
   `ARCA_TICKET_KEYRING_FILE=/run/arca/ticket-keyring.json` y
   `ARCA_HOMOLOGATION_ENABLED=true`. Para proveedor local además:
   `ARCA_LOCAL_CREDENTIALS_ENABLED=true`,
   `ARCA_LOCAL_CREDENTIAL_ROOT=/run/arca/material` con montaje readonly. El
   proveedor local y la emisión externa están desactivados por defecto.
6. En Ajustes, actor fiscal autorizado completa emisor/serie homologación/POS/
   tipo/concepto/CAE, referencia opaca, política y revisión contable. Consulta
   preparación local; luego confirma la validación remota explícita. WSAA debe
   autenticar y los seis parámetros devolver datos reales, incluido POS activo.
   Un catálogo global no demuestra que el CUIT pueda emitir el tipo: confirmar
   su habilitación con el contador y el resultado real de autorización.
7. En una venta sintética confirmada ARS, registrar cobro íntegro y aprobar la
   propuesta ARCA.1. Completar intención de emisión con identidad del emisor,
   receptor/tipo/número/condición IVA, consumidor final explícito cuando aplique,
   fechas, detalle de la porción exacta e importes. Guardar/confirmar intención;
   anotar su UUID y el de la venta. Aprobar no envía.
8. Emitir explícitamente en UI **o** ejecutar la herramienta separada, dentro del
   runtime Docker, contra API local autenticada. Provisionar el bearer del actor
   sin imprimirlo en `ARCA_HOMOLOGATION_API_TOKEN`; habilitar además
   `ARCA_HOMOLOGATION_SMOKE_ENABLED=true` sólo para esa ejecución:

   ```sh
   uv run --frozen --no-sync python -m app.tools.arca_homologation \
     --execute-homologation --confirm-synthetic-data \
     --api-origin http://127.0.0.1:8000 \
     --sale-id <UUID-venta-sintetica> --emission-id <UUID-intencion>
   ```

   Ese origen debe ser la API local accesible desde el contenedor (loopback
   compartido explícitamente si se usa un contenedor de comandos). La herramienta
   exige ambos flags y su variable independiente; sólo admite origen loopback,
   exige autenticación y comprueba homologación. Si ya está incierta consulta
   sin reenviar; si está autorizada descarga el PDF. PASS sólo significa que esa
   ejecución real obtuvo autorización y PDF; no habilita producción. Pendiente/
   rechazo/error no son PASS. No imprimir respuestas completas ni tokens.
9. Ante incertidumbre usar pendientes/conciliar exacto; jamás otra numeración
   para el mismo cobro. Ante conflicto suspender avance y revisar. Ante rechazo
   definitivo corregir en nueva intención auditada. Ante archivo pendiente,
   regenerar el PDF existente. Confirmar CAE, datos y QR reales con el contador.
10. Desactivar flags al terminar y retirar material montado según su custodia.
    Registrar por emisor qué se validó realmente, sin claves/TA en el informe.
    Producción seguirá bloqueada: requiere otro bloque de habilitación, CAEA,
    correcciones fiscales y validación integral ARCA.3.

## Limpieza

Los esquemas sintéticos y sesiones/pools/threads de tests se cierran en finally.
Los certificados, PDFs, PNGs y logs de preparación fueron temporales propios.
Al finalizar se retiran esos artefactos y contenedores etiquetados; el DB vuelve
al estado detenido inicial conservando su contenedor y volumen. La imagen local
incremental contiene sólo dependencias/código base, sin credenciales sintéticas.
