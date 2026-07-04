# Vetflow — Plan de trabajo, validación con usuarios y preguntas de alcance

**Fecha:** 4 de julio de 2026  
**Objetivo del documento:** servir como guía práctica para reuniones con veterinarios, definición de alcance, diseño de mockups y ejecución ordenada por sprint.

---

## 1. Principios de desarrollo para esta etapa

1. **Entregar valor visible rápido.**
   - Corregir primero problemas pequeños pero molestos.
   - Evitar que todos los esfuerzos se vayan a módulos grandes como facturación.

2. **Validar flujos económicos antes de codificar.**
   - Inventario, precios, ventas y facturación impactan dinero.
   - Todo cálculo debe validarse con usuarios y, cuando aplique, contador.

3. **Construir MVP antes que sistema completo.**
   - Ventas: primero registro + cierre manual.
   - Facturación: primero spike técnico.
   - Conciliación: primero comparación asistida, no integración bancaria automática.

4. **Evitar cambios masivos sin auditoría.**
   - Actualizaciones por marca deben tener preview, confirmación e historial.

5. **Diseñar pensando en operación real.**
   - El sistema debe reducir pasos, no agregar carga administrativa.

---

## 2. Plan de trabajo recomendado

### Fase 1 — Orden y quick wins

**Objetivo:** resolver fricción inmediata y dejar claro el alcance de inventario.

**Tareas:**
- Corregir redirección del buscador global para propietarios.
- Revisar si existe detalle de propietario.
- Diseñar mockup del formulario de alimento.
- Validar fórmula de precio con veterinarios.
- Solicitar Excel actual de ventas para modelar el módulo de ventas.

**Resultado esperado:**
- Mejora visible en buscador.
- Inventario listo para implementación con menos riesgo.
- Ventas entendidas desde el flujo real actual.

---

### Fase 2 — Inventario de alimentos

**Objetivo:** simplificar carga de alimentos y permitir administración por marca.

**Tareas:**
- Implementar campos:
  - Compra sin IVA.
  - IVA fijo 21%.
  - % de ganancia.
  - Precio de venta con IVA.
- Implementar cálculo automático.
- Agregar campo marca.
- Agregar filtros por marca.
- Crear vista agrupada por marca.

**Resultado esperado:**
- Menos errores al cargar alimentos.
- Mejor control por proveedor/marca.

---

### Fase 3 — Actualización masiva por marca

**Objetivo:** actualizar precios de una marca completa en segundos, pero con seguridad.

**Tareas:**
- Acción “Actualizar precios por marca”.
- Selección de marca.
- Ingreso de porcentaje.
- Selección de base de cálculo:
  - Aumentar costo de compra.
  - Aumentar precio de venta.
  - Recalcular venta desde costo + margen.
- Preview antes/después.
- Confirmación final.
- Historial del cambio.

**Resultado esperado:**
- Ahorro operativo real.
- Menor riesgo de errores económicos.

---

### Fase 4 — Ventas y cierres

**Objetivo:** reemplazar gradualmente el Excel diario.

**MVP sugerido:**
- Registro de venta.
- Fecha/hora.
- Turno.
- Usuario responsable.
- Método de pago.
- Productos/servicios.
- Total.
- Observaciones.
- Estado: activa, anulada, corregida.
- Cierre diario por turno.
- Cierre semanal.
- Exportación.

**Resultado esperado:**
- Ventas centralizadas en Vetflow.
- Cierres más rápidos.
- Menos dependencia de Excel.

---

### Fase 5 — Facturación ARCA

**Objetivo:** determinar si conviene construir integración directa, usar proveedor intermedio o mantener flujo externo con mejoras parciales.

**Primero hacer spike técnico-fiscal.**

**Validaciones necesarias:**
- Acceso a entorno de homologación.
- Certificados digitales.
- CUITs emisores.
- Puntos de venta.
- Tipo de comprobantes.
- Flujo de CAE.
- PDF/comprobante.
- Responsabilidad fiscal.

**Resultado esperado:**
- Decisión informada antes de comprometer presupuesto/desarrollo.

---

## 3. Preguntas para veterinarios — Buscador y propietarios

1. Cuando buscan un propietario, ¿qué esperan ver al entrar al detalle?
   - Datos personales.
   - Teléfono/email.
   - Dirección.
   - Mascotas asociadas.
   - Historial de visitas.
   - Deudas/facturas/ventas.

2. ¿Actualmente existe una pantalla de detalle de propietario o solo listado?

3. ¿Qué datos usan más para buscar propietarios?
   - Nombre.
   - Apellido.
   - DNI/CUIT.
   - Teléfono.
   - Email.
   - Nombre del paciente/mascota.

4. Cuando seleccionan propietario, ¿quieren ir al propietario o al listado de sus pacientes?

5. ¿Un propietario puede tener múltiples mascotas/pacientes?

6. ¿Necesitan crear paciente desde el detalle del propietario?

---

## 4. Preguntas para veterinarios — Inventario de alimentos

### Sobre cálculo de precio

1. ¿El % de ganancia se aplica sobre compra sin IVA o sobre compra con IVA?

2. ¿El IVA de alimentos es siempre 21% para todos los productos?

3. ¿Hay alimentos con IVA diferente o exentos?

4. ¿El precio de venta final debe poder editarse manualmente?

5. Si editan manualmente el precio de venta, ¿el sistema debe recalcular el % de ganancia?

6. ¿Redondean precios?
   - Sin redondeo.
   - Al peso más cercano.
   - A múltiplos de 10.
   - A múltiplos de 50/100.

7. ¿Quieren guardar precio anterior para comparar aumentos?

8. ¿Necesitan fecha de última actualización de precio?

9. ¿Necesitan proveedor además de marca?

10. ¿Un mismo alimento puede tener diferentes presentaciones/tamaños?
    - Ejemplo: 1 kg, 3 kg, 7.5 kg, 15 kg.

### Sobre marcas

11. ¿La marca debe ser obligatoria para alimentos?

12. ¿Quién puede crear nuevas marcas?

13. ¿Quieren evitar marcas duplicadas por diferencias de escritura?
    - Ejemplo: Royal Canin / RoyalCanin / royal canin.

14. ¿Los aumentos por marca se aplican a todos los productos o debe poder excluirse alguno?

15. Cuando una marca aumenta precios, ¿aumenta el costo de compra, el precio de venta o ambos?

16. ¿El margen de ganancia se mantiene igual después del aumento?

17. ¿Necesitan cargar lista de precios del proveedor por Excel?

---

## 5. Preguntas para veterinarios — Ventas, turnos y cierres

### Sobre registro de ventas

1. ¿Qué columnas tiene actualmente el Excel de ventas?

2. ¿Qué datos son obligatorios por cada venta?

3. ¿Registran ventas por productos, servicios o ambos?

4. ¿Una venta puede tener varios métodos de pago?
   - Ejemplo: parte efectivo y parte transferencia.

5. ¿Qué métodos de pago usan?
   - Efectivo.
   - Transferencia.
   - Débito.
   - Crédito.
   - Mercado Pago.
   - Otro.

6. ¿Registran quién realizó la venta?

7. ¿Registran turno?

8. ¿Cuántos turnos hay por día?

9. ¿Qué pasa si una venta se corrige o anula?

10. ¿Necesitan motivo de anulación/corrección?

### Sobre cierres

11. ¿El cierre se hace por turno, por día o ambos?

12. ¿Quién hace el cierre?

13. ¿Qué debe mostrar el cierre diario?
    - Total general.
    - Total por método de pago.
    - Total por usuario.
    - Total por turno.
    - Ventas anuladas.
    - Diferencias.

14. ¿El cierre puede editarse después de cerrado?

15. Si se edita, ¿quién puede hacerlo?

16. ¿Necesitan firma/aprobación de cierre?

17. ¿Necesitan imprimir o exportar cierre?

### Sobre conciliación

18. ¿Con qué bancos/cuentas concilian?

19. ¿La conciliación se hace con movimientos reales o con totales del día?

20. ¿Pueden exportar movimientos bancarios en Excel/CSV?

21. ¿Qué diferencias suelen aparecer?
    - Transferencias no identificadas.
    - Pagos duplicados.
    - Ventas no registradas.
    - Errores de método de pago.
    - Comisiones.

22. ¿Quieren conciliación automática o primero una comparación manual asistida?

---

## 6. Preguntas para veterinarios/contador — Facturación ARCA

### Sobre emisores

1. ¿Cuántos médicos/emisores facturan actualmente?

2. ¿Cada médico factura con CUIT propio?

3. ¿Todos usan el mismo punto de venta o cada uno tiene punto de venta diferente?

4. ¿Qué condición fiscal tiene cada emisor?
   - Monotributista.
   - Responsable inscripto.
   - Exento.
   - Otro.

5. ¿Quién debe autorizar técnicamente el uso de web services?

6. ¿Tienen certificado digital de ARCA para web services?

7. ¿Tienen acceso a homologación/testing?

### Sobre comprobantes

8. ¿Qué tipos de comprobantes emiten?
   - Factura A.
   - Factura B.
   - Factura C.
   - Nota de crédito.
   - Nota de débito.

9. ¿Necesitan detalle de ítems en la factura o solo concepto general?

10. ¿Facturan productos, servicios médicos o ambos?

11. ¿Manejan IVA discriminado?

12. ¿Qué alícuotas de IVA usan?

13. ¿Emiten factura a consumidor final, empresas o ambos?

14. ¿Qué datos del cliente son obligatorios según sus casos reales?

15. ¿El paciente/mascota debe aparecer en la factura o solo internamente?

### Sobre operación

16. ¿La factura se genera al momento de registrar la venta o después?

17. ¿Una venta puede quedar registrada sin factura?

18. ¿Quién puede emitir factura?

19. ¿Quién puede anular o generar nota de crédito?

20. ¿Necesitan enviar la factura por email o WhatsApp?

21. ¿Necesitan descargar PDF?

22. ¿Qué pasa si ARCA está caído o rechaza la factura?

23. ¿Quieren que Vetflow guarde el comprobante aunque falle la emisión?

24. ¿El contador necesita acceso/reportes?

---

## 7. Mockup funcional sugerido — Alimentos

### Pantalla: Crear / editar alimento

```text
Información básica
--------------------------------------------------
Nombre del producto:        [___________________]
Marca:                      [Seleccionar / Crear]
Presentación:               [Ej. 15 kg]
Código/SKU:                 [___________________]
Stock actual:               [____]
Stock mínimo:               [____]

Precio
--------------------------------------------------
Compra sin IVA:             [$ ________]  editable
IVA:                        [21%]         fijo/no editable
% de ganancia:              [___ %]       editable
Precio venta con IVA:       [$ ________]  calculado

[ ] Permitir ajuste manual del precio final

Resumen de cálculo
--------------------------------------------------
Costo sin IVA:              $ X
Ganancia aplicada:          $ X
Subtotal venta sin IVA:     $ X
IVA venta 21%:              $ X
Precio final:               $ X

[Guardar alimento]
```

### Comportamiento recomendado

- Al modificar compra sin IVA, recalcular precio final.
- Al modificar % ganancia, recalcular precio final.
- Si se permite editar precio final, recalcular margen estimado.
- Mostrar advertencia si el margen queda negativo o demasiado bajo.
- Guardar historial si cambia el precio.

---

## 8. Mockup funcional sugerido — Actualización por marca

### Pantalla: Actualizar precios por marca

```text
Marca:                      [Seleccionar marca]
Productos encontrados:       34

Aplicar ajuste sobre:        ( ) Costo de compra
                             ( ) Precio de venta
                             ( ) Recalcular venta manteniendo margen

Porcentaje de ajuste:        [___ %]
Fecha efectiva:              [Hoy]
Motivo:                      [Aumento proveedor / ajuste interno / otro]

[Previsualizar cambios]
```

### Preview

```text
Producto              Precio actual     Precio nuevo      Diferencia
--------------------------------------------------------------------
Alimento A 15 kg      $ 10.000          $ 11.200          +12%
Alimento B 7.5 kg     $ 6.000           $ 6.720           +12%
Alimento C 3 kg       $ 3.000           $ 3.360           +12%

[Cancelar] [Confirmar actualización]
```

### Reglas de seguridad

- No aplicar sin preview.
- No aplicar sin confirmación.
- Guardar historial.
- Permitir exportar cambios.
- Restringir permiso a administrador/superadmin.

---

## 9. Mockup funcional sugerido — Registro de venta

```text
Nueva venta
--------------------------------------------------
Fecha/hora:                 [Automático]
Turno:                      [Mañana/Tarde/Noche]
Usuario:                    [Automático]
Propietario:                [Buscar / opcional]
Paciente:                   [Buscar / opcional]

Detalle
--------------------------------------------------
[Agregar producto/servicio]

Ítem                  Cantidad      Precio      Total
-----------------------------------------------------
Consulta              1             $ X         $ X
Alimento              1             $ X         $ X

Método de pago
--------------------------------------------------
Método:                     [Efectivo/Transferencia/etc]
Monto:                      [$ ______]
Referencia:                 [opcional]

[+ Agregar otro método de pago]

Total venta:                $ X
Total pagos:                $ X
Diferencia:                 $ 0

Observaciones:              [________________]

[Guardar venta]
```

---

## 10. Definición de roles/permisos sugerida

| Rol | Permisos sugeridos |
|---|---|
| Superadmin | Todo: usuarios, métricas globales, inventario, precios, ventas, cierres, facturación |
| Admin clínica | Inventario, precios, ventas, cierres, reportes, usuarios limitados |
| Médico veterinario | Pacientes, historias clínicas, ventas/facturación propias según autorización |
| Recepción/caja | Registro ventas, cierres de turno, consulta pacientes/propietarios |
| Solo lectura/contador | Reportes, cierres, ventas, facturación, exportaciones |

---

## 11. Riesgos y decisiones pendientes

### Riesgos principales

1. **Cálculo de precios mal definido.**
   - Mitigación: validar fórmula antes de implementar.

2. **Actualización masiva de precios sin control.**
   - Mitigación: preview + confirmación + historial.

3. **Módulo de ventas demasiado grande.**
   - Mitigación: empezar con MVP manual, no conciliación bancaria automática.

4. **Facturación ARCA subestimada.**
   - Mitigación: spike técnico-fiscal previo.

5. **Roles/permisos insuficientes.**
   - Mitigación: definir permisos desde el inicio para precios, cierres y facturación.

---

## 12. Checklist para próxima reunión con veterinarios

### Material a pedir

- Excel actual de ventas diarias.
- Ejemplo de cierre diario.
- Ejemplo de cierre semanal.
- Lista de métodos de pago.
- Lista de marcas de alimentos.
- Ejemplo real de aumento de marca/proveedor.
- Capturas del flujo actual de facturación ARCA.
- Tipos de factura emitidos por cada médico.
- Confirmación del contador sobre requisitos fiscales.

### Decisiones a tomar

- Fórmula definitiva de precio de alimentos.
- Si precio final puede editarse manualmente.
- Si marca será obligatoria.
- Cómo aplicar aumentos por marca.
- Campos mínimos para venta.
- Estructura de turnos.
- Alcance MVP del módulo ventas.
- Si se inicia spike ARCA en paralelo.

---

## 13. Sprint propuesto inmediato

### Sprint 1 — 1 a 2 semanas

**Objetivo:** quick win + definición sólida de inventario y ventas.

**Historias sugeridas:**

1. Como usuario, quiero seleccionar un propietario desde el buscador global y entrar directamente a su detalle para ahorrar tiempo.

2. Como administrador, quiero ver un mockup del nuevo formulario de alimentos para validar que el cálculo de precios corresponde a mi operación real.

3. Como administrador, quiero confirmar cómo se calcula el precio de venta con IVA para evitar errores de margen.

4. Como equipo de desarrollo, queremos analizar el Excel actual de ventas para diseñar el módulo sin inventar un flujo distinto al que la clínica ya usa.

5. Como equipo técnico, queremos documentar requisitos mínimos de ARCA para decidir si la facturación se integra directo o por proveedor externo.

**Entregables del sprint:**
- Buscador corregido.
- Mockup de alimentos.
- Reglas de cálculo documentadas.
- Análisis inicial del Excel de ventas.
- Checklist fiscal/técnico ARCA.

---

## 14. Definición de terminado recomendada

Una funcionalidad se considera terminada cuando:

- Está implementada en frontend y backend si aplica.
- Tiene validación de permisos.
- Tiene estados de carga/error.
- No rompe flujos existentes.
- Fue probada con casos reales.
- Tiene criterio de aceptación validado.
- Queda documentada en changelog o notas internas.
- Si afecta dinero, tiene prueba de cálculo y validación con usuario.

