# Vetflow — Backlog, priorización y alcance funcional

**Fecha:** 4 de julio de 2026  
**Objetivo del documento:** ordenar el feedback recibido, convertirlo en backlog accionable y priorizar entregas que generen valor rápido a la veterinaria sin comprometer estabilidad del sistema.

---

## 1. Resumen básico de funcionalidades desarrolladas hasta el momento

> Este resumen está construido con base en el estado conocido del proyecto y el feedback reciente. Debe actualizarse si el repositorio tiene módulos adicionales no contemplados aquí.

### Funcionalidades principales existentes

1. **Gestión de pacientes**
   - Listado de pacientes.
   - Detalle individual de paciente.
   - Búsqueda global de pacientes.
   - Redirección desde resultado de búsqueda al detalle del paciente.
   - Vista de historia clínica del paciente.
   - Exportación / vista previa de historia clínica en PDF.
   - Selector de tamaño de hoja para PDF: carta, A4 y legal/oficio.

2. **Gestión de propietarios**
   - Listado de propietarios.
   - Búsqueda global de propietarios.
   - Resultado actual: al seleccionar un propietario desde el buscador global, redirige al listado de propietarios y no al detalle del propietario seleccionado.

3. **Inventario / stock**
   - Registro de medicamentos / productos en stock.
   - Campos existentes de IVA en compra e IVA en venta, modificables/editables.
   - Necesidad detectada: simplificar cálculo de precio de venta para alimentos.

4. **Frontend operativo**
   - Detalle de paciente funcional.
   - Integración con servicios de exportación clínica.
   - Vista previa responsive de PDF mediante iframe.
   - Manejo de estados de carga/error.
   - Limpieza de object URLs al reemplazar, cerrar visor o desmontar componente.

5. **Trabajo en curso / próximo por otro desarrollador**
   - Mejoras en inventario.
   - Usuario superadmin para gestión de usuarios.
   - Métricas globales.

---

## 2. Temas principales a trabajar

### T1 — Corrección buscador global para propietarios

**Problema:**  
El buscador global funciona correctamente para pacientes, pero no para propietarios. Al seleccionar un propietario, el sistema redirige al listado general de propietarios y no al detalle del propietario seleccionado.

**Objetivo:**  
Que todos los resultados del buscador global tengan comportamiento consistente: si el usuario selecciona un paciente, va al detalle del paciente; si selecciona un propietario, va al detalle del propietario.

**Tipo:** bug / mejora UX.  
**Complejidad estimada:** baja.  
**Valor:** alto, porque elimina fricción diaria.  
**Riesgo:** bajo.

**Criterios de aceptación:**
- Buscar propietario por nombre, apellido, documento, teléfono o email, según campos disponibles.
- Mostrar propietarios coincidentes.
- Al hacer clic en un propietario, navegar a `/owners/:ownerId` o ruta equivalente real del proyecto.
- Si no existe vista detalle de propietario, crear definición mínima o redirigir a una vista filtrada con foco claro en el propietario seleccionado.
- Mantener comportamiento actual de búsqueda de pacientes.
- Agregar prueba manual y, si existe infraestructura, test unitario/e2e del flujo.

---

### T2 — Rediseño de formulario de alimentos en inventario

**Problema:**  
Actualmente existen campos separados de IVA de compra e IVA de venta. El feedback indica que, para alimentos, el flujo real deseado es más simple:

- Compra sin IVA.
- IVA fijo 21%.
- % de ganancia.
- Precio de venta con IVA.

El usuario solo debería ingresar:

- Compra sin IVA.
- % de ganancia.

Y el sistema debería calcular automáticamente:

- IVA fijo 21%.
- Precio de venta con IVA.

**Objetivo:**  
Reducir errores y acelerar carga de alimentos en stock.

**Tipo:** mejora funcional / UX / cálculo de negocio.  
**Complejidad estimada:** media.  
**Valor:** alto.  
**Riesgo:** medio, porque involucra lógica de precios y operación fiscal/comercial.

**Recomendación:**  
Antes de implementar, diseñar mockup y validarlo con usuarios. Este cambio afecta la forma en que calculan margen, precio final y actualización de stock.

**Fórmula base propuesta:**

```text
costo_sin_iva = input usuario
iva = 21%
ganancia_pct = input usuario
precio_venta_sin_iva = costo_sin_iva * (1 + ganancia_pct / 100)
precio_venta_con_iva = precio_venta_sin_iva * 1.21
```

**Punto a validar:**  
Confirmar si el % de ganancia se aplica sobre compra sin IVA o sobre compra con IVA. Operativamente, lo más limpio suele ser aplicar margen sobre costo sin IVA y luego sumar IVA, pero debe validarse con la veterinaria/contador.

**Criterios de aceptación:**
- En creación de alimento, mostrar campos:
  - Compra sin IVA: editable.
  - IVA: fijo 21%, visible pero no editable por defecto.
  - % de ganancia: editable.
  - Precio de venta con IVA: calculado automáticamente.
- Al cambiar compra sin IVA o % ganancia, actualizar precio final en tiempo real.
- Definir si el precio final puede editarse manualmente y recalcular margen inverso.
- Guardar valores necesarios para auditoría: costo sin IVA, IVA aplicado, margen, precio final.
- Mantener compatibilidad con productos existentes.
- No romper medicamentos u otros tipos de producto si tienen reglas distintas.

---

### T3 — Agrupación de alimentos por marca y actualización masiva por porcentaje

**Problema:**  
Los proveedores/marcas suelen actualizar precios por porcentaje general para todos los productos de una misma marca. Hoy actualizar producto por producto es lento.

**Objetivo:**  
Permitir gestión de alimentos por marca y actualización masiva de precios por porcentaje.

**Tipo:** nueva funcionalidad inventario.  
**Complejidad estimada:** media.  
**Valor:** alto.  
**Riesgo:** medio, porque requiere control de cambios masivos y prevención de errores.

**Funcionalidad esperada:**
- Campo obligatorio/opcional de marca para alimentos.
- Filtro/agrupación por marca.
- Acción: “Actualizar precios por marca”.
- Ingreso de porcentaje de aumento/disminución.
- Previsualización antes de aplicar.
- Confirmación final.
- Registro/auditoría del cambio.

**Criterios de aceptación:**
- Listar alimentos agrupados por marca.
- Permitir seleccionar una marca.
- Aplicar ajuste porcentual sobre costo de compra, precio de venta o ambos, según definición validada.
- Mostrar antes/después por producto antes de confirmar.
- Permitir cancelar sin cambios.
- Guardar historial: usuario, fecha, marca, porcentaje aplicado, productos afectados, valores anteriores y nuevos.

**Recomendación de diseño:**  
No aplicar cambios masivos directamente sin vista previa. El riesgo de errores económicos es alto.

---

### T4 — Evaluación e integración de facturación electrónica ARCA

**Problema:**  
Actualmente la veterinaria factura en ARCA manualmente. Tienen 3 médicos/emisores diferentes, cada uno con usuario y clave. Para emitir deben cambiar de cuenta, completar datos repetitivos y configurar campos manualmente.

**Objetivo:**  
Evaluar y eventualmente desarrollar un módulo de facturación en Vetflow para:

- Seleccionar médico/emisor.
- Reutilizar datos existentes: propietario, paciente, dirección, teléfono, conceptos, productos/servicios vendidos.
- Completar solo campos mínimos necesarios.
- Emitir comprobante electrónico o dejar la factura preparada para emisión.
- Reducir tiempo operativo y errores.

**Viabilidad inicial:** técnicamente viable, pero requiere spike técnico-fiscal.  
ARCA mantiene documentación oficial de web services SOAP de factura electrónica. El servicio WSFEv1 aplica para comprobantes A, B, C y M sin detalle de ítem; WSMTXCA se usa para comprobantes A/B con detalle de ítems. La autenticación ante WSAA requiere certificado digital X.509 emitido/autorizado para operar con ARCA.

**Fuentes oficiales consultadas:**
- ARCA / AFIP — Webservices de factura electrónica: https://www.afip.gob.ar/ws/documentacion/ws-factura-electronica.asp
- ARCA / AFIP — WSAA autenticación: https://www.afip.gob.ar/ws/documentacion/wsaa.asp
- ARCA / AFIP — Certificados para testing/homologación: https://www.afip.gob.ar/ws/documentacion/certificados.asp
- ARCA / AFIP — Arquitectura web services SOAP: https://www.afip.gob.ar/ws/documentacion/

**Complejidad estimada:** alta.  
**Valor:** muy alto.  
**Riesgo:** alto por dependencia fiscal, certificados, credenciales, ambientes, CUITs, puntos de venta, tipos de comprobante y responsabilidad legal/contable.

**Alcance recomendado por fases:**

#### Fase 0 — Discovery fiscal/técnico
- Confirmar régimen fiscal de cada médico/emisor.
- Confirmar CUIT, condición IVA, punto/s de venta, tipos de comprobante usados.
- Confirmar si emiten factura A, B, C, notas de crédito/débito.
- Confirmar si requieren detalle de ítems o factura simplificada por concepto.
- Validar con contador de la veterinaria.
- Revisar si conviene integración directa ARCA o usar proveedor/API intermedia.

#### Fase 1 — Prototipo interno en homologación
- Crear módulo técnico aislado para autenticación WSAA.
- Obtener token/sign.
- Consultar último comprobante autorizado.
- Solicitar CAE en entorno de testing.
- Registrar respuesta y errores.

#### Fase 2 — MVP de facturación en Vetflow
- Seleccionar médico/emisor.
- Seleccionar propietario/paciente.
- Prellenar datos conocidos.
- Cargar concepto/importes.
- Vista previa antes de emitir.
- Emitir comprobante.
- Guardar CAE, vencimiento CAE, número, tipo, punto de venta, total.
- Generar PDF o comprobante imprimible.

#### Fase 3 — Operación avanzada
- Notas de crédito/débito.
- Reenvío por email/WhatsApp.
- Anulación lógica interna.
- Reportes fiscales.
- Conciliación con ventas/caja.

**Decisión recomendada:**  
No incluir facturación ARCA en el sprint inmediato de entrega rápida. Incluir un spike técnico de 1 sprint corto y tomar decisión con evidencia.

---

### T5 — Módulo de ventas, turnos, cierres y conciliación

**Problema:**  
Hoy registran ventas diarias en Excel y luego hacen conciliación diaria/semanal con cuentas bancarias. Esto genera trabajo duplicado, errores y poca trazabilidad.

**Objetivo:**  
Crear un módulo de control de ventas que permita registrar ventas, separar por turno/fecha/método de pago, cerrar caja diaria/semanal y detectar diferencias con cuentas bancarias.

**Tipo:** nuevo módulo operativo.  
**Complejidad estimada:** alta si incluye conciliación bancaria automática; media si inicia como registro y cierre manual.  
**Valor:** muy alto.  
**Riesgo:** medio/alto por manejo de dinero, reportes y cierres.

**MVP recomendado:**
- Registro manual de venta.
- Fecha/hora automática.
- Usuario/turno responsable.
- Método de pago: efectivo, transferencia, débito, crédito, Mercado Pago u otros reales.
- Cliente/propietario opcional.
- Paciente opcional.
- Productos/servicios vendidos.
- Total.
- Observaciones.
- Estado: registrada, anulada, corregida.
- Cierre diario por turno.
- Cierre diario general.
- Resumen semanal.
- Exportación a Excel/CSV.

**No incluir en MVP inicial:**
- Integración bancaria automática.
- Conciliación automática con bancos.
- Facturación fiscal completa.
- Contabilidad avanzada.

**Criterios de aceptación MVP:**
- Registrar venta en menos de 30 segundos.
- Filtrar por fecha, turno, usuario, método de pago.
- Ver total vendido por día y por método de pago.
- Generar cierre diario con diferencia declarada.
- Exportar cierre.
- Ver historial de correcciones/anulaciones.

---

## 3. Priorización recomendada

### Método usado

Se prioriza con lógica de valor rápido:

1. Alto impacto diario.
2. Baja/mediana complejidad.
3. Bajo riesgo de romper operación.
4. Dependencias claras.
5. Entregable validable por usuarios.

### Tabla de priorización

| Prioridad | Tema | Tipo | Valor | Complejidad | Riesgo | Recomendación |
|---|---|---|---:|---:|---:|---|
| P0 | Buscador global propietarios | Bug/UX | Alto | Baja | Bajo | Hacer primero |
| P1 | Mockup flujo alimentos: costo, IVA 21%, margen, precio final | UX/negocio | Alto | Baja-media | Medio | Diseñar y validar antes de código |
| P1 | Ajuste formulario alimentos validado | Inventario | Alto | Media | Medio | Implementar luego del mockup |
| P1 | Marca en alimentos + agrupación por marca | Inventario | Alto | Media | Medio | Desarrollar con vista previa |
| P2 | Actualización masiva de precios por marca | Inventario | Alto | Media | Medio-alto | Requiere auditoría y confirmación |
| P2 | Módulo ventas MVP | Nuevo módulo | Muy alto | Media-alta | Medio | Iniciar con registro/cierre manual |
| P3 | Spike facturación ARCA | Investigación técnica | Muy alto | Media | Alto | Hacer antes de prometer desarrollo |
| P4 | Facturación ARCA MVP | Integración fiscal | Muy alto | Alta | Alto | Solo tras spike + validación contador |

---

## 4. Backlog inicial recomendado

### Épica A — Experiencia de búsqueda y navegación

#### A1. Corregir navegación del buscador global para propietarios
- **Prioridad:** P0
- **Responsable sugerido:** frontend
- **Dependencia:** ruta/vista de detalle propietario
- **Resultado esperado:** selección de propietario lleva al detalle correcto.

#### A2. Revisar consistencia de resultados globales
- **Prioridad:** P2
- **Objetivo:** asegurar que pacientes, propietarios y futuros resultados tengan patrón común.
- **Resultado esperado:** componente de búsqueda preparado para más entidades.

---

### Épica B — Inventario de alimentos

#### B1. Diseñar mockup de formulario alimento
- **Prioridad:** P1
- **Resultado esperado:** wireframe validado con veterinarios.

#### B2. Validar fórmula de precio
- **Prioridad:** P1
- **Resultado esperado:** regla confirmada: margen sobre costo sin IVA o con IVA.

#### B3. Implementar formulario alimento con cálculo automático
- **Prioridad:** P1
- **Resultado esperado:** precio de venta con IVA calculado en tiempo real.

#### B4. Agregar marca a alimentos
- **Prioridad:** P1
- **Resultado esperado:** alimentos pueden filtrarse/agruparse por marca.

#### B5. Implementar actualización masiva por marca con preview
- **Prioridad:** P2
- **Resultado esperado:** aplicar porcentaje a productos de una marca con confirmación.

#### B6. Historial de cambios de precio
- **Prioridad:** P2
- **Resultado esperado:** trazabilidad completa de ajustes.

---

### Épica C — Ventas, caja y conciliación

#### C1. Levantar flujo actual de Excel
- **Prioridad:** P1
- **Resultado esperado:** entender columnas, métodos de pago, cierres y responsables.

#### C2. Diseñar modelo de venta
- **Prioridad:** P1
- **Resultado esperado:** estructura clara para venta, detalle, método de pago, turno y cierre.

#### C3. Crear módulo ventas MVP
- **Prioridad:** P2
- **Resultado esperado:** registrar ventas y consultar listado por fecha/turno.

#### C4. Crear cierre diario por turno
- **Prioridad:** P2
- **Resultado esperado:** totales por método de pago y responsable.

#### C5. Crear cierre semanal
- **Prioridad:** P2
- **Resultado esperado:** consolidado semanal exportable.

#### C6. Conciliación manual asistida
- **Prioridad:** P3
- **Resultado esperado:** cargar/importar movimientos o totales bancarios y comparar contra ventas registradas.

---

### Épica D — Facturación ARCA

#### D1. Discovery fiscal con veterinarios/contador
- **Prioridad:** P3
- **Resultado esperado:** mapa de emisores, comprobantes, puntos de venta, régimen y necesidades.

#### D2. Spike técnico ARCA en homologación
- **Prioridad:** P3
- **Resultado esperado:** prueba real de autenticación y emisión en testing.

#### D3. Decisión build vs proveedor intermedio
- **Prioridad:** P3
- **Resultado esperado:** elegir integración directa ARCA o API intermedia.

#### D4. Diseño MVP facturación
- **Prioridad:** P4
- **Resultado esperado:** flujo validado antes de desarrollo.

#### D5. Implementar facturación MVP
- **Prioridad:** P4
- **Resultado esperado:** emisión controlada desde Vetflow.

---

## 5. Roadmap sugerido de entregas

### Sprint 1 — Valor rápido y base de inventario

**Meta:** resolver fricción inmediata y validar rediseño de inventario antes de codificar fuerte.

**Incluye:**
- A1 Corregir buscador global propietarios.
- B1 Mockup formulario alimento.
- B2 Validación fórmula de precio.
- B4 Análisis de datos para marca en alimentos.
- C1 Levantar flujo actual de Excel de ventas.

**Entregables:**
- Buscador corregido.
- Mockup validable.
- Documento de reglas de precio.
- Mapa del Excel actual de ventas.

---

### Sprint 2 — Inventario operativo

**Meta:** entregar mejoras concretas en alimentos.

**Incluye:**
- B3 Implementar formulario alimento con cálculo automático.
- B4 Agregar marca a alimentos.
- Vista de alimentos filtrable/agrupable por marca.

**Entregables:**
- Formulario actualizado.
- Productos de alimento con marca.
- Listado agrupado por marca.

---

### Sprint 3 — Actualización masiva y auditoría

**Meta:** permitir aumentos por marca de forma segura.

**Incluye:**
- B5 Actualización masiva por marca con preview.
- B6 Historial de cambios de precio.

**Entregables:**
- Ajuste porcentual por marca.
- Confirmación antes de aplicar.
- Historial/auditoría.

---

### Sprint 4 — Ventas MVP

**Meta:** reemplazar gradualmente el Excel diario.

**Incluye:**
- C2 Modelo de venta.
- C3 Registro/listado de ventas.
- C4 Cierre diario por turno.

**Entregables:**
- Registro de ventas.
- Filtros básicos.
- Cierre diario por turno.
- Exportación simple.

---

### Sprint 5 — Cierre semanal y conciliación manual asistida

**Meta:** facilitar validación semanal con cuentas bancarias.

**Incluye:**
- C5 Cierre semanal.
- C6 Conciliación manual asistida.

**Entregables:**
- Reporte semanal.
- Comparación ventas vs totales bancarios/manuales.
- Identificación de diferencias.

---

### Sprint paralelo / técnico — ARCA discovery + spike

**Meta:** determinar factibilidad real antes de comprometer alcance.

**Incluye:**
- D1 Discovery fiscal.
- D2 Spike técnico homologación.
- D3 Decisión build vs proveedor.

**Entregables:**
- Documento técnico-fiscal.
- Prueba de autenticación/emisión en homologación o bloqueo documentado.
- Recomendación final: construir directo, usar proveedor o postergar.

---

## 6. Recomendación ejecutiva

Para entregar valor rápido y mantener orden de desarrollo:

1. **Primero corregir buscador de propietarios.** Es pequeño, visible y mejora la percepción de avance.
2. **Luego validar mockup de inventario antes de implementar.** El cálculo de precio afecta dinero; no debe asumirse sin confirmación.
3. **Después implementar marca + actualización por porcentaje.** Es una mejora de alto valor operativo.
4. **En paralelo levantar flujo de ventas actual.** El módulo de ventas debe copiar lo que ya hacen bien en Excel, no inventar un proceso desde cero.
5. **Facturación ARCA debe ir como spike separado.** Es viable, pero fiscalmente sensible y técnicamente más riesgoso.

