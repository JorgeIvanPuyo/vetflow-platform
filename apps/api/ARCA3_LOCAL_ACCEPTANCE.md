# ARCA.3 — aceptación local

Checks técnicos locales y recorrido de harness aprobados. **Pendiente la
aceptación manual de la aplicación autenticada completa y la homologación
externa por emisor. Producción bloqueada.** Los resultados se conservan por
comando, sin sumar pasadas superpuestas. No hubo ejecución productiva.

Este informe registra el cierre de aceptación previo al commit de integración.
La publicación posterior del avance no amplía la validación ni habilita producción.

## Referencia y alcance

- Rama: `feature/arca1-fiscal-proposals`.
- HEAD de partida: `b3631f20a19faba38ebd8f9c6e7786598a333ced`.
- Al cierre de aceptación, ARCA.1/2 y las correcciones ARCA.3 estaban sin commit. No se publicaron PR,
  commits, push, merge, workflows ni despliegues. El HEAD por sí solo no contiene
  el trabajo probado: se validó el árbol de trabajo actual montado en lectura.
- Alcance conservado: Factura C/Recibo C, CAE, ARS, varios emisores por clínica.
  Producción bloqueada antes de resolver credenciales o crear transporte.
  La prueba externa opt-in permaneció desactivada.

## Correcciones de ARCA.3

1. WSAA vuelve a leer el reloj después de resolver credenciales y adquirir el
   lock. Un TA que venció durante la espera no se devuelve; un certificado que
   venció en ese intervalo impide comenzar otro login.
2. Recuperar un claim WSAA perdido conserva un límite durable que incluye la
   ventana restante del TRA y la vida máxima del TA. El fence impide que el
   worker anterior publique después de ser reemplazado. No hay renovación
   anticipada ni esperas bloqueantes en tests.
3. Algoritmos de clave no soportados producen errores sanitizados. Una prueba
   de timeout CMS verifica cierre de todos los pipes, sin devolver stderr ni
   material privado. Certificados, claves y TA de tests son sintéticos.
4. Las revisiones de archivo y los intentos fiscales son append-only en ORM:
   no se pueden editar ni borrar mediante operaciones ORM ordinarias. No se
   introdujo DDL ni se presenta esto como protección frente a un administrador
   con escritura SQL directa.
5. PDF/QR rechaza CUIT con checksum inválido, importe cero y vencimiento CAE
   anterior al comprobante. No cambió el layout ya inspeccionado en ARCA.2.
6. Si falla una regeneración pero existen versiones persistidas, se conserva
   `file_status=ready`, la descarga y el historial; se registra
   `regeneration_failed_previous_version_retained`. Si todavía no existe un
   archivo, sigue autorizado con archivo pendiente. Ningún fallo reenvía CAE.
7. Se corrigió una fixture frontend antigua que intentaba gestionar emisores
   como secretaria, usando ahora un administrador activo sintético. Los tests
   de secretaria de sólo lectura se mantienen. Se nombró un componente stub
   para que el lint completo cumpla `react/display-name`.
8. El recorrido visual detectó orientación de cancelación en una propuesta ya
   autorizada. Los cobros comprometidos muestran instrucciones según su estado:
   cancelación sólo antes del envío; consulta/conciliación o circuito fiscal
   cuando ya hubo envío, incertidumbre o autorización. No se agregan permisos
   ni acciones de cancelación y se conserva la nota de revisión contable manual.

No se rebajaron permisos, validaciones, guards ni asserts de negocio para
conseguir verde. No se actualizaron dependencias ni se reconstruyeron imágenes.

## Invariantes y aceptación transversal

La revisión se limitó al flujo fiscal/cobros, sus contratos, modelos, migraciones,
pruebas y componentes. Se reutilizó cobertura existente y se añadieron cinco
casos transversales en `app/tests/test_arca3_acceptance.py`, sin sustituir el
orquestador. El doble es un transporte HTTP con ledger por CUIT/POS/tipo/número;
el serializador y el parser SOAP reales siguen ejecutándose.

| Escenario | Evidencia de comportamiento |
| --- | --- |
| Dos tenants y tres emisores; efectivo y transferencias a dos CUIT | Matriz parametrizada `electronic_only`/`all_payments`: libro total 100.00, reserva 66.67 o 100.00; efectivo separado o incluido según política |
| Varios pagos compatibles del mismo emisor | 10.01 + 23.32 se agrupan exactamente; el segundo emisor conserva 33.34; no se prorratea ningún pago |
| Confirmar/reintentar confirmación | Servicio real de checkout y replay idempotente; mismos pagos, reservas y documentos, sin emisión automática |
| CUIT con distintos POS/tipos | Tres series separadas; la selección automática ambigua no elige la primera; la selección explícita conserva POS1/POS2 y tipos 11/15 |
| Other, USD, emisor inactivo, datos incompletos, composición mixta parcial | Bloqueos ARCA.1/2 existentes; no conversión, exención inventada ni atribución automática |
| Reserva exclusiva y cambios posteriores | Pago íntegro, unicidad activa y snapshots congelados; cancelación previa al envío permite otra aprobación, pero su intención anterior no puede emitir |
| Manual sin imputación | Aprobación bloqueada; regularización exacta 33.33 con actor/fecha y replay; emisión del saldo íntegro 66.67 conserva archivo e historial manual |
| Incertidumbre y reinicio | Una consulta SOAP Fault incluso con `retry_same_request=true` no reenvía; la consulta posterior recupera el mismo número/hash/CAE; otros emisores avanzan |
| Rechazo y conflicto | Rechazo exige nueva intención con `supersedes_id`; conflicto conserva reservas y bloquea la serie; no se adopta un CAE ajeno |
| Pagos, reversión y stock | Confirmar/cobrar no emite; anular/revertir frente a reservas o autorización da conflicto; la emisión no agrega movimientos de inventario |
| PDF/storage y versiones | Fallo inicial recuperable, regeneración repetida, versión antigua descargable y fallo posterior que conserva versiones; un solo documento y CAE |
| TA, rotación y concurrencia | AES-GCM con AAD, scopes separados, huella/clave versionadas; renovación de TA expirado única entre procesos y tenants; respuesta tardía fenced |
| Tenant, roles y secretos | Actor activo real; administrador/contador y veterinario propio; secretaria lectura; sin superadmin implícito. IDs/versiones ajenos 404; rutas/URLs de secretos no provienen de HTTP |
| Límite de transacción | El transporte y el storage transversales comprueban que no haya transacción de negocio abierta al comenzar cada llamada |

Los tests ARCA.2/3 bloquean sockets/HTTP no inyectados. La pasada general tiene
además red Docker deshabilitada; las carreras fiscales usan sólo el DB Docker
local verificado y esquemas privados. No se contactaron servicios de negocio.

## Entorno y persistencia

Se verificaron proyecto Compose `api`, servicio/contenedor existente `api-db-1`,
directorio real, red `api_default`, alias `db`, imagen `postgres:17` y volumen
`api_postgres_vetflow_data` antes de conectar. DB inicialmente detenido; se
inició únicamente ese contenedor. Los servicios preexistentes se preservan.

Imagen reutilizada de ARCA.2:
`sha256:bd4537c439fbebea6b4fcb6a32a3beecc7cf7430b2f6902fa78210cca5f0c838`.
Su lockfile interno coincide con el actual y sus dependencias instaladas:
cryptography 49.0.0, defusedxml 0.7.1, Secret Manager 2.31.0, qrcode 8.2,
WeasyPrint 69.0, httpx 0.27.2 y pytest 8.3.3. No se ejecutó sync/install ni build
de imagen. Código/manifests/lockfiles montados en lectura.

Alembic `current` y `heads`: **0058_arca_emission**. No hubo nueva migración ni
upgrade/downgrade/stamp. Revisión antes/después: **0058 → 0058**, confirmada
también en la introspección final. Se registraron conteos y hashes agregados de IDs de las
**49 tablas** con identidad de public, sin exportar filas, snapshots, tickets ni
datos de clientes. Verificación posterior al recorrido: **49 conteos/hashes
idénticos, cero esquemas temporales y ningún fixture en public**.

Todos los comandos usan contenedores `--rm`, `--pull=never` y etiqueta propia
`vetflow.arca3.task=arca3-ac61ad301e8b27136598fbf8`. La URL se deriva del DB
verificado, no de `.env`, y no se imprime. Homologación, smoke y proveedor local
falsos; registro/keyring/token y credenciales Firebase/GCS/IA vacíos.
Se encontraron y vaciaron las cinco variables `*_MIGRATION_DATABASE_URL` del
checkout/imagen: pagos batch/idempotencia, secretary, pricing y receivables.

## Comandos y resultados

El wrapper temporal fue `/tmp/vetflow-arca3-20261021/runtime.cjs`. `general`
fija `DATABASE_URL=sqlite://`, `TEST_DATABASE_URL=` y red `none`. `postgres`
mantiene la conexión de aplicación en SQLite, entrega exclusivamente a sus
fixtures la URL local explícita y usa la red Docker validada. Las variables de
migraciones destructivas permanecen vacías en ambas modalidades.

```sh
node /tmp/vetflow-arca3-20261021/runtime.cjs verify-image
node /tmp/vetflow-arca3-20261021/runtime.cjs run uv run --frozen --no-sync alembic current
node /tmp/vetflow-arca3-20261021/runtime.cjs run uv run --frozen --no-sync alembic heads

# Suite completa, sin filtros de módulos ni -k.
node /tmp/vetflow-arca3-20261021/runtime.cjs general \
  uv run --frozen --no-sync pytest -q -ra -p no:cacheprovider --tb=short

# Sólo carreras fiscales; TODAS sus sesiones/threads usan esquema traducido.
node /tmp/vetflow-arca3-20261021/runtime.cjs postgres \
  uv run --frozen --no-sync pytest -q -ra -p no:cacheprovider --tb=short \
  app/tests/test_arca1_postgresql.py app/tests/test_arca2_postgresql.py \
  app/tests/test_arca3_postgresql.py

# Corrección de regeneración y aceptación transversal.
node /tmp/vetflow-arca3-20261021/runtime.cjs general \
  uv run --frozen --no-sync pytest -q -ra -p no:cacheprovider --tb=short \
  app/tests/test_arca3_acceptance.py app/tests/test_arca2_emission.py
```

| Comando | Resultado |
| --- | --- |
| Imagen/lock/dependencias | PASS, sin reconstrucción |
| Alembic current/heads | PASS, 0058 sin cambios |
| Suite backend completa, primera pasada | **1695 PASS / 0 FAIL / 147 SKIP**, 511.86 s |
| Suite backend completa, confirmación final estable | **1695 PASS / 0 FAIL / 147 SKIP**, 500.11 s; código estable después del fix de regeneración |
| Carreras fiscales PostgreSQL | **13 PASS / 0 SKIP** |
| Aceptación transversal + emisión tras fix de regeneración | **30 PASS / 0 SKIP** |
| Todos los tests frontend Node, final | **28 archivos, 413 PASS / 0 FAIL / 0 SKIP** |
| TypeScript | PASS |
| Lint completo | PASS; archivos afectados tras el último copy, PASS |
| Build web final | PASS con el copy corregido, API loopback y configuración pública sintética |
| Recorrido Chrome desktop/móvil | **8/8 escenarios comprobados**, alcance harness; revalidaciones descritas abajo |
| Git diff --check | PASS |

Las trece carreras incluyen cuatro ARCA.1, siete ARCA.2 y dos ARCA.3 nuevas:
renovación única de TA expirado con rotación de clave, y worker de autenticación
vencido que no publica ni dispara otro login antes de su frontera durable.
Cada fixture crea exclusivamente `arca1_test_<uuid>`, `arca2_test_<uuid>` o
`arca3_test_<uuid>`, con `schema_translate_map`, sesiones/transportes propios,
executors unidos y eliminación del esquema en finally. No se ejecutaron los
tests PostgreSQL históricos que escriben sin ese aislamiento.

Los **147 SKIP reales** de la pasada general se conservan como tales: cinco
pruebas de migración requieren DB vacía dedicada y **142 casos PostgreSQL**
requieren `TEST_DATABASE_URL`. Estos últimos incluyen las trece carreras ARCA
aprobadas separadamente, y 129 casos/colecciones heredadas de cuentas,
receivables, pacientes, clasificación/reportes, compras y cobros/confirmación/
composición transaccional. Parte de los heredados ya usa esquema aislado y parte
usa el esquema por defecto; no se activó su URL global para eliminar skips.
Por tanto, este informe no declara validados esos 129 casos PostgreSQL ni las
cinco migraciones destructivas. Sus variantes SQLite y pruebas estáticas de
cadena se recogieron normalmente donde existen.

Frontend desde `apps/web`, dependencias existentes, descubrimiento NUL-safe:

```sh
node - <<'NODE'
const { execFileSync, spawnSync } = require('node:child_process');
const files = execFileSync('rg', ['--files', '-0', 'src', '-g', '*.test.cjs'], {
  encoding: 'utf8'
}).split('\0').filter(Boolean).sort();
if (!files.length) throw new Error('No se encontraron archivos de prueba frontend');
const result = spawnSync(process.execPath, ['--test', ...files], { stdio: 'inherit' });
if (result.error) throw result.error;
process.exit(result.status ?? 1);
NODE
pnpm exec tsc --noEmit
pnpm run lint
pnpm run build
```

El build fijó `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:18083` y las seis
variables públicas Firebase a valores sintéticos en el entorno del comando;
no se modificó ni mostró `.env.local`. `CIRCLE_NODE_TOTAL=2` limitó los workers
mediante la opción existente de Next, sin cambiar bundler/configuración.
No se conectó Firebase. La primera pasada Node tuvo 410 PASS/1 FAIL por la
fixture antigua; se corrigió y la repetición completa dio 411 PASS. El lint
inicial detectó el stub anónimo; corregido, el lint completo pasó. Tras el hallazgo
visual se añadieron dos regresiones: foco de 50 casos PASS y pasada completa final
**413 PASS**. TypeScript, lint de los archivos afectados y build final también
pasaron. No se suman 410/411/413: son etapas distintas del mismo alcance.

## Recorrido de navegador y alcance real

Recorrido realizado mediante **harness de componentes reales con sesión
sintética**. No se presenta como navegación completa de la aplicación
autenticada con Firebase. La aceptación manual de esa aplicación completa
queda pendiente aunque el recorrido del harness pase.

Se reutiliza Chrome instalado con CDP directo y Node, sin instalar framework ni
navegador. El chromedriver existente resultó ser un launcher Snap sin runtime;
se descartó ese launcher. El harness monta componentes y servicios reales con
React/ReactDOM; sólo sesión/providers de contexto se inyectan en el laboratorio.

API real FastAPI con código actual en `127.0.0.1:18083`; harness en
`127.0.0.1:18084`; depuración Chrome sólo loopback. El bootstrap temporal vive
fuera del checkout y no puede activarse desde una ruta/flag normal del producto.
Sobrescribe dependencias exclusivamente en ese proceso: actor sintético,
factory privada, runtime fiscal con ledger y storage en memoria. Flags de
homologación reales falsos. CORS limitado al origen del harness.

El DB de demo usa únicamente `arca3_ui_<uuid>`, `schema_translate_map` y
`search_path` exclusivo del esquema; el DB por defecto de la aplicación sigue
siendo SQLite. Datos completamente sintéticos, dos tenants y emisores/roles
explícitos. Endpoints de control sólo del bootstrap simulan pérdida de respuesta,
timeout, rechazo y storage fallido; no existen en la API normal.

Se montaron `FiscalConfigurationScreen`, `FiscalIssuersScreen` y
`SaleDetailScreen` reales, en escritorio y viewport móvil **390×844**.
Se inspeccionaron capturas completas y de viewport de mensajes, formularios,
receptor, política, archivo y tabla desplazada.

| Punto de recorrido | Resultado observado |
| --- | --- |
| Ajustes y mapping | Guardar/releer `all_payments`, nota y referencia operativa; snapshots de cobros sin cambios. Administrador/contador gestionan; veterinario/secretaria no pueden editar configuración |
| Mixto | Dos propuestas aprobadas por 30.00/50.00, reserva 80.00 y efectivo 20.00 excluido; cero autorizaciones al revisar/aprobar |
| Doble clic, refresh y respuesta perdida | Una intención y delta de una autorización; se recuperó la operación autorizada persistida después del error de red simulado |
| Incierto | Consulta exacta recuperó el número 1 autorizado; delta de autorizaciones cero |
| Rechazo/conflicto | Rechazo original conservado y nueva intención preparada, dos IDs auditables; conflicto mantuvo estado y bloqueo, cero nuevos envíos |
| Archivo/versiones | Se observó autorizado con archivo fallido; regeneración dejó archivo disponible y tres versiones conservadas; PDF real descargado, CAE/número iguales y delta de autorizaciones cero |
| Tenant/roles | Secretaria sin mutadores; veterinario sólo sus siete series; recursos/archivos ajenos dieron 404 en dos comprobaciones. Contador puede gestionar ajustes |
| Móvil | Página/formularios con scrollWidth=390, sin overflow global; importes y controles legibles. Tabla existente con scroll interno: clientWidth=332, scrollWidth=937 y scrollLeft=605 permite alcanzar la acción «Anular»; importe accesible al inicio |

La primera pasada del runner temporal obtuvo **4 PASS / 4 FAIL**. Sus fallos
fueron de sincronización/inspección: contador leído antes de finalizar el envío,
click de regeneración durante `busy`, serialización de un nodo DOM y detector
que confundía celdas fuera del viewport dentro de una tabla desplazable con
overflow global. Se corrigió sólo el runner para esperar estados durables y
controles habilitados, evaluar booleanos y verificar el desplazamiento real.
Se revalidaron separadamente los puntos 3, 6, 7 y 8 con PASS. La revisión visual
añadió la corrección de orientación de reservas descrita arriba, dos regresiones
Node y nuevas capturas de autorizado/incierto; no se ocultaron fallos del producto.

Red de Chrome: sólo orígenes `127.0.0.1:18083`/`:18084`, **cero peticiones HTTP
externas y cero excepciones JS sin capturar**. Se bloquearon red de fondo,
extensiones/sync/component update, DNS/proxy externos y conexiones mediante CSP
y guard del harness. Consola con eventos esperados: el middleware del laboratorio
devolvió 503 sin CORS para simular pérdida de respuesta, y el navegador lo trató
como error de red; los intentos cross-tenant produjeron 404. Se conservaron como
eventos deliberados, no como una consola «sin ningún error».

El ledger final de laboratorio acumuló ocho llamadas de autorización, siete
documentos remotos y nueve versiones de archivo, incluyendo fixtures de rechazo/
incertidumbre y revalidaciones. Esos totales no representan ocho emisiones del
mismo cobro: cada escenario comprobó sus deltas e identidad persistida.

## Homologación y bloqueos productivos

No se ejecutó WSAA/WSFE real, Secret Manager, Firebase, IA, bucket, herramienta
opt-in, conectividad productiva ni comando remoto. No se repitió investigación
normativa ni se ampliaron tipos fiscales. Para conectar un emisor cuando lleguen
accesos, usar el procedimiento existente de [ARCA2.md](ARCA2.md#conectar-un-emisor-de-homologación-cuando-lleguen-los-accesos):
registro de servidor, material seguro readonly/Secret Manager, keyring externo,
serie de homologación, validación remota explícita y venta sintética revisada.

Pendientes **por cada emisor**: certificado/clave bajo custodia segura, delegación
o autorización WSASS al servicio `wsfe`, POS Web Services del ambiente, CUIT y
datos fiscales completos, habilitación efectiva del tipo y revisión contable de
política/cobros/efectivo. Un catálogo o un certificado local válido no sustituye
esa validación real.

Bloqueos de salida productiva conservados: homologación real por emisor,
contingencia CAEA completa, circuito fiscal de corrección/notas de crédito,
tratamiento de devoluciones y autorización explícita de habilitación. No se
implementaron ni simularon como un ajuste de hardening.

## Preparación de integración y despliegue — sólo documental

1. Publicar el avance en la feature mediante un commit autorizado y revisar su
   futura integración. No desplegar el HEAD de partida como si incluyera estos cambios.
2. Provisionar identidad de servicio e IAM mínimos para las versiones concretas
   de secretos del ambiente; keyring AES-GCM externo con versiones retenidas.
   Separar homologación/producción y tenants/representados en el registro.
   Conservar flags de emisión/smoke/proveedor local desactivados inicialmente.
3. Verificar head del destino sólo durante una futura ejecución autorizada.
   Orden previsto: migración incremental revisada → API de esta revisión → web
   coordinada. ARCA.3 no añade revisión y no autoriza aplicar 0055–0058 otra vez.
   La copia local ya está en 0058.
4. No asumir compatibilidad de una API antigua con el esquema/datos nuevos.
   El código de HEAD `b3631f2` elige el primer documento activo y considera eso
   cobertura fiscal; con documentos ARCA/homologación podría seleccionar el
   documento equivocado. Además las migraciones separan namespaces y el singular
   manual. No se ensayó un despliegue mixto de versiones ni se certifica rollback
   a esa API antigua.
5. Recuperación operativa: desactivar envíos, conservar DB/claims/reservas y
   solicitudes congeladas; desplegar una API compatible/fix forward, listar
   pendientes y conciliar el número exacto con actor autorizado. Regenerar el
   archivo después del CAE si falta. Nunca borrar autorizaciones, restaurar la
   DB ni usar downgrade para recuperar una emisión incierta. Ensayar este
   procedimiento operativo con accesos reales de homologación antes de habilitar
   cualquier ambiente productivo.

### Borrador de futura PR a develop — no publicada

**Título:** Incorporar revisión fiscal y emisión CAE recuperable por emisor.

**Descripción:** Las ventas confirmadas ARS pueden revisar y reservar cobros
íntegros por emisor/serie y confirmar una intención fiscal explícita. La emisión
guarda número y solicitud antes de enviar; los resultados inciertos se recuperan
por consulta exacta, conservando reservas. WSAA usa credenciales referenciadas y
TA cifrado; autorización y PDF/QR versionado se recuperan por separado.

Se preserva el adjunto manual singular y se agregan documentos/totales por
ambiente. Homologación no computa como cobertura productiva; roles/tenants y
producción permanecen protegidos. Validación local: pytest general 1695 PASS/
147 SKIP; carreras ARCA PostgreSQL 13 PASS/0 SKIP; Node 413 PASS; TypeScript,
lint y build PASS; Chrome desktop/móvil, ocho puntos de harness comprobados.
La aplicación autenticada completa requiere aceptación manual. Homologación
real, CAEA, correcciones fiscales y habilitación productiva siguen pendientes.

## Limpieza

Limpieza verificada: Chrome y harness cerrados por sus procesos identificados;
API de laboratorio y contenedores etiquetados propios retirados. **Cero
contenedores ARCA.3 activos/restantes**. El DB existente volvió a su estado
**detenido inicial**, conservando contenedor, red y volumen. No se detuvieron
servicios ajenos.

Se registraron los esquemas propios para limpieza explícita incluso cuando el
supervisor uv no reenvió la señal al proceso Python. Tanto el esquema de la
recarga como el final fueron retirados. Verificación PostgreSQL posterior:
**cero esquemas temporales**, public sin fixtures y 49 conteos/hashes históricos
idénticos. Las sesiones/conexiones/pools/threads de pruebas se cerraron; al
terminar el proceso de la API se cerraron sus conexiones antes de retirar su
esquema.

Se retiraron sólo los perfiles, harness, scripts, metadata, logs, capturas y PDFs
temporales propios. Los certificados sintéticos vivieron en los contenedores de
tests eliminados. Ningún material privado ni artefacto de laboratorio se añadió
al repositorio. La imagen de dependencias ARCA.2 preexistente se conservó.
