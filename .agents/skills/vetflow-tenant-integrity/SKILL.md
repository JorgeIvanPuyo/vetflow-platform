---
name: vetflow-tenant-integrity
description: Audita e implementa el aislamiento multi-tenant de Vetflow. Usar al cambiar autenticación, `TenantContext`, roles, modelos o migraciones tenant-owned, repositorios, servicios, endpoints, relaciones, búsquedas, agregados, exportaciones, archivos, contratos que expongan datos de clínica o accesos cross-tenant de superadmin. No usar para presentación frontend sin impacto en datos o autorización.
---

# Integridad multi-tenant de Vetflow

Proteger cada operación tenant-owned usando el código y las pruebas vigentes como fuente de verdad. No cargar `docs/` para ejecutar esta revisión.

## Delimitar el acceso

1. Revisar el diff y recorrer la ruta afectada: API, esquema, servicio, repositorio, modelo, migración y pruebas.
2. Clasificar cada operación como tenant-scoped, cross-tenant protegida o pública. No inferir excepciones por el nombre de la ruta; comprobar sus dependencias actuales.
3. Derivar la pertenencia desde modelos, claves foráneas y consultas reales. No mantener ni confiar en un mapa estático de entidades.
4. Identificar todos los recursos relacionados que toque la operación, incluidos los registros derivados.

## Asegurar el flujo del tenant

- Obtener `tenant_id`, usuario y rol desde `TenantContext`; en flujos tenant-scoped no aceptar un `tenant_id` elegido por el cliente.
- Asignar `tenant_id` y, cuando el modelo lo soporte, la trazabilidad de creación en el servidor.
- Filtrar por `tenant_id` dentro del repositorio en lecturas y mutaciones. Auditar detalle, listado, conteo, paginación, búsqueda, dashboard, agregación, exportación y eliminación.
- Filtrar todas las tablas tenant-owned relevantes cuando una consulta usa joins o subconsultas; no asumir que filtrar sólo la entidad raíz protege relaciones inconsistentes.
- Evitar `db.get` para entidades tenant-owned. Si su uso es necesario, comprobar el tenant antes de devolver datos, validar relaciones o mutar estado.
- Validar cada ID relacionado mediante una consulta tenant-scoped antes de enlazarlo. La existencia global del UUID no demuestra pertenencia.
- Construir rutas de archivos con el tenant autenticado y comprobar la pertenencia antes de firmar, descargar, reemplazar o borrar objetos.
- Mantener `404` para recursos de otra clínica cuando el patrón existente evita revelar su existencia; conservar los códigos de error vigentes.

## Revisar excepciones

- Permitir acceso cross-tenant a datos de dominio sólo mediante una dependencia explícita de autorización, como `require_superadmin`.
- Mantener las consultas cross-tenant separadas y nombradas de forma inequívoca; no reutilizarlas desde flujos tenant-scoped.
- Verificar que un usuario sin el rol requerido reciba `403` y que el acceso autorizado cubra únicamente el alcance previsto.
- Tratar la búsqueda global de usuario por email como bootstrap de autenticación: usarla sólo para derivar su propio tenant y no para exponer datos ni permitir seleccionar clínica.
- Revisar con especial cuidado cambios en `apps/api/app/core/tenant.py`, resolución por email y fallback de desarrollo; no debilitar producción para facilitar pruebas locales.

## Revisar persistencia

- Incluir `tenant_id` no nulo, clave foránea e índice en cada nueva tabla tenant-owned, salvo que el modelo existente demuestre otra estrategia.
- Revisar las migraciones anteriores antes de crear una nueva y mantener sincronizados modelo y migración.
- Evaluar índices o restricciones compuestas cuando una identidad o unicidad deba limitarse a una clínica.
- No depender sólo de claves foráneas simples para impedir relaciones entre tenants; validar la pertenencia en la capa de servicio o con una restricción adecuada.

## Probar de forma adversarial

Crear o ajustar pruebas con dos tenants y, cuando aplique, dos usuarios del mismo tenant:

- Confirmar que la creación usa el tenant autenticado y que la trazabilidad usa el usuario cuando esté disponible.
- Confirmar que listados, conteos, búsquedas, dashboards y exportaciones excluyen datos ajenos.
- Confirmar que detalle, actualización y eliminación de un ID ajeno responden sin revelar el recurso.
- Confirmar que no se pueden enlazar IDs de otra clínica.
- Confirmar que archivos y sus rutas no cruzan tenants.
- Confirmar que usuarios del mismo tenant comparten los datos permitidos.
- Confirmar tanto el rechazo de un rol ordinario como el caso permitido de superadmin.

Ejecutar primero el archivo o test afectado:

```bash
cd apps/api
uv run --frozen pytest app/tests/test_<dominio>.py
```

Ampliar a `uv run --frozen pytest` cuando cambien el contexto de tenant, auth, roles, repositorios compartidos o varias áreas de dominio.

## Cerrar la revisión

- En una revisión, presentar primero vulnerabilidades o faltantes con referencias de archivo y línea.
- En una implementación, informar qué escenarios entre tenants quedaron cubiertos y qué comandos se ejecutaron.
- No declarar seguro el cambio sólo porque contiene algún filtro `tenant_id`; comprobar todos los caminos de acceso afectados.
