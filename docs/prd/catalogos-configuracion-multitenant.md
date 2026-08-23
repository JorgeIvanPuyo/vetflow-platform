# PRD — Catálogos y configuración multi-tenant de Vetflow

> **Estado:** Propuesta lista para refinamiento técnico y de producto  
> **Fecha:** 2026-08-09  
> **Alcance:** Catálogos, preferencias y autoservicio por clínica  
> **Código validado:** `apps/api`, migraciones `0001` a `0025`, `apps/web` y pruebas vigentes

---

## 1. Resumen ejecutivo

Vetflow ya opera con una única aplicación y una única base de datos, aislando los datos de cada clínica mediante `tenant_id`. Sin embargo, varias opciones de negocio continúan definidas como arreglos de frontend, tipos `Literal` del backend, textos libres o valores predeterminados globales.

Esta situación obliga al equipo de Vetflow a modificar código o mantener instalaciones especiales cuando una clínica necesita servicios, categorías, duraciones, impuestos o vocabulario propios. El objetivo de esta iniciativa es convertir esas decisiones de negocio en configuración administrable por cada clínica, sin convertir en editables los estados técnicos que controlan los flujos del sistema.

La solución propuesta combina:

1. Un catálogo específico de servicios por clínica.
2. Catálogos simples tenant-owned para listas reutilizables.
3. Preferencias estructuradas de clínica.
4. Valores iniciales sembrados durante el onboarding.
5. Un rol de administrador de clínica con autorización backend.
6. Compatibilidad gradual con los contratos y datos actuales.

No se debe crear una instancia de Vetflow por clínica. Todas las clínicas utilizarán el mismo despliegue y cada configuración se resolverá desde el `TenantContext` autenticado.

---

## 2. Contexto y estado actual

### 2.1 Arquitectura vigente

- Backend FastAPI con capas `router -> service -> repository -> SQLAlchemy`.
- Frontend Next.js 14 con rutas, features, servicios y tipos TypeScript.
- PostgreSQL con migraciones Alembic; la cadena vigente termina en `0025_consultation_six_step_workflow.py`.
- Firebase autentica la identidad y el backend deriva `tenant_id`, usuario y rol.
- Los recursos clínicos, archivos, búsquedas, agregados y exportaciones están diseñados para filtrar por tenant.
- El perfil de clínica ya permite nombre, logo, contacto, notas y zona horaria.

### 2.2 Problema observable

Actualmente existen cuatro clases de configuración mezcladas:

1. **Catálogos de negocio quemados:** opciones que una clínica debería poder administrar.
2. **Valores libres sin catálogo:** permiten escribir cualquier texto, pero no reutilizar, ordenar ni reportar consistentemente.
3. **Preferencias globales implícitas:** moneda, margen, impuestos, locale y duraciones.
4. **Enumeraciones técnicas:** estados y códigos que controlan lógica y deben permanecer en código.

### 2.3 Inventario verificado

| Área | Estado actual | Clasificación propuesta |
| --- | --- | --- |
| Servicios y tipos de turno | `consultation`, `follow_up`, `vaccine`, `deworming`, `exam`, `other` en frontend y esquema API | Servicio tenant-owned con clasificación interna estable |
| Estados de turno | `scheduled`, `completed`, `cancelled`, `no_show` | Enumeración técnica, no editable |
| Tipos de seguimiento | Control, vacuna, desparasitación, revisión de examen y otro | Plantillas o catálogo tenant-owned |
| Estados de seguimiento | Pendiente, programado, completado, cancelado y vencido | Enumeración técnica, no editable |
| Duraciones | 15, 30, 45 y 60 minutos; default 30 | Preferencia y opciones tenant-owned |
| Cuidados preventivos | Vacuna, desparasitación y otro; nombre libre | Familia técnica estable + catálogo tenant-owned de prestaciones/protocolos |
| Estudios solicitados | Laboratorio, examen y otro; nombre libre | Familia técnica estable + catálogo tenant-owned de estudios |
| Estados de examen | Solicitado, realizado y resultado cargado | Enumeración técnica, no editable |
| Categorías de inventario | Medicamento, vacuna, insumo, alimento y otro | Catálogo tenant-owned |
| Subcategorías de inventario | Texto libre | Catálogo tenant-owned opcional y relacionado con categoría |
| Unidades de inventario | Unidad, comprimido, cápsula, ml, kg, caja, etc. | Catálogo global normalizado con selección por clínica |
| Proveedores | Texto libre repetido | Directorio tenant-owned |
| Motivos de salida de inventario | Venta, consulta, ajuste, descarte, daño y otro | Códigos operativos estables; permitir nota o motivo complementario |
| Tipos de archivo clínico | Laboratorio, radiografía, ecografía, foto, documento y otro | Catálogo tenant-owned |
| Especies | Canino, felino y otro; acepta texto libre | Valores base globales + extensiones tenant-owned |
| Razas | Texto libre | Catálogo/autocompletado por especie y clínica |
| Sexo del paciente | Macho y hembra | Vocabulario clínico estable, no arbitrario |
| Mucosas | Seis opciones de frontend | Presets clínicos tenant-owned con entrada libre |
| Hidratación | Cuatro opciones de frontend | Presets clínicos tenant-owned con entrada libre |
| Etiquetas diagnósticas | Texto transformado a lista | Catálogo/autocompletado tenant-owned, sin impedir texto libre |
| Medicación manual e indicaciones | Texto libre | Plantillas tenant-owned como mejora posterior |
| Moneda | ARS en nombres de campos, UI y formatters `es-AR` | Preferencia de tenant y migración a nombres monetarios neutrales |
| Impuestos y margen | Impuestos default 0 %, margen default 35 % | Preferencias tenant-owned |
| Zona horaria | Columna de tenant, pero frontend usa zona del navegador | Preferencia existente aplicada consistentemente |
| Formatos PDF, MIME y extensiones | Valores controlados por validación | Configuración técnica global, no editable por clínica |
| Roles y pasos clínicos | Códigos usados por autorización y lógica | Enumeraciones técnicas versionadas en código |

### 2.4 Solapamiento con el PRD de facturación

`docs/prd/facturacion-mvp.md` ya propone crear un catálogo `services`, pero toma dos decisiones que entran en tensión con esta iniciativa:

- usa nombres monetarios terminados en `_ars`;
- no crea un rol separado de administrador de clínica.

Antes de implementar facturación o esta iniciativa se debe adoptar un único modelo canónico de servicios. Este PRD recomienda que `services` sea transversal, tenant-owned y monetariamente neutral. Facturación, agenda y consultas deberán reutilizarlo; no se deben crear catálogos paralelos.

---

## 3. Problema de producto

### 3.1 Problema principal

Una clínica no puede adaptar Vetflow a su operación sin intervención del equipo de desarrollo. Esto aumenta soporte, genera forks o despliegues especiales y limita la incorporación de clínicas de otros países o especialidades.

### 3.2 Impacto

- Los servicios ofrecidos por una clínica no están modelados como datos.
- La agenda no puede asignar precios ni duraciones reutilizables a una prestación.
- Las listas libres generan nombres duplicados y reportes inconsistentes.
- ARS y `es-AR` impiden reutilización correcta fuera de Argentina.
- Un veterinario común puede acceder a Ajustes, pero no existe un responsable tenant-scoped con permisos claros para administrar configuración.
- La creación de un tenant no genera automáticamente configuración inicial.

---

## 4. Objetivos

### 4.1 Objetivos del MVP

1. Permitir que cada clínica cree, edite, ordene y desactive sus servicios.
2. Permitir que cada clínica administre los catálogos simples priorizados.
3. Configurar moneda, locale, impuestos, margen y duración predeterminada.
4. Reutilizar los servicios desde agenda y, posteriormente, facturación.
5. Sembrar valores iniciales al crear una clínica, sin soporte manual.
6. Preservar datos históricos cuando un catálogo cambie o se desactive.
7. Autorizar la configuración desde backend mediante un administrador de clínica.
8. Garantizar aislamiento adversarial entre al menos dos tenants.

### 4.2 Métricas de éxito

- Una clínica nueva puede configurar sus servicios sin intervención de Vetflow.
- Cero endpoints de catálogos aceptan un `tenant_id` elegido por el cliente.
- Dos clínicas pueden usar nombres iguales con precios, duraciones y opciones diferentes.
- Ningún cambio de nombre o precio altera registros históricos.
- Las opciones configurables prioritarias dejan de depender de arreglos del frontend.
- El onboarding crea una clínica utilizable en una única operación transaccional.

### 4.3 Fuera de alcance inicial

- Constructor arbitrario de formularios o campos clínicos.
- Permitir que una clínica defina estados o transiciones de negocio.
- EAV genérico para almacenar cualquier dato sin esquema.
- Personalización visual completa o CSS por tenant.
- Traducción completa de toda la aplicación.
- Conversión automática entre múltiples monedas dentro de una misma clínica.
- Sedes o sucursales dentro de un tenant.
- PostgreSQL Row-Level Security en la primera entrega.

---

## 5. Personas y permisos

### 5.1 Administrador de clínica

Responsable de configurar servicios, catálogos, preferencias, horarios y equipo de su propia clínica. No puede consultar ni modificar datos de otro tenant.

### 5.2 Médico veterinario

Consume servicios y catálogos durante la operación clínica. Puede proponer nuevos textos libres donde el flujo lo permita, pero no administra configuración salvo que también tenga permiso administrativo.

### 5.3 Contador

Consume moneda, impuestos y servicios desde facturación. No modifica configuración clínica general por defecto.

### 5.4 Superadmin de plataforma

Administra la plataforma y operaciones cross-tenant explícitas. No debe usarse como sustituto del administrador de cada clínica.

### 5.5 Decisión de autorización

Se recomienda agregar `clinic_admin` o evolucionar a permisos/membresías. Para el primer incremento se acepta un rol `clinic_admin` validado por una dependencia backend equivalente a `require_role`.

La visibilidad de botones en frontend no constituye autorización. Todo `POST`, `PATCH`, cambio de orden o desactivación debe validarse en la API.

---

## 6. Principios de diseño

1. El tenant se deriva siempre de `TenantContext`.
2. Un payload tenant-scoped nunca acepta `tenant_id`.
3. Los catálogos usados se archivan mediante `is_active`; no se eliminan físicamente.
4. Los documentos históricos guardan snapshots de nombre, precio, impuesto y moneda cuando corresponda.
5. Los estados técnicos permanecen versionados en código.
6. Los valores iniciales son copiables y modificables por tenant, no referencias globales mutables.
7. Cada relación por ID se valida con una consulta tenant-scoped.
8. Las listas con semántica propia usan tablas específicas; no todo se fuerza dentro de una tabla genérica.
9. Los metadatos JSON sólo se permiten con esquema Pydantic definido por `catalog_type`.
10. Toda unicidad de negocio se limita por tenant.

---

## 7. Requerimientos funcionales

### RF-01. Preferencias de clínica

El administrador configura:

- moneda ISO 4217, inicialmente una por clínica;
- locale de presentación;
- zona horaria IANA;
- impuesto de compra predeterminado;
- impuesto de venta predeterminado;
- margen de venta predeterminado;
- duración predeterminada de turnos;
- opciones de duración habilitadas;
- regla de redondeo monetario.

**Criterios de aceptación**

- Los valores se leen desde el tenant autenticado.
- La moneda se valida como código soportado y no como texto libre.
- Cambiar defaults afecta nuevos registros, no registros existentes.
- La zona horaria se aplica en agenda, dashboard, seguimientos y PDFs.
- Los porcentajes se validan en backend.

### RF-02. Catálogo de servicios

Cada clínica puede crear servicios con:

- nombre y descripción;
- código interno opcional;
- clasificación interna estable;
- duración predeterminada;
- precio base;
- impuesto de venta;
- color de agenda opcional;
- disponibilidad para agenda;
- orden e indicador activo.

La clasificación interna inicial será: `consultation`, `follow_up`, `vaccine`, `deworming`, `exam`, `procedure` y `other`. Esta clasificación no es el nombre visible del servicio y permanece controlada por código.

Ejemplos de una misma clínica:

- Consulta general, 30 minutos.
- Consulta de especialidad, 60 minutos.
- Vacunación anual, 20 minutos.
- Ecografía abdominal, 45 minutos.

**Criterios de aceptación**

- Dos tenants pueden crear servicios con el mismo nombre.
- Un mismo tenant no puede duplicar un nombre normalizado activo.
- Un servicio desactivado no aparece al crear turnos nuevos.
- Los turnos históricos continúan mostrando el servicio desactivado.
- Agenda puede calcular la hora de finalización usando la duración del servicio.
- El usuario puede ajustar duración o precio en el flujo que lo permita sin modificar el catálogo.

### RF-03. Catálogos simples

El administrador puede gestionar inicialmente:

- categorías y subcategorías de inventario;
- proveedores;
- estudios y exámenes;
- prestaciones preventivas;
- plantillas de seguimiento;
- tipos documentales;
- presets de mucosas e hidratación.

En una segunda etapa:

- especies habilitadas y razas;
- etiquetas diagnósticas;
- plantillas de prescripción e indicaciones.

Cada elemento tiene nombre, descripción opcional, orden, estado y metadatos definidos por tipo.

### RF-04. Administración desde Ajustes

`/settings` incorpora secciones de:

- Perfil de clínica.
- Preferencias regionales y operativas.
- Servicios.
- Catálogos clínicos.
- Inventario y proveedores.
- Equipo y permisos.

Cada listado permite crear, editar, ordenar, activar y desactivar. El frontend debe explicar referencias activas antes de desactivar, pero no debe mostrar texto técnico sobre `tenant_id` o implementación.

### RF-05. Valores iniciales y restauración

Al crear un tenant se generan defaults versionados:

- servicios básicos;
- categorías de inventario;
- estudios frecuentes;
- cuidados preventivos;
- tipos documentales;
- presets clínicos;
- preferencias regionales seleccionadas durante onboarding.

Los defaults se copian al tenant y luego son independientes. Una actualización de defaults de plataforma no sobrescribe modificaciones locales.

La restauración de un valor predeterminado crea o reactiva solamente ese elemento y nunca borra personalizaciones.

### RF-06. Integridad histórica

- Un servicio o catálogo referenciado no se elimina físicamente.
- Turnos, ventas y demás documentos guardan la referencia por ID.
- Los documentos económicos guardan snapshots de nombre, monto, impuesto y moneda.
- Los registros clínicos conservan el texto presentado en el momento del registro cuando sea relevante para trazabilidad.
- Los listados históricos incluyen elementos inactivos cuando son referenciados.

### RF-07. Onboarding de clínica

Una operación transaccional crea:

1. Tenant.
2. Preferencias.
3. Catálogos iniciales.
4. Usuario administrador o membresía.
5. Registro de versión del template aplicado.

Si cualquier paso falla, no queda un tenant parcialmente aprovisionado.

### RF-08. Auditoría

Se registra quién creó, modificó, reordenó, activó o desactivó configuración, incluyendo tenant, usuario, entidad, ID, timestamp y cambios relevantes. La auditoría es tenant-scoped; una vista cross-tenant requiere autorización explícita de plataforma.

### RF-09. Compatibilidad

- Los contratos actuales siguen funcionando durante una ventana de migración.
- Los campos string existentes no se eliminan hasta completar backfill y despliegue frontend.
- Los IDs de catálogo se introducen primero como opcionales.
- Los clientes antiguos reciben labels y códigos compatibles.
- Las nuevas respuestas pueden agregar campos sin cambiar la envoltura `{data, meta}`.

---

## 8. Modelo de datos propuesto

Todas las tablas tenant-owned heredan `BaseModel`, llevan `tenant_id` no nulo, FK e índice, y registran `created_by_user_id` cuando aplica.

### 8.1 `tenant_preferences`

Relación uno a uno con `tenants`.

```text
tenant_id PK/FK
currency_code CHAR(3)
locale VARCHAR(20)
default_purchase_tax_rate NUMERIC(5,2)
default_sale_tax_rate NUMERIC(5,2)
default_profit_margin NUMERIC(7,2)
default_appointment_duration_minutes INTEGER
appointment_duration_options JSONB
money_rounding_increment NUMERIC(12,2)
catalog_template_version INTEGER
created_at, updated_at
```

La zona horaria continúa en `tenants.timezone`; no se duplica. `appointment_duration_options` es una lista de enteros validada, no un objeto de configuración libre.

### 8.2 `services`

```text
id UUID PK
tenant_id UUID FK/index
code VARCHAR(80) nullable
name VARCHAR(255)
normalized_name VARCHAR(255)
description TEXT nullable
kind VARCHAR(50)
default_duration_minutes INTEGER
default_price NUMERIC(12,2) nullable
sale_tax_rate_percentage NUMERIC(5,2)
calendar_color VARCHAR(20) nullable
is_bookable BOOLEAN
sort_order INTEGER
is_active BOOLEAN
created_by_user_id UUID nullable
created_at, updated_at
```

Restricciones mínimas:

- unique `(tenant_id, normalized_name)` para elementos activos mediante índice parcial;
- `default_duration_minutes > 0`;
- precios no negativos;
- impuesto entre 0 y 100;
- `kind` validado por backend.

### 8.3 `catalog_items`

Adecuado para vocabularios simples, no para servicios ni proveedores con datos comerciales extensos.

```text
id UUID PK
tenant_id UUID FK/index
catalog_type VARCHAR(80)
parent_id UUID nullable
code VARCHAR(80) nullable
name VARCHAR(255)
normalized_name VARCHAR(255)
description TEXT nullable
metadata JSONB
sort_order INTEGER
is_active BOOLEAN
created_by_user_id UUID nullable
created_at, updated_at
```

Restricciones mínimas:

- índice `(tenant_id, catalog_type, is_active, sort_order)`;
- unique tenant-scoped por tipo y nombre normalizado;
- `parent_id` validado contra el mismo tenant y tipo compatible;
- allowlist backend de `catalog_type`;
- esquema de `metadata` por tipo.

### 8.4 `suppliers`

Se recomienda tabla específica porque un proveedor evolucionará hacia contacto, identificación fiscal, compras y cuentas por pagar.

```text
id, tenant_id, name, document_id?, phone?, email?, address?, notes?, is_active,
created_by_user_id, created_at, updated_at
```

### 8.5 Referencias desde dominios existentes

Adiciones graduales previstas:

- `appointments.service_id` nullable.
- `exams.exam_catalog_item_id` nullable.
- `consultation_study_requests.exam_catalog_item_id` nullable.
- `patient_preventive_care.catalog_item_id` nullable.
- `patient_file_references.file_type_catalog_item_id` nullable.
- `inventory_items.category_catalog_item_id` nullable.
- `inventory_items.supplier_id` nullable.

Los campos string actuales se conservan durante la transición y sirven como snapshot/fallback.

### 8.6 Identidad y membresía

El modelo vigente `users.tenant_id` más email globalmente único impide que una identidad participe en varias clínicas. Antes de habilitar usuarios multi-clínica se recomienda separar:

```text
users: identidad global
tenant_memberships: tenant_id, user_id, role, is_active
platform_roles: autorización cross-tenant separada
```

Esta separación no bloquea el primer incremento de catálogos, pero debe decidirse antes de ampliar onboarding y roles.

---

## 9. Contratos API propuestos

### 9.1 Preferencias

```text
GET   /api/v1/clinic/preferences
PATCH /api/v1/clinic/preferences
```

### 9.2 Servicios

```text
GET    /api/v1/services
POST   /api/v1/services
GET    /api/v1/services/{service_id}
PATCH  /api/v1/services/{service_id}
POST   /api/v1/services/{service_id}/activate
POST   /api/v1/services/{service_id}/deactivate
PATCH  /api/v1/services/reorder
```

### 9.3 Catálogos simples

```text
GET    /api/v1/clinic/catalogs/{catalog_type}
POST   /api/v1/clinic/catalogs/{catalog_type}
PATCH  /api/v1/clinic/catalogs/{catalog_type}/{item_id}
POST   /api/v1/clinic/catalogs/{catalog_type}/{item_id}/activate
POST   /api/v1/clinic/catalogs/{catalog_type}/{item_id}/deactivate
PATCH  /api/v1/clinic/catalogs/{catalog_type}/reorder
```

### 9.4 Bootstrap de configuración

Para evitar que cada pantalla realice múltiples solicitudes:

```text
GET /api/v1/clinic/configuration?include=preferences,services,catalogs
```

La respuesta incluye una versión o `updated_at` para invalidación de caché. Nunca incluye datos de otro tenant ni acepta tenant por query.

### 9.5 Convenciones

- Respuestas `{data, meta}`.
- Listados con `include_inactive=false` por defecto.
- `404` para IDs de otro tenant, sin revelar existencia.
- `409` para duplicados tenant-scoped.
- `422` para tipo, porcentaje, duración o metadata inválida.
- `403` para usuarios sin permiso de administración.
- Creación, actualización, reorder y activación usan el tenant autenticado.

---

## 10. Experiencia frontend

### 10.1 Arquitectura

Nuevos módulos previstos:

```text
src/services/clinic-preferences.ts
src/services/services.ts
src/services/catalogs.ts
src/features/clinic-config/
src/features/services/
```

Un `ClinicConfigurationProvider` carga preferencias y catálogos compartidos después de resolver el usuario actual. Las features consumen datos tipados; no importan arreglos locales de opciones configurables.

### 10.2 Estados requeridos

- Carga inicial y reintento.
- Catálogo vacío.
- Duplicado.
- Elemento activo/inactivo.
- Elemento referenciado que no puede desaparecer.
- Permiso insuficiente.
- Configuración incompleta con defaults seguros.
- Valor histórico inactivo seleccionado en una edición.

### 10.3 Reglas de presentación

- Los estados técnicos conservan helpers y badges locales.
- Los catálogos muestran labels entregados por API.
- Moneda y números usan `Intl.NumberFormat(locale, {currency})` con preferencias del tenant.
- Fechas usan explícitamente `tenant.timezone`, no la zona del navegador.
- Los formularios permiten buscar cuando el catálogo crece.
- El orden configurado se respeta en formularios y filtros.

---

## 11. Estrategia de migración

### 11.1 Migración inicial

La siguiente revisión Alembic real debe partir de `0025`; previsiblemente será `0026`.

1. Crear `tenant_preferences`, `services`, `catalog_items` y `suppliers`.
2. Crear índices y restricciones tenant-scoped.
3. Agregar FKs opcionales a dominios priorizados.
4. Sembrar defaults para todos los tenants existentes.
5. Registrar versión del template.

### 11.2 Servicios y agenda

1. Crear un servicio default por tipo de turno para cada tenant.
2. Agregar `appointments.service_id` nullable.
3. Mantener `appointment_type` como clasificación técnica durante compatibilidad.
4. Nuevos turnos escriben `service_id` y `appointment_type=service.kind`.
5. Turnos existentes pueden permanecer sin referencia o backfillearse cuando la relación sea inequívoca.
6. Lecturas resuelven primero el servicio y luego el label histórico/fallback.

### 11.3 Neutralización de ARS

La migración monetaria debe ser separada del primer CRUD de servicios para reducir riesgo.

1. Añadir `currency_code` a preferencias.
2. Introducir nombres neutrales en modelos y contratos nuevos: `default_price`, `purchase_price`, `sale_price`, `unit_cost`, `total_cost`.
3. Mantener aliases `_ars` de lectura/escritura durante una ventana de compatibilidad.
4. Migrar frontend a campos neutrales y formatter por tenant.
5. Renombrar columnas físicas o retirar aliases únicamente después de validar consumidores.

No se almacenan conversiones ni múltiples monedas por registro en el MVP. Cada documento económico sí guarda `currency_code` como snapshot.

### 11.4 Catálogos existentes

- Agregar FK nullable.
- Crear elementos a partir de valores conocidos y strings frecuentes por tenant.
- Backfill sólo con coincidencias normalizadas inequívocas.
- Conservar el string original.
- Cambiar escrituras nuevas para incluir ID y snapshot.
- Retirar el flujo antiguo en una fase posterior, no en el mismo despliegue.

### 11.5 Orden de despliegue

1. Migración compatible.
2. Backend con doble lectura/escritura.
3. Seed y verificación de tenants existentes.
4. Frontend consumiendo configuración.
5. Observación y corrección de datos sin mapear.
6. Endurecimiento de campos y eliminación posterior de compatibilidad.

---

## 12. Plan de implementación

### Fase 0. Decisiones y coordinación

- Alinear este PRD con facturación para adoptar un único `services`.
- Confirmar rol `clinic_admin` frente a permisos/membresías.
- Confirmar países iniciales, monedas y locales soportados.
- Definir allowlist exacta de `catalog_type` para MVP.
- Definir defaults de onboarding por mercado.

**Salida:** decisiones cerradas y contratos revisados antes de migraciones.

### Fase 1. Fundaciones backend

- Agregar rol/dependencia de autorización tenant admin.
- Crear modelos, migración, esquemas, repositorios y servicios.
- Implementar preferencias, servicios y seed idempotente.
- Añadir pruebas unitarias y API con dos tenants.
- No integrar todavía todos los formularios.

**Salida:** API tenant-scoped administrable y tenants existentes sembrados.

### Fase 2. Servicios como rebanada vertical

- Crear pantalla de Servicios dentro de Ajustes.
- Crear cliente y tipos frontend.
- Integrar servicios con creación/edición de turnos.
- Resolver duración, label, color y clasificación desde servicio.
- Mantener compatibilidad con `appointment_type`.

**Salida:** cada clínica administra y usa sus propios servicios en agenda.

### Fase 3. Preferencias regionales

- Añadir editor de moneda, locale, impuestos, margen y duración.
- Crear formatter monetario compartido.
- Aplicar zona horaria de tenant en agenda, dashboard, seguimientos y PDF.
- Migrar inventario de defaults globales a preferencias.

**Salida:** una segunda clínica/país no requiere cambios de código para configuración básica.

### Fase 4. Catálogos operativos

- Inventario: categorías, subcategorías y proveedores.
- Clínica: estudios, preventivos, tipos documentales y seguimientos.
- Reemplazar listas locales por consultas/configuración compartida.
- Mantener estados y clasificaciones internas fijas.

**Salida:** principales listas operativas administradas por clínica.

### Fase 5. Catálogos clínicos y onboarding

- Especies, razas y presets clínicos.
- Diagnósticos y plantillas como autocompletado opcional.
- Crear flujo transaccional de onboarding.
- Añadir clonación/restauración de defaults.

**Salida:** autoservicio completo para alta y adaptación de una clínica.

### Fase 6. Identidad, auditoría y endurecimiento

- Decidir e implementar `tenant_memberships` si habrá usuarios multi-clínica.
- Separar rol de plataforma y rol de tenant.
- Completar auditoría de configuración.
- Retirar contratos legacy tras la ventana acordada.
- Evaluar RLS como defensa adicional, no sustituto de filtros de aplicación.

**Salida:** modelo preparado para crecimiento operativo y de soporte.

---

## 13. Archivos y módulos previstos

### Backend

```text
apps/api/app/core/roles.py
apps/api/app/core/tenant.py
apps/api/app/models/tenant_preference.py
apps/api/app/models/service.py
apps/api/app/models/catalog_item.py
apps/api/app/models/supplier.py
apps/api/app/repositories/*
apps/api/app/services/*
apps/api/app/schemas/*
apps/api/app/api/services.py
apps/api/app/api/clinic_catalogs.py
apps/api/app/api/clinic_preferences.py
apps/api/alembic/versions/0026_*.py
apps/api/app/tests/test_services.py
apps/api/app/tests/test_clinic_catalogs.py
apps/api/app/tests/test_clinic_preferences.py
apps/api/app/tests/test_tenant_provisioning.py
```

### Frontend

```text
apps/web/src/types/api.ts
apps/web/src/services/services.ts
apps/web/src/services/catalogs.ts
apps/web/src/services/clinic-preferences.ts
apps/web/src/features/services/*
apps/web/src/features/clinic-config/*
apps/web/src/features/clinic/components/settings-screen.tsx
apps/web/src/features/agenda/*
apps/web/src/features/inventory/*
apps/web/src/lib/datetime.ts
apps/web/src/lib/money.ts
```

La lista es orientativa. Se deben respetar las divisiones reales del repositorio y evitar un único componente de Ajustes excesivamente grande.

---

## 14. Pruebas y validación

### 14.1 Casos multi-tenant obligatorios

- Tenant A y B pueden crear el mismo nombre con atributos diferentes.
- Un listado sólo devuelve elementos del tenant autenticado.
- Detalle, edición, reorder, activación y desactivación de un ID ajeno devuelven `404`.
- No se puede relacionar un servicio, padre, proveedor o catálogo de otro tenant.
- Un usuario del mismo tenant ve los catálogos compartidos.
- Un usuario sin permiso administrativo recibe `403` al mutar.
- Un administrador de clínica no obtiene capacidades cross-tenant.
- Un superadmin sólo opera cross-tenant mediante endpoints explícitos.
- Conteos, búsqueda, caché y bootstrap no mezclan tenants.

### 14.2 Casos funcionales

- Duplicados normalizados reciben `409`.
- Un elemento desactivado desaparece de formularios nuevos.
- Un registro histórico sigue resolviendo un elemento desactivado.
- Cambiar defaults no altera inventario ni turnos existentes.
- Seed repetido es idempotente.
- Reorder valida todos los IDs y el tenant en una transacción.
- Locale, moneda y timezone se aplican consistentemente.
- Backfill conserva strings sin coincidencia segura.

### 14.3 Validación técnica

```bash
cd apps/api
uv run --frozen pytest app/tests/test_services.py
uv run --frozen pytest app/tests/test_clinic_catalogs.py
uv run --frozen pytest app/tests/test_clinic_preferences.py
uv run --frozen pytest

cd apps/web
pnpm exec tsc --noEmit
pnpm run lint
pnpm run build
```

También se debe probar upgrade de la migración sobre una copia local con al menos dos tenants y datos existentes. Nunca validar contra producción.

---

## 15. Observabilidad y operación

- Logs estructurados con `tenant_id`, `user_id`, catálogo y acción, sin contenido clínico innecesario.
- Métrica de tenants sin seed o con versión de template antigua.
- Métrica de valores legacy sin FK mapeada.
- Métrica de errores `403`, `404` cross-tenant y duplicados.
- Cachés siempre incluyen `tenant_id` y versión de configuración en la clave.
- Jobs futuros reciben tenant explícito y vuelven a validar pertenencia al cargar datos.
- Exportaciones y archivos continúan usando rutas prefijadas por tenant.

---

## 16. Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Convertir estados técnicos en listas editables | Allowlist estricta y separación entre `kind/status` y label de catálogo |
| Duplicar el catálogo de facturación | Un único modelo `services` compartido antes de implementar ambos módulos |
| Cambiar históricos al renombrar valores | FK más snapshot y desactivación en lugar de borrado |
| Filtración cross-tenant por IDs relacionados | Validación repository/service tenant-scoped y pruebas adversariales |
| Migración de strings ambiguos | Backfill conservador; mantener fallback y reporte de no mapeados |
| Tabla genérica convertida en EAV | Metadata limitada por esquemas; entidades específicas para servicios/proveedores |
| Caché compartida entre clínicas | Claves con tenant y versión de configuración |
| Permisos sólo en frontend | Dependencias de autorización aplicadas en todos los endpoints de mutación |
| Romper inventario por neutralizar ARS | Migración separada, aliases compatibles y despliegue gradual |
| Defaults de plataforma sobrescriben personalizaciones | Copia versionada por tenant, seeds idempotentes y sin updates destructivos |

---

## 17. Criterios de aceptación de la iniciativa

La iniciativa se considera completa cuando:

1. Una clínica administra servicios, preferencias y catálogos prioritarios desde Ajustes.
2. Agenda utiliza servicios tenant-owned y deja de depender de la lista visible quemada.
3. Moneda, locale, impuestos, margen y duración no requieren editar código.
4. Onboarding crea configuración inicial automáticamente.
5. Los valores utilizados pueden desactivarse sin romper históricos.
6. La API aplica permisos y aislamiento tenant en lectura y escritura.
7. No existen dos catálogos de servicios para agenda y facturación.
8. Las pruebas con dos tenants cubren CRUD, referencias, búsquedas, orden y permisos.
9. Backend completo, TypeScript, lint y build finalizan correctamente.
10. Se documenta cualquier compatibilidad temporal y su condición de retiro.

---

## 18. Preguntas que deben cerrarse antes de Fase 1

1. ¿`clinic_admin` será un rol exclusivo o una capacidad adicional de una membresía?
2. ¿Una persona podrá pertenecer a varias clínicas en el horizonte de producto?
3. ¿Qué países, monedas y locales deben sembrarse inicialmente?
4. ¿Facturación adoptará desde el inicio campos monetarios neutrales?
5. ¿Qué catálogos exactos entran en el primer MVP después de servicios?
6. ¿Los precios de servicios incluyen impuesto o se presentan antes de impuesto?
7. ¿Los horarios de atención pertenecen a la clínica completa o se requerirán agendas por profesional?
8. ¿Se permite crear un valor rápido desde un formulario operativo o sólo desde Ajustes?
9. ¿Qué cambios requieren auditoría visible para la clínica?
10. ¿Cuál será la ventana de compatibilidad de los campos legacy?

