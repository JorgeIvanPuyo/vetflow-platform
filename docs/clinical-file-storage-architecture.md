# Clinical File Storage Architecture Decision

## Context

Vetflow requiere soportar archivos clínicos asociados a pacientes:

-   PDFs (laboratorios, fórmulas, reportes)
-   Imágenes (radiografías, ecografías, fotos clínicas)
-   Archivos adjuntos para historia clínica

Actualmente existe el modelo `patient_file_references`, pero solo
almacena metadata/referencias. No existe carga real de archivos.

------------------------------------------------------------------------

## Problema

Necesitamos implementar almacenamiento real de archivos clínicos con:

-   seguridad por clínica (tenant)
-   trazabilidad por usuario
-   acceso controlado
-   escalabilidad
-   bajo costo
-   integración limpia con arquitectura actual

Arquitectura actual:

-   Frontend: Next.js (Vercel)
-   Backend: FastAPI (Cloud Run)
-   Auth: Firebase Authentication
-   Database: Supabase (PostgreSQL)
-   Multi-tenancy: tenant_id

------------------------------------------------------------------------

## Opciones evaluadas

### Opción 1: Firebase Storage

**Pros** - Integración nativa con Firebase Auth - SDK frontend simple -
Free tier inicial útil

**Contras** - Seguridad distribuida entre Firebase Rules y backend -
Duplica lógica de autorización - Menor coherencia arquitectónica

**Decisión:** Descartado.

------------------------------------------------------------------------

### Opción 2: AWS S3

**Pros** - Muy robusto - Estándar de industria - Escalable

**Contras** - Introduce AWS solo para storage - Mayor complejidad
operativa - Más credenciales y servicios externos

**Decisión:** Descartado.

------------------------------------------------------------------------

### Opción 3: Google Cloud Storage

**Pros** - Misma nube que Cloud Run - IAM unificado - Service accounts
ya disponibles - Backend controla toda la seguridad - Fácil generación
de signed URLs - Escalable - Bajo costo

**Contras** - Requiere configuración inicial de bucket e IAM

**Decisión:** Seleccionado.

------------------------------------------------------------------------

# Decisión técnica final

Usaremos:

## Google Cloud Storage (Bucket privado)

Modelo:

-   bucket privado
-   uploads solo desde backend
-   descargas mediante signed URLs
-   metadata persistida en PostgreSQL

------------------------------------------------------------------------

## Flujo de arquitectura

Frontend → FastAPI → Cloud Storage → Supabase

Descarga:

Frontend → FastAPI → Signed URL temporal → Descarga segura

------------------------------------------------------------------------

## Estructura de almacenamiento

`tenants/{tenant_id}/patients/{patient_id}/files/{file_reference_id}/{filename}`

------------------------------------------------------------------------

## Modelo de datos

Tabla: `patient_file_references`

Campos nuevos:

-   bucket_name
-   object_path
-   original_filename
-   content_type
-   size_bytes
-   uploaded_at
-   created_by_user_id

------------------------------------------------------------------------

## Seguridad

Bucket privado.

Reglas:

-   no archivos públicos
-   no acceso directo frontend
-   backend genera signed URLs
-   validación tenant-aware obligatoria

Tipos permitidos:

-   pdf
-   jpg
-   jpeg
-   png
-   webp

Límite inicial:

25MB

------------------------------------------------------------------------

## Endpoints planeados

POST `/api/v1/patients/{patient_id}/files/upload`

GET `/api/v1/file-references/{file_reference_id}/download-url`

DELETE `/api/v1/file-references/{file_reference_id}`

------------------------------------------------------------------------

## Razones de la decisión

### Coherencia arquitectónica

El backend ya centraliza:

-   auth
-   tenant resolution
-   autorización

Storage debe seguir mismo patrón.

### Menor complejidad

No se agregan nuevos proveedores.

### Seguridad centralizada

Toda autorización pasa por backend.

### Escalabilidad

Cloud Storage soporta crecimiento sin rediseño.

### Preparación para PDF export

Los archivos podrán integrarse en exportación futura de historia
clínica.

------------------------------------------------------------------------

## Slices planeados

### Slice 1

Backend upload infrastructure

### Slice 2

Frontend upload UI

### Slice 3

Production configuration

-   bucket creation
-   IAM permissions
-   env vars
-   Cloud Run secrets

------------------------------------------------------------------------

## Estado

Decision status: Approved

Fecha: 2026-05-01
