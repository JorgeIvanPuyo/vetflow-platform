import type { HelpGuide } from "../types";

export const guides: HelpGuide[] = [
  {
    "slug": "dashboard-inventario",
    "title": "Usar el dashboard de inventario",
    "description": "Consulta existencias, valores estimados y productos que necesitan atención.",
    "category": "inventario",
    "keywords": [
      "dashboard",
      "existencias",
      "stock",
      "alertas",
      "vencimiento"
    ],
    "appRoute": "/inventory/dashboard",
    "appRouteLabel": "Ir al dashboard de inventario",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Revisa el resumen",
        "description": "Abre Inventario desde el menú para consultar indicadores y valores estimados a costo y a precio de venta."
      },
      {
        "title": "Filtra la información",
        "description": "Selecciona categoría, marca, proveedor, estado y fechas según lo que necesites revisar."
      },
      {
        "title": "Atiende las alertas",
        "description": "Revisa Requieren atención y abre un producto para ver su detalle. Usa Productos, Movimientos o Importar para continuar con una tarea."
      }
    ],
    "relatedGuides": [
      "crear-producto",
      "movimientos-inventario",
      "importar-inventario"
    ],
    "updatedAt": "2026-09-10"
  },
  {
    "slug": "crear-producto",
    "title": "Crear un producto",
    "description": "Registra un artículo con sus existencias, proveedor y precios.",
    "category": "inventario",
    "keywords": [
      "producto",
      "item",
      "articulo",
      "categoria",
      "proveedor",
      "precio",
      "margen",
      "stock"
    ],
    "appRoute": "/inventory/new",
    "appRouteLabel": "Ir a Nuevo item",
    "estimatedMinutes": 5,
    "steps": [
      {
        "title": "Clasifica el producto",
        "description": "Selecciona Tipo de item y completa Nombre, Código interno si lo usas, Marca y Unidad de medida."
      },
      {
        "title": "Asocia su categoría y proveedor",
        "description": "Elige Categoría de la clínica y Subcategoría cuando correspondan. En Proveedor, selecciona el directorio o usa Otro (texto libre)."
      },
      {
        "title": "Configura las existencias",
        "description": "El producto nuevo se crea con Stock actual en cero. Completa Stock mínimo para identificar cuándo requiere reposición. Añade lote y vencimiento si corresponde."
      },
      {
        "title": "Indica el costo de compra",
        "description": "Completa Precio compra sin IVA e Impuesto de compra (%). Revisa Costo compra con impuesto."
      },
      {
        "title": "Revisa el precio de venta",
        "description": "Indica Margen de ganancia (%), revisa Precio sugerido y Precio de venta sin impuesto. Comprueba Impuesto de venta (%) y Precio final de venta."
      },
      {
        "title": "Decide el redondeo y guarda",
        "description": "Revisa la opción Redondear precio al múltiplo indicado, completa las notas y guarda el artículo."
      }
    ],
    "relatedGuides": [
      "editar-producto",
      "registrar-proveedor",
      "preferencias-clinica"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "El redondeo utiliza el incremento configurado en las preferencias de la clínica. Revisa siempre el precio final antes de guardar.",
      "Después de crear el producto, registra una entrada o recibe una compra para cargar sus existencias."
    ]
  },
  {
    "slug": "editar-producto",
    "title": "Editar un producto",
    "description": "Actualiza los datos comerciales de un artículo existente.",
    "category": "inventario",
    "keywords": [
      "editar",
      "producto",
      "precio",
      "margen",
      "proveedor",
      "stock minimo"
    ],
    "appRoute": "/inventory",
    "appRouteLabel": "Ir a Inventario",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre el producto",
        "description": "Busca el artículo en Inventario y entra a su detalle."
      },
      {
        "title": "Edita la información",
        "description": "Pulsa Editar y cambia nombre, categoría, proveedor, stock mínimo o precios según corresponda."
      },
      {
        "title": "Revisa y guarda",
        "description": "Comprueba impuestos, margen y precio final antes de guardar. Revisa el resumen actualizado en el detalle."
      }
    ],
    "relatedGuides": [
      "crear-producto",
      "movimientos-inventario",
      "operaciones-grupales"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "Para registrar entradas o salidas, usa las acciones de movimiento del producto."
    ]
  },
  {
    "slug": "movimientos-inventario",
    "title": "Registrar y consultar movimientos de inventario",
    "description": "Registra entradas o salidas de un producto y consulta cómo cambiaron sus existencias.",
    "category": "inventario",
    "keywords": [
      "movimientos",
      "entrada",
      "salida",
      "stock",
      "consumo",
      "compra"
    ],
    "appRoute": "/inventory",
    "appRouteLabel": "Ir a Inventario",
    "estimatedMinutes": 4,
    "steps": [
      {
        "title": "Abre el artículo",
        "description": "Busca el producto y entra a su detalle. Revisa Stock actual y Stock mínimo."
      },
      {
        "title": "Elige el movimiento",
        "description": "Usa Registrar compra para una entrada del artículo o Registrar salida para descontar unidades."
      },
      {
        "title": "Completa la operación",
        "description": "Para una entrada, indica cantidad y los datos de costo disponibles. Para una salida, completa cantidad, motivo y los demás datos que correspondan."
      },
      {
        "title": "Guarda y comprueba",
        "description": "Confirma la operación y revisa el stock actualizado y el Historial de stock."
      },
      {
        "title": "Consulta todos los movimientos",
        "description": "En Movimientos puedes buscar, filtrar y abrir el detalle para ver cantidad, stock antes y después, origen y posibles reversas.",
        "appRoute": "/inventory/movements",
        "appRouteLabel": "Ir a Movimientos"
      }
    ],
    "relatedGuides": [
      "registrar-compra",
      "recibir-compra",
      "dashboard-inventario"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "Registrar compra desde el producto es una entrada de ese artículo. Para documentar una compra a proveedor con varias líneas, usa Compras. No registres dos veces la misma recepción."
    ]
  },
  {
    "slug": "importar-inventario",
    "title": "Importar inventario desde Excel",
    "description": "Carga productos o actualiza el catálogo revisando los cambios antes de confirmarlos.",
    "category": "inventario",
    "keywords": [
      "excel",
      "xlsx",
      "importar",
      "carga",
      "productos",
      "inventario"
    ],
    "appRoute": "/inventory/import",
    "appRouteLabel": "Ir a Importar inventario",
    "estimatedMinutes": 5,
    "steps": [
      {
        "title": "Descarga la plantilla",
        "description": "Pulsa Plantilla, completa el archivo de Excel y conserva su estructura. Usa un archivo .xlsx de hasta 5 MB."
      },
      {
        "title": "Selecciona el modo",
        "description": "Elige Carga inicial para conciliar stock físico y catálogo, o Actualizar catálogo para ignorar las existencias del archivo."
      },
      {
        "title": "Genera la vista previa",
        "description": "Pulsa Seleccionar archivo .xlsx y después Generar preview. Este paso permite revisar los datos antes de aplicarlos."
      },
      {
        "title": "Revisa cada fila",
        "description": "Usa los filtros Válidas, Revisión y Errores. Comprueba producto y acción: Crear, Actualizar u Omitir. Selecciona las filas que deseas aplicar."
      },
      {
        "title": "Confirma la importación",
        "description": "Pulsa Confirmar, revisa las filas seleccionadas y el motivo opcional, y confirma. Solo puedes aplicar filas sin errores."
      },
      {
        "title": "Comprueba el resultado",
        "description": "Revisa Resultado, las importaciones recientes y los movimientos cuando estén disponibles."
      }
    ],
    "relatedGuides": [
      "crear-producto",
      "exportar-inventario",
      "operaciones-grupales"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "Actualizar catálogo ignora el stock del archivo. En Carga inicial revisa cuidadosamente las cantidades antes de confirmar."
    ]
  },
  {
    "slug": "exportar-inventario",
    "title": "Exportar el inventario a Excel",
    "description": "Descarga el inventario completo o los resultados de una búsqueda.",
    "category": "inventario",
    "keywords": [
      "excel",
      "exportar",
      "descargar",
      "filtros",
      "listado"
    ],
    "appRoute": "/inventory",
    "appRouteLabel": "Ir a Inventario",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Prepara el listado",
        "description": "Abre Inventario y aplica búsqueda y filtros si solo necesitas una parte de los productos."
      },
      {
        "title": "Elige qué exportar",
        "description": "Pulsa Exportar. Selecciona Exportar inventario completo para los productos activos, o Exportar resultados filtrados."
      },
      {
        "title": "Descarga y revisa",
        "description": "Confirma la exportación y abre el archivo descargado para revisar su contenido."
      }
    ],
    "relatedGuides": [
      "importar-inventario",
      "dashboard-inventario"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "La exportación filtrada incluye todos los resultados, no solo la página visible."
    ]
  },
  {
    "slug": "operaciones-grupales",
    "title": "Realizar operaciones grupales",
    "description": "Actualiza varios productos y revisa los cambios antes de aplicarlos.",
    "category": "inventario",
    "keywords": [
      "grupo",
      "masivo",
      "precio",
      "margen",
      "marca",
      "proveedor",
      "stock minimo"
    ],
    "appRoute": "/inventory",
    "appRouteLabel": "Ir a Inventario",
    "estimatedMinutes": 4,
    "steps": [
      {
        "title": "Selecciona los artículos",
        "description": "Aplica filtros en Inventario. Usa Seleccionar esta página o Seleccionar todos los resultados y comprueba la selección."
      },
      {
        "title": "Configura el cambio",
        "description": "Pulsa Editar grupo. Selecciona la operación: cambiar precios, margen, marca, proveedor, stock mínimo o actividad, y completa el valor cuando corresponda."
      },
      {
        "title": "Simula el resultado",
        "description": "Pulsa Simular y revisa los valores anteriores y nuevos, así como las filas que requieran revisión."
      },
      {
        "title": "Confirma",
        "description": "Cuando los cambios sean correctos, pulsa Confirmar."
      },
      {
        "title": "Consulta el historial",
        "description": "Abre Historial grupal u Operaciones grupales y selecciona la operación para revisar su estado y los cambios.",
        "appRoute": "/inventory/bulk-operations",
        "appRouteLabel": "Ir a Operaciones grupales"
      }
    ],
    "relatedGuides": [
      "editar-producto",
      "exportar-inventario",
      "importar-inventario"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "Si el detalle ofrece Revertir cambios, revisa los posibles conflictos antes de usarlo."
    ]
  }
];
