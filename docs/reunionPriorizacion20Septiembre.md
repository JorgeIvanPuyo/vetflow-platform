# Vetflow — Seguimiento de solicitudes y pendientes de usuarios

**Reunión de seguimiento:** 20 de septiembre de 2026

## Objetivo de la reunión

Revisar las solicitudes y reportes realizados por el equipo veterinario, validar las funcionalidades entregadas recientemente y acordar prioridades para los siguientes desarrollos.

Durante las últimas semanas el equipo de desarrollo ha estado concentrado principalmente en:

- Inventario.
- Compras.
- Ventas.
- Configuración por clínica.
- Catálogos.
- Métodos de pago.
- Facturación.
- Preparación de la integración con ARCA.

Esto permitió avanzar significativamente en los módulos necesarios para completar el flujo administrativo y de facturación, aunque algunos bugs menores y mejoras de experiencia quedaron pendientes de priorización.

---

## Estados

- ✅ **Resuelto:** cambio implementado y disponible.
- 🟡 **En ejecución:** actualmente en desarrollo.
- 🔵 **Pendiente de validación:** ya se realizaron cambios, pero necesitamos feedback de los usuarios.
- 🟠 **Pendiente de definición/priorización:** necesitamos acordar alcance o prioridad.
- ⚪ **Pendiente de confirmar:** necesitamos verificar si el problema continúa existiendo o si ya fue solucionado.

---

## Solicitudes y seguimiento

| #  | Fecha reportada | Solicitud / Reporte                                                                                                       | Estado actual                    | Respuesta / Avance                                                                                                                                | Acción requerida en reunión                                                                                                                   | Prioridad          |
| -- | --------------- | ------------------------------------------------------------------------------------------------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| 1  | **6 jul**       | Los datos del examen como temperatura, peso, frecuencia, etc. no quedaban registrados en la Historia Clínica.             | ✅ Resuelto                       | Corregido el **7 de julio**.                                                                                                                      | Confirmar que actualmente funciona correctamente.                                                                                             | Cerrado            |
| 2  | **8 jul**       | Permitir edición de elementos de vacunas y desparasitación.                                                               | ✅ Resuelto                       | Corregido el **8 de julio**.                                                                                                                      | Confirmar experiencia actual.                                                                                                                 | Cerrado            |
| 3  | **12 ago**      | La sesión indica que expiró y es necesario recargar la página para volver a obtener los datos.                            | ⚪ Pendiente de confirmar         | No está confirmado si Cristian ya corrigió el problema o si continúa ocurriendo.                                                                  | Confirmar con los usuarios si actualmente sigue ocurriendo.                                                                                   | Definir            |
| 4  | **12 ago**      | Separar / mejorar la organización del Inventario.                                                                         | 🔵 Pendiente de validación       | Se realizó una actualización importante del módulo de Inventario.                                                                                 | Revisar con usuarios la nueva experiencia, organización y facilidad de navegación.                                                            | Validar            |
| 5  | **12 ago**      | Poder imprimir listas de Inventario.                                                                                      | 🔵 Pendiente de validación       | Se entregó funcionalidad de **exportación a Excel el 11 de septiembre** como alternativa para trabajar e imprimir listados.                       | Confirmar si Excel cubre la necesidad o requieren impresión/PDF directo desde Vetflow.                                                        | Validar            |
| 6  | **2 sep**       | En el dashboard aparecen como “Turnos de hoy” citas correspondientes al día siguiente, generando confusión.               | 🟡 En ejecución                  | Problema identificado y pendiente de finalizar corrección.                                                                                        | Confirmar comportamiento esperado del dashboard.                                                                                              | Definir            |
| 7  | **11 sep**      | Se desplegó una versión amplia con nuevas funcionalidades de Inventario, Ventas, Compras, Configuración, Catálogos, etc.  | 🔵 Pendiente de validación       | Se solicita una revisión integral con el equipo veterinario.                                                                                      | Recoger feedback de experiencia, comodidad, bugs y funcionalidades faltantes.                                                                 | Alta               |
| 8  | **12 sep**      | En Ventas, el selector de propietarios no mostraba todos los propietarios y era difícil navegar.                          | ✅ Resuelto                       | Corregido el **12 de septiembre**. Ahora incluye búsqueda, orden alfabético y paginación.                                                         | Confirmar experiencia actual.                                                                                                                 | Cerrado            |
| 9  | **12 sep**      | Jenny reportó que no podía modificar un precio; posteriormente identificó que estaba utilizando coma en el valor.         | 🟠 Mejora UX pendiente           | No es un bloqueo funcional confirmado, pero puede mejorarse la experiencia para aceptar formatos habituales o explicar mejor el formato esperado. | Preguntar si este problema ocurre frecuentemente y definir si vale la pena priorizar una mejora.                                              | Media/Baja         |
| 10 | **19 sep**      | En una venta se necesita registrar que una parte del pago fue en efectivo y otra mediante otro medio de pago.             | 🟠 Pendiente de definición       | Se debe revisar el flujo de **pago dividido / múltiples formas de pago**.                                                                         | Definir cómo desean registrar, visualizar y reportar los pagos divididos.                                                                     | Definir            |
| 11 | **19 sep**      | Agregar servicios: Internación, Ecografía, Corte de uñas, Glicemia, Dosis, Tratamientos y Cirugías.                       | ✅ Resuelto                       | Servicios agregados por el administrador el **19 de septiembre**.                                                                                 | Confirmar si falta algún servicio adicional.                                                                                                  | Cerrado            |
| 12 | **19 sep**      | Corregir tilde en el apellido de Juliana.                                                                                 | ✅ Resuelto                       | Cambio aplicado el mismo **19 de septiembre**. Los nombres pueden editarse desde Configuración.                                                   | Recordar al equipo que estos nombres pueden modificarse desde la aplicación.                                                                  | Cerrado            |
| 13 | **19 sep**      | Verificar “otras tildes” pendientes.                                                                                      | 🟠 Requiere información          | No se indicaron específicamente los nombres o textos que deben corregirse.                                                                        | Los usuarios deben indicar exactamente qué textos presentan errores.                                                                          | Esperando usuarios |
| 14 | **19 sep**      | Mostrar en Propietarios —y posiblemente Mascotas— un indicador que permita saber si el cliente está al día o tiene deuda. | 🟠 Pendiente de definición       | Requiere diseñar la relación entre propietario, ventas, pagos y saldo pendiente.                                                                  | Definir dónde debe mostrarse, qué significa “deuda” y si aplica a propietario, mascota o ambos.                                               | Definir            |
| 15 | **19 sep**      | Los veterinarios no podían configurar/editar servicios; solicitan mayores permisos.                                       | 🟡 En ejecución                  | Ya se habilitó la **edición de servicios para médicos veterinarios**. Sigue pendiente definir la matriz completa de roles y permisos.             | Definir permisos de Administrador, Médico Veterinario y Secretaria. Confirmar creación, edición, activación/inactivación y demás operaciones. | Alta               |
| 16 | **19 sep**      | Crear un nuevo tipo de usuario **Secretaria** para Jenny.                                                                 | 🟠 Pendiente de definición       | El rol todavía no existe. Primero debe definirse qué módulos y acciones podrá utilizar.                                                           | Completar matriz de permisos de Secretaria.                                                                                                   | Alta               |
| 17 | **Actual**      | Continuar integración de Vetflow con **ARCA** para completar ventas y facturación.                                        | 🟡 En planificación / desarrollo | Primero necesitamos tener **Compras y Ventas estables y validadas por los usuarios**.                                                             | Definir qué bugs o cambios son bloqueantes antes de continuar con ARCA.                                                                       | Estratégica        |

---

# Puntos que requieren decisión del equipo veterinario

## 1. Roles y permisos

Debemos definir por escrito qué podrá hacer cada perfil:

- Administrador.
- Médico Veterinario.
- Secretaria.

Especialmente en:

- Servicios.
- Agenda.
- Propietarios.
- Pacientes.
- Inventario.
- Compras.
- Ventas.
- Pagos.
- Configuración.
- Catálogos.

---

## 2. Pago dividido en ventas

Definir el comportamiento esperado cuando, por ejemplo:

**Venta: ARS 100.000**

- ARS 40.000 en efectivo.
- ARS 60.000 por transferencia.

Debemos confirmar cómo desean registrar, consultar y reportar estos pagos.

---

## 3. Indicador de deuda

Definir:

- si el indicador aparece en Propietarios;
- si también debe aparecer en Mascotas;
- qué condición determina “Al día” o “Con deuda”;
- si se necesita visualizar directamente el monto pendiente.

---

## 4. Inventario

Validar la nueva versión y responder:

- ¿La organización actual es clara?
- ¿Es fácil encontrar productos?
- ¿El dashboard es útil?
- ¿La exportación Excel cubre la necesidad de impresión?
- ¿Qué información debería verse más fácilmente?

---

## 5. Sesiones expiradas

Confirmar si actualmente continúa ocurriendo:

> “La sesión expiró y debo recargar la página para volver a ver los datos”.

Si continúa, registrar:

- usuario;
- pantalla;
- acción que estaba realizando;
- hora aproximada;
- frecuencia del problema.

---

# Prioridad a definir en la reunión

Proponemos clasificar los pendientes en:

### Prioridad 1 — Bloqueantes

Problemas que impiden realizar correctamente una tarea diaria o bloquean el avance hacia facturación/ARCA.

### Prioridad 2 — Importantes

Mejoras que afectan significativamente la productividad o facilidad de uso.

### Prioridad 3 — Mejoras

Ajustes visuales, comodidad, textos o mejoras no bloqueantes.

---

# Objetivo al finalizar la reunión

Salir de la reunión con:

1. Bugs actuales confirmados.
2. Solicitudes que ya pueden considerarse cerradas.
3. Matriz definida de roles y permisos.
4. Alcance del nuevo rol Secretaria.
5. Priorización acordada de los pendientes.
6. Confirmación de qué funcionalidades actuales de Inventario, Compras y Ventas están aprobadas por los usuarios.
7. Lista de cambios bloqueantes antes de continuar con la integración completa con ARCA.