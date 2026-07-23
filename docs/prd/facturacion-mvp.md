# PRD — Módulo de Facturación de Vetflow (MVP)

> **Nota de este documento.** Producto entregó un PRD inicial (Argentina-first, con ARCA). Este PRD lo reelabora **cruzándolo con el estado real del código de Vetflow**: marca qué ya existe y se reutiliza, qué es net-new, y qué gaps o deuda técnica hay que asumir. Las secciones conservan la numeración del PRD de producto (RF, HU, roadmap) para trazabilidad. Los bloques **"Estado actual / Gap"** son el aporte de ingeniería.

---

## 1. Información general

- **Producto:** Vetflow — app web multi-tenant de gestión clínica veterinaria (monorepo `apps/api` FastAPI + `apps/web` Next.js 14).
- **Módulo:** Facturación y control financiero.
- **Mercado inicial:** Argentina (ARS, facturación electrónica ARCA).
- **Expansión futura:** Colombia y Panamá (fuera de alcance de este MVP).
- **Multi-tenant:** tenant = clínica. Es la única unidad organizativa (no hay sedes).

### Decisiones de alcance ya tomadas (con el equipo)

1. **ARCA se incluye dentro del MVP** (no en una fase posterior), asumiendo que es la pieza más riesgosa y 100% greenfield.
2. **Se crea un catálogo de Servicios** con precio + IVA, reutilizable por venta, además de permitir conceptos manuales.
3. **No se crean roles nuevos.** El rol existente `medico_veterinario` actúa como administrador de la clínica (acceso total a facturación). `contador` consulta/reportes/fiscal. `superadmin` es plataforma. **No** se implementa un sistema de permisos granular (`sales.create`, etc.) en el MVP.
4. **Moneda: ARS hardcodeado** en todo el módulo, consistente con el inventario actual (`inventory_items._ars`). Multi-moneda queda fuera de alcance.

---

## 2. Contexto

Vetflow hoy gestiona (módulos reales verificados en código): propietarios (`owners`), pacientes (`patients`), citas (`appointments`), consultas (`consultations` con pasos de workflow), exámenes (`exams`), inventario (`inventory_items` + `inventory_movements`), seguimientos (`follow_ups`), cuidado preventivo (`patient_preventive_care`), archivos clínicos en GCS (`patient_file_references`), clínica/branding (`tenants`), dashboard operativo, búsqueda global, IA (resúmenes clínicos) y administración de usuarios cross-tenant (`admin`).

Se requiere agregar un módulo que registre las operaciones económicas de cada clínica: venta de consultas, procedimientos y productos; registro de pagos; identificación del profesional que generó el ingreso y del usuario que recibió el dinero; registro de compras y gastos; visualización de ingresos, gastos y utilidad estimada; y emisión de comprobantes electrónicos en Argentina (ARCA).

### Estado actual / Gap (resumen)

- **Lo único monetario que existe hoy vive en inventario.** `inventory_items` tiene `purchase_price_ars`, `sale_price_ars`, `purchase_tax_rate_percentage` (IVA compra), `sale_tax_rate_percentage` (IVA venta), `profit_margin_percentage` (default 35%) y `round_sale_price`. `inventory_movements` guarda `unit_cost_ars`/`total_cost_ars` (entradas) y `unit_sale_price_ars`/`total_sale_price_ars` (salidas). La salida con `reason='sale'` **ya decrementa stock** y captura precio de venta.
- **No existe** ningún modelo de venta, orden, factura, pago, gasto, servicio ni documento fiscal.
- **No existe** identidad fiscal ni de la clínica ni del cliente.
- El módulo `/accounting` (Contabilidad) existe como **placeholder "En construcción"** en el front (`features/accounting/components/accounting-screen.tsx`), gateado a `contador`/`superadmin`, sin backend.

---

## 3. Objetivo del producto

Permitir que cada clínica controle sus ventas, pagos y gastos desde Vetflow, obtenga información básica del desempeño financiero y cumpla con los requerimientos iniciales de facturación electrónica en Argentina, sin pretender reemplazar (todavía) un sistema contable completo.

---

## 4. Objetivos del MVP

El MVP debe permitir:

1. Registrar ventas de productos y servicios.
2. Asociar una venta con propietario y paciente.
3. Identificar al profesional que realizó cada servicio.
4. Registrar quién recibió el dinero.
5. Registrar uno o varios medios de pago.
6. Registrar compras y gastos.
7. Consultar ventas y gastos por rango de fechas.
8. Consultar ingresos generados por profesional.
9. Consultar dinero recibido por usuario.
10. Visualizar indicadores financieros básicos.
11. Emitir comprobantes electrónicos mediante ARCA.
12. Mantener aislamiento estricto de información entre tenants.

---

## 5. Fuera del alcance del MVP

No se incluirá inicialmente:

- Contabilidad de doble partida y plan de cuentas tributario.
- Conciliación bancaria e integración directa con bancos.
- Cuentas por pagar avanzadas y gestión de comisiones.
- Proyecciones financieras y cálculo contable preciso del costo de venta.
- Facturación electrónica para Colombia y Panamá.
- **Multi-sede / sucursales** (Vetflow no modela sedes; el tenant es la única unidad org).
- **Múltiples monedas** (todo en ARS; ver §11 y Apéndice B).
- **Sistema de permisos granular** por acción (`sales.create`, etc.) y **rol "administrador" separado** (se usa `medico_veterinario`; ver §6).

---

## 6. Usuarios y permisos

### Decisión de roles (MVP)

Vetflow tiene hoy **3 roles** en `users.role` (`apps/api/app/core/roles.py`): `superadmin`, `medico_veterinario` (default) y `contador`. **No se agregan roles nuevos.** El PRD de producto proponía admin/veterinario/contador + permisos granulares; para el MVP se mapea así:

| Rol producto                | Rol Vetflow (MVP)        | Acceso en facturación                                                                                                                                                |
| --------------------------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Administrador + Veterinario | **`medico_veterinario`** | Acceso total: crear ventas, registrar pagos, anular (con motivo), registrar gastos, ver reportes/indicadores, configurar datos fiscales, descargar comprobantes.     |
| Contador                    | **`contador`**           | Consultar ventas, gastos y documentos fiscales; descargar reportes; revisar impuestos; ver comprobantes emitidos/rechazados. Solo lectura (no crea ventas ni pagos). |
| (plataforma)                | **`superadmin`**         | Administración cross-tenant de usuarios (sin cambios).                                                                                                               |

### Estado actual / Gap (importante)

- Hoy **solo `superadmin` se valida en el backend** (`require_superadmin` en `core/tenant.py`, usado solo en `api/admin_users.py`). La diferencia entre `medico_veterinario` y `contador` es **puramente de navegación en el front** (`components/layout/navigation-items.ts::filterNavigationByRole`); a nivel API no hay restricción.
- Por lo tanto, **el enforcement por rol en el backend para el módulo de facturación es net-new.** Se debe crear una dependencia tipo `require_role([...])` (siguiendo el patrón de `require_superadmin`) y aplicarla a los endpoints de escritura (ventas, pagos, gastos, config fiscal), manteniendo lectura para `contador`.
- Los permisos granulares (`sales.create`, `payments.register`, `fiscal_configuration.manage`, etc.) del PRD de producto quedan como **visión futura**, no MVP. Se documentan en el Apéndice A.
- El `contador` reemplaza su placeholder actual `/accounting` por el dashboard/reportes financieros reales.

---

## 7. Conceptos principales

El sistema distingue tres responsabilidades que pueden ser personas distintas:

- **Profesional responsable** — quien realizó el servicio → `SaleItem.performed_by_user_id`. Se alinea con el `attending_user_id` que ya existe en `consultations`.
- **Usuario que recibió el pago** → `Payment.received_by_user_id` (obligatorio).
- **Usuario que creó la venta** → `Sale.created_by_user_id`.

> Ejemplo: Servicio realizado por Vet. Ana · Venta registrada por Admin Juan · Pago recibido por Vet. Ana · Medio: QR · Total: $25.000.

### Estado actual / Gap

La infraestructura de trazabilidad ya existe: casi todas las tablas llevan `created_by_user_id`, y el front resuelve nombres con `lib/user-traceability.ts`. `performed_by_user_id` y `received_by_user_id` son campos nuevos que siguen el mismo patrón.

---

## 8. Requerimientos funcionales

### RF-01. Crear una venta

Desde una única pantalla. La venta puede asociarse opcionalmente con propietario, paciente y cita (no con sede — no existe). Contiene: fecha, moneda (ARS, implícita), conceptos, cantidades, precios, descuentos, impuestos, total, usuario creador, estado.

**Criterios de aceptación**

- Puede agregar uno o varios conceptos.
- El total se calcula automáticamente.
- No se confirma una venta sin conceptos.
- No se permiten cantidades ≤ 0.
- El precio unitario puede editarse (en MVP, cualquier `medico_veterinario`; ver §6, el permiso fino queda fuera de alcance).
- La venta pertenece únicamente al tenant activo.

**Estado actual / Gap:** net-new completo (`sales`). La moneda no se almacena como columna: es ARS implícito (coherente con inventario). Reutiliza envoltura `{data, meta}` y `AppError`.

---

### RF-02. Agregar productos y servicios (líneas de venta)

Una venta puede incluir: consulta, procedimiento, vacuna, medicamento, producto, servicio adicional o concepto manual. Cada línea registra: tipo de concepto, descripción, cantidad, precio unitario, descuento, impuesto, total, profesional responsable (si aplica) y paciente (si aplica).

**Criterios de aceptación**

- Los servicios pueden tener profesional responsable; los productos no lo requieren.
- Un servicio puede asociarse a un paciente.
- El sistema **conserva nombre y precio del momento de la venta (snapshot)** aunque luego cambie el catálogo.

**Estado actual / Gap (clave):**

- **No existe catálogo de servicios.** Hoy solo los `inventory_items` (bienes físicos) tienen precio. Consultas, exámenes y procedimientos **no tienen precio**. → **Se crea el modelo `services`** (catálogo con `default_price_ars` + `sale_tax_rate_percentage`).
- `sale_items` referencia **`service_id`** (catálogo de servicios) **o** **`product_id`** (un `inventory_items`) **o** un **concepto manual** (solo `description` + precio). Guarda snapshot de `description` y `unit_price_ars`.
- **Reconciliación con inventario:** si la línea es un producto, la venta debe generar/consumir la salida de stock existente (`inventory_movements` con `reason='sale'`) para no duplicar el descuento de stock. Cuidado especial con `consultation_medications`, que **ya** generan salidas al dispensar en consulta: una venta que facture esos medicamentos no debe volver a descontar stock (debe vincularse al movimiento ya creado).

---

### RF-03. Registrar pagos

Durante o después de la venta. Medios: efectivo, transferencia, QR, tarjeta débito, tarjeta crédito, otro. Cada pago registra: medio, valor, usuario que recibió, fecha/hora, referencia opcional, observación opcional.

**Criterios de aceptación**

- Una venta puede tener uno o varios pagos.
- La suma de pagos no puede superar el total.
- El usuario receptor es obligatorio; el medio es obligatorio; la referencia es opcional.
- El sistema identifica cuánto entró por cada medio.

**Estado actual / Gap:** net-new (`payments`). `received_by_user_id` FK a `users`. `paid_total_ars` en `sales` se recalcula al registrar/anular pagos.

---

### RF-04. Estados de la venta

`DRAFT`, `PENDING_PAYMENT`, `PARTIALLY_PAID`, `PAID`, `CANCELLED`.

**Reglas**

- `DRAFT`: editable.
- `PENDING_PAYMENT`: confirmada, sin pagos.
- `PARTIALLY_PAID`: pagos < total.
- `PAID`: pagos = total.
- `CANCELLED`: anulada.
- El estado se actualiza automáticamente según los pagos.
- Una venta pagada no se edita directamente.
- Una venta anulada permanece para auditoría; anular requiere motivo; solo `medico_veterinario` puede anular.

**Estado actual / Gap:** net-new. La anulación escribe en `audit_logs` (§12).

---

### RF-05. Consultar historial de ventas

Filtros: rango de fechas, estado, propietario, paciente, profesional responsable, usuario receptor, medio de pago, número de venta, número de comprobante fiscal. Cada resultado muestra: fecha, número, cliente, paciente, total, total pagado, estado, estado fiscal.

**Estado actual / Gap:** net-new. Reutiliza paginación `ListMeta` (`schemas/common.py`) y el patrón de filtros por query params (como `services/inventory.ts`).

---

### RF-06. Registrar compras y gastos

Categorías iniciales (revisar términos para Argentina): compra de medicamentos, compra de productos, insumos médicos, alquiler, servicios públicos, sueldos, publicidad, mantenimiento, impuestos, comisiones bancarias, otros. Cada gasto registra: fecha, descripción, categoría, proveedor opcional, valor, medio de pago, usuario que registró, archivo adjunto opcional, observaciones.

**Criterios de aceptación**

- Valor > 0; categoría obligatoria.
- Filtrable por fecha y categoría.
- Asociado al tenant activo.
- El MVP no genera asientos contables.

**Estado actual / Gap:** net-new (`expense_categories` + `expenses`). El **adjunto reutiliza GCS** (`ClinicalFileStorageService` en `services/storage.py`) con nuevo prefijo `tenants/{tenant_id}/expenses/...`. El PRD de producto usaba términos colombianos ("arriendo", "nómina"); se ajustan a AR ("alquiler", "sueldos") en el seed.

---

### RF-07. Dashboard financiero

Selector de rango de fechas. Indicadores: total vendido, total cobrado, total pendiente, total de gastos, utilidad estimada, número de ventas, número de consultas, ticket promedio, ventas por profesional, dinero recibido por usuario, ventas por medio de pago, productos/servicios más vendidos.

**Fórmulas**

```
Total vendido    = Σ ventas confirmadas no anuladas
Total cobrado    = Σ pagos válidos
Total pendiente  = Total vendido − Total cobrado
Utilidad estimada= Total vendido − Total de gastos
Ticket promedio  = Total vendido / número de ventas
```

Se llama **utilidad estimada** porque el MVP no considera costos contables, inventario, depreciaciones ni retenciones.

**Estado actual / Gap:** net-new financiero (distinto del `dashboard/summary` operativo existente). **Reemplaza el placeholder `/accounting`.** Reutiliza el formatter ARS existente (`features/inventory/components/inventory-helpers.tsx::formatInventoryCurrency`), que conviene promover a un util compartido en `lib/`.

---

### RF-08. Reporte por profesional

Campos: profesional, número de consultas, número de procedimientos, cantidad de servicios, total generado.
**Regla:** el ingreso se atribuye al `performed_by_user_id` de cada línea de servicio, no al creador de la venta ni al receptor del pago.

**Estado actual / Gap:** net-new; agregación sobre `sale_items`.

---

### RF-09. Reporte por usuario receptor

Campos: usuario, efectivo, transferencias, QR, débito, crédito, otros, total recibido.
**Regla:** usa el `received_by_user_id` de cada pago.

**Estado actual / Gap:** net-new; agregación sobre `payments`.

---

### RF-10. Reporte por medio de pago

Agrupa pagos por: efectivo, transferencia, QR, débito, crédito, otros. Filtrable por rango de fechas, usuario receptor y estado de la venta. (Sede: N/A — no existe.)

**Estado actual / Gap:** net-new; agregación sobre `payments`.

---

## 9. Facturación electrónica en Argentina (ARCA)

> **Riesgo técnico — leer.** Esta es la parte **más grande y 100% greenfield** del MVP. Hoy Vetflow **no tiene nada** de la infraestructura necesaria: las integraciones externas actuales son REST vía `httpx` (IA) y SDKs (Firebase, GCS). No hay SOAP, XML, `zeep`, `lxml`, ni manejo de certificados X.509 / firma CMS/PKCS#7. ARCA (ex-AFIP) requiere autenticación WSAA (login ticket firmado con certificado X.509, válido ~12 h) y el Web Service de Factura Electrónica **WSFE**. Se recomienda encapsular todo en `services/arca_service.py` siguiendo el patrón de `services/ai_service.py` (error propio → mapeo a respuesta, sanitización de secretos, logging estructurado) y gatear con un flag `ARCA_ENABLED` (patrón `AI_FEATURES_ENABLED`). Dependencias nuevas previstas: `zeep`/`lxml` (SOAP), `cryptography`/`signxml` (firma). Se deben actualizar **`pyproject.toml` y `requirements.txt`** (este último para el Dockerfile/Cloud Run).

### RF-11. Configuración fiscal del tenant

El administrador (`medico_veterinario`) configura: razón social, nombre comercial, CUIT, domicilio fiscal, condición frente al IVA, ingresos brutos (si aplica), inicio de actividades, punto de venta, ambiente (homologación/producción), certificado digital y clave privada asociada, tipos de comprobante habilitados.

**Estado actual / Gap:** net-new (`fiscal_configurations`, 1:1 con tenant). **El `tenants` actual no tiene ningún dato fiscal** (solo branding + contacto). Certificado y clave privada deben **almacenarse cifrados** (no exponer nunca en respuestas API).

### RF-12. Emitir comprobante electrónico

Flujo:

```
1. Confirmar venta.
2. Validar configuración fiscal.
3. Determinar tipo de comprobante (depende de la condición IVA del emisor y del cliente).
4. Autenticar vía WSAA (reusar ticket cacheado si sigue vigente).
5. Enviar solicitud al WSFE.
6. Recibir autorización (CAE) o rechazo.
7. Guardar request/response completos.
8. Generar representación visual (PDF + QR).
```

Se almacena la respuesta de ARCA incluyendo el **CAE** cuando se aprueba.

**Estado actual / Gap:** net-new. La determinación del tipo de comprobante (A/B/C) exige la **condición IVA del cliente** → ver extensión de `owners` en §11. La emisión debe ser **desacoplada**: si ARCA tarda o falla, la venta ya quedó registrada (no bloquear).

### RF-13. Estados fiscales

`NOT_REQUIRED`, `PENDING`, `PROCESSING`, `AUTHORIZED`, `REJECTED`, `CANCELLED`.

**Reglas**

- Una venta puede existir aunque la emisión fiscal falle.
- Un rechazo muestra el error recibido (traducido a mensaje comprensible).
- Un usuario autorizado puede reintentar.
- Una factura autorizada no se elimina.
- Request/response de ARCA se conservan para auditoría.
- **La venta y el documento fiscal tienen identificadores distintos** (`sales.id` ≠ `fiscal_documents.id`).

**Estado actual / Gap:** net-new. Reintentos **idempotentes** (no generar CAE duplicado).

### RF-14. Comprobante descargable

Cuando está autorizado: visualizar, descargar PDF, imprimir, enviar por correo (posterior). Debe mostrar: datos emisor, datos receptor, fecha, tipo y número, punto de venta, detalle, impuestos, total, CAE, vencimiento del CAE, QR fiscal.

**Estado actual / Gap:** net-new, pero **reutiliza el pipeline de PDF existente**: WeasyPrint + Jinja2 (patrón `services/clinical_history_pdf.py` + template en `app/templates/`). El QR y el logo deben inyectarse **inline como `data:` URI** (el `PdfAssetURLFetcher` bloquea URLs externas). El front usa `api.postBlob` + `downloadBlob` (patrón `services/clinical-history-export.ts` / `patient-detail.tsx`). El PDF puede persistirse en GCS (`ClinicalFileStorageService`, prefijo `tenants/{id}/fiscal/...`).

---

## 10. Experiencia de usuario

### 10.1 Pantallas del MVP

- **Nueva venta** (una sola pantalla): seleccionar propietario/paciente → agregar productos/servicios → asignar profesionales → ver total → registrar pagos → confirmar → emitir comprobante.
- **Historial de ventas**: buscar, filtrar, ver detalle, ver pagos, ver estado fiscal, descargar comprobantes, anular cuando esté permitido.
- **Compras y gastos**: crear gasto, adjuntar soporte, historial, filtrar por fecha/categoría.
- **Dashboard financiero**: indicadores, distribución por medios de pago, rendimiento por profesional, ingresos y gastos por período. **Reemplaza `/accounting` (placeholder actual).**
- **Configuración fiscal**: completar datos fiscales, configurar punto de venta, cargar certificado y clave, seleccionar ambiente (prueba/producción), probar conexión.

### 10.2 Principios de usabilidad

- Flujo de venta en una sola pantalla; campos fiscales avanzados ocultos durante una venta normal; cálculos automáticos; errores de ARCA traducidos a mensajes comprensibles; se puede guardar la venta aunque ARCA no responda; filtros frecuentes siempre visibles; mínima escritura manual.

**Estado actual / Gap:** el front sigue rebanadas verticales (`app/<ruta>/page.tsx` → `features/<modulo>/components` → `services/<modulo>.ts` → `lib/api.ts`). Nuevas rutas: `/sales` (+ `/sales/new`, `/sales/[id]`), `/expenses`, y el dashboard financiero (dentro de `/accounting`). Config fiscal dentro de `/settings`.

---

## 11. Modelo de datos inicial

Todas las tablas nuevas heredan `BaseModel` (`id` UUID, `created_at`, `updated_at`) y llevan `tenant_id` (FK, indexado, NOT NULL). Todos los montos en ARS (sin columna de moneda, coherente con inventario). Migración Alembic nueva `alembic/versions/0025_*.py` (la cadena actual llega a `0024_*`).

### Entidades nuevas

**`services`** (catálogo de servicios — net-new)

```
id, tenant_id, name, description?, default_price_ars,
sale_tax_rate_percentage (default 0), is_active, created_by_user_id
```

**`sales`**

```
id, tenant_id, owner_id?, patient_id?, appointment_id?,
status (DRAFT|PENDING_PAYMENT|PARTIALLY_PAID|PAID|CANCELLED),
subtotal_ars, discount_total_ars, tax_total_ars, total_ars, paid_total_ars,
sale_number, cancellation_reason?, created_by_user_id, created_at, updated_at
```

**`sale_items`**

```
id, tenant_id, sale_id,
item_type (consultation|procedure|vaccine|medication|product|service|manual),
service_id?, product_id?(inventory_items), consultation_id?, patient_id?,
performed_by_user_id?,
description (snapshot), quantity, unit_price_ars (snapshot),
discount_ars, tax_ars, total_ars,
inventory_movement_id?  -- vínculo a la salida de stock, evita doble descuento
```

**`payments`**

```
id, tenant_id, sale_id, received_by_user_id,
payment_method (cash|transfer|qr|debit|credit|other),
amount_ars, reference?, notes?, paid_at, created_at
```

**`expense_categories`** (seed inicial, términos AR)

```
id, tenant_id?, name, is_system
```

**`expenses`**

```
id, tenant_id, category_id, supplier_name?, description,
amount_ars, payment_method, expense_date, created_by_user_id,
attachment_bucket_name?, attachment_object_path?, notes?, created_at
```

**`fiscal_configurations`** (1:1 con tenant)

```
id, tenant_id, razon_social, nombre_comercial?, cuit, domicilio_fiscal,
condicion_iva, ingresos_brutos?, inicio_actividades,
punto_de_venta, ambiente (homologacion|produccion),
certificate_encrypted, private_key_encrypted, tipos_comprobante_habilitados (JSON)
```

**`fiscal_documents`** (id ≠ sale.id)

```
id, tenant_id, sale_id, country='AR', document_type, point_of_sale,
document_number?, status (NOT_REQUIRED|PENDING|PROCESSING|AUTHORIZED|REJECTED|CANCELLED),
cae?, cae_expiration?, request_payload, response_payload, error_message?,
issued_at?, created_at
```

**`audit_logs`**

```
id, tenant_id, user_id, action, entity_type, entity_id,
before? (JSON), after? (JSON), reason?, created_at
```

### Extensiones a tablas existentes

**`owners`** (agregar identidad fiscal, hoy solo hay `document_id` genérico):

```
+ tax_id_type?   (DNI|CUIT|CUIL|...)
+ tax_id?
+ iva_condition? (Responsable Inscripto|Monotributo|Consumidor Final|Exento|...)
```

### Regla multi-tenant (invariante)

**Toda** consulta, comando y reporte filtra obligatoriamente por `tenant_id` (patrón `core/tenant.py::get_tenant_context`). Ningún usuario puede consultar ni modificar información de otro tenant. La auditoría cubre ventas, pagos, anulaciones y documentos fiscales.

---

## 12. Requerimientos no funcionales

**Seguridad**

- Autorización por rol (net-new en backend; ver §6), validada **también en backend**, no solo en UI.
- Aislamiento estricto por tenant.
- **Cifrado de certificados y claves privadas** fiscales.
- Auditoría de ventas, pagos, anulaciones y documentos fiscales (`audit_logs`).
- No exponer respuestas técnicas completas de ARCA al usuario final (sanitizar, patrón `ai_service.py::_sanitize_provider_message`).

**Rendimiento**

- Crear una venta responde en < 2 s (sin contar ARCA).
- Reportes mensuales < 3 s para volumen normal.
- Emisión fiscal desacoplada cuando la respuesta externa tarde.

**Disponibilidad**

- Una falla de ARCA no impide registrar la venta.
- Documentos pendientes reintentables; reintentos **sin comprobantes duplicados** (idempotencia por venta/punto de venta).

**Auditoría** — registrar: usuario, acción, fecha/hora, entidad afectada, valor anterior, valor nuevo, motivo de anulación, request/response fiscal.

---

## 13. Historias de usuario principales

- **HU-01.** Como `medico_veterinario`, quiero registrar productos y servicios vendidos para controlar los ingresos.
- **HU-02.** Como usuario, quiero asignar el profesional que realizó cada servicio para conocer el ingreso que generó.
- **HU-03.** Como usuario autorizado, quiero registrar medio de pago y receptor para trazar el recaudo.
- **HU-04.** Como `medico_veterinario`, quiero registrar compras y gastos para conocer los egresos.
- **HU-05.** Como `medico_veterinario`, quiero ver ingresos, gastos y utilidad estimada por período.
- **HU-06.** Como `medico_veterinario`, quiero conocer consultas/procedimientos por profesional y su valor total.
- **HU-07.** Como `medico_veterinario`, quiero emitir un comprobante electrónico para documentar la venta.
- **HU-08.** Como `medico_veterinario` o `contador`, quiero revisar y reintentar documentos rechazados sin perder la venta.
- **HU-09.** Como usuario autorizado, quiero descargar el comprobante fiscal para entregarlo al cliente.

---

## 14. Métricas de éxito (primeros 3 meses)

% de ventas registradas en Vetflow · tiempo promedio de creación de venta · % de ventas con profesional asignado · % de pagos con receptor identificado · % de comprobantes autorizados · nº de comprobantes rechazados · nº de gastos registrados · usuarios activos del módulo · uso del dashboard · diferencia entre ventas y pagos registrados.

**Objetivos iniciales:** venta creada en < 2 min · > 90 % de ventas con medio de pago · > 95 % de servicios con profesional · > 95 % de comprobantes autorizados sin intervención manual · **cero accesos cross-tenant**.

---

## 15. Roadmap recomendado

Aunque **todo es MVP**, el orden de construcción entrega valor antes de asumir el riesgo de ARCA:

- **Fase 1 — Operación comercial:** catálogo de servicios, ventas, líneas (producto/servicio/manual) con reconciliación de inventario, pagos, receptor, historial de ventas.
- **Fase 2 — Control financiero:** compras y gastos, dashboard financiero (reemplaza `/accounting`), reportes por profesional / por receptor / por medio de pago.
- **Fase 3 — Facturación electrónica Argentina:** config fiscal + cifrado, WSAA, WSFE, comprobantes, estados fiscales, PDF + QR, reintentos idempotentes, `ARCA_ENABLED`.
- **Fase 4 — Post-MVP:** notas de crédito, devoluciones, cierre de caja, costo de inventario, comisiones, conciliación, adaptadores fiscales CO/PA, permisos granulares (Apéndice A).

---

## 16. Criterio de finalización del MVP

Completo cuando una clínica pueda: (1) registrar una venta de productos y servicios; (2) asociarla a un paciente; (3) identificar al profesional; (4) registrar el receptor del dinero; (5) registrar uno o varios medios de pago; (6) registrar compras y gastos; (7) consultar ingresos, gastos y utilidad estimada; (8) consultar resultados por profesional y por receptor; (9) emitir un comprobante autorizado por ARCA; (10) descargarlo; (11) consultar y reintentar documentos rechazados; (12) operar **sin acceder a datos de otros tenants**.

---

## Apéndice A — Gaps y deuda técnica detectada

Resumen de lo que Vetflow **no tenía** y este PRD introduce o difiere:

| Gap                                   | Estado                                    | Tratamiento en el MVP                                                      |
| ------------------------------------- | ----------------------------------------- | -------------------------------------------------------------------------- |
| Catálogo de servicios con precio      | No existía (solo inventario tenía precio) | **Net-new** `services`                                                     |
| Venta / línea / pago                  | No existía                                | **Net-new** `sales`/`sale_items`/`payments`                                |
| Identidad fiscal del tenant           | `tenants` sin datos fiscales              | **Net-new** `fiscal_configurations` (cifrado)                              |
| Identidad fiscal del cliente          | `owners` solo `document_id`               | **Extensión** `owners` (tax_id, condición IVA)                             |
| Enforcement de roles en backend       | Solo `superadmin` se valida hoy           | **Net-new** `require_role`; `medico_veterinario`=admin, `contador`=lectura |
| Permisos granulares (`sales.create`…) | No existían                               | **Diferido** (post-MVP)                                                    |
| Rol "administrador" separado          | No existe                                 | **No se crea**; usa `medico_veterinario`                                   |
| Multi-sede                            | No existe                                 | **Fuera de alcance**                                                       |
| Multi-moneda                          | Inventario hardcodea ARS; timezone Panama | **ARS hardcodeado**; deuda para expansión CO/PA                            |
| ARCA (WSAA/WSFE, X.509, CMS, CAE)     | Cero infraestructura                      | **Net-new mayor**, `services/arca_service.py`, deps nuevas                 |
| Auditoría                             | Solo `created_by_user_id`                 | **Net-new** `audit_logs`                                                   |
| Documento fiscal                      | No existía                                | **Net-new** `fiscal_documents` (id ≠ venta)                                |

---

## Apéndice B — Guía de implementación (rebanada vertical)

Por cada módulo nuevo (services, sales, payments, expenses, fiscal):

1. **Backend:** `models/` → `schemas/` → `repositories/` (SIEMPRE filtrar `tenant_id`) → `services/` (build `{data, meta}`) → `api/<modulo>.py` (router).
2. Registrar router en `app/main.py` dentro de `api_v1_router` (prefijo `/api/v1`).
3. Migración Alembic nueva en `alembic/versions/` (`0025_*`, `down_revision = "0024_..."`) + `uv run alembic upgrade head`.
4. **Frontend:** `types/api.ts` → `services/<modulo>.ts` → `features/<modulo>/components/` → `app/<ruta>/page.tsx`.
5. Menú: ajustar `components/layout/navigation-items.ts` (reemplazar placeholder `/accounting`, gatear escritura a `medico_veterinario`).
6. Tests en `apps/api/app/tests/test_<modulo>.py` (SQLite in-memory, patrón `conftest.py`).

**Reutilizar:** PDF (`services/clinical_history_pdf.py`), storage GCS (`services/storage.py`), envoltura (`schemas/common.py`), errores (`core/errors.py`), tenant/roles (`core/tenant.py`), traceability (`lib/user-traceability.ts`), cliente API (`lib/api.ts`), formatter ARS (`features/inventory/components/inventory-helpers.tsx` → promover a `lib/`). Para ARCA seguir el patrón de integración de `services/ai_service.py` y el gating de `AI_FEATURES_ENABLED`.
