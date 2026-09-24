import type { HelpGuide } from "../types";

export const guides: HelpGuide[] = [
  {
    "slug": "dashboard-compras",
    "title": "Usar el dashboard de compras",
    "description": "Revisa compras recientes, proveedores y operaciones que requieren atención.",
    "category": "compras",
    "keywords": [
      "dashboard",
      "proveedor",
      "compras",
      "pendientes",
      "comprobantes"
    ],
    "appRoute": "/purchases/dashboard",
    "appRouteLabel": "Ir al dashboard de compras",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Delimita la consulta",
        "description": "Abre Compras desde el menú. Filtra por fechas, proveedor, creador o tipo de comprobante."
      },
      {
        "title": "Revisa el resumen",
        "description": "Consulta los indicadores, Compras recientes y Principales proveedores del período."
      },
      {
        "title": "Abre una compra pendiente",
        "description": "En Requieren atención, usa Ver pendientes. Abre una compra para revisar su recepción o comprobante."
      }
    ],
    "relatedGuides": [
      "registrar-compra",
      "recibir-compra",
      "adjuntar-compra"
    ],
    "updatedAt": "2026-09-10"
  },
  {
    "slug": "registrar-compra",
    "title": "Registrar una compra",
    "description": "Prepara un borrador con proveedor, productos y comprobante.",
    "category": "compras",
    "keywords": [
      "compra",
      "proveedor",
      "factura",
      "borrador",
      "productos"
    ],
    "appRoute": "/purchases/new",
    "appRouteLabel": "Ir a Nueva compra",
    "estimatedMinutes": 4,
    "steps": [
      {
        "title": "Selecciona al proveedor",
        "description": "Abre Nueva compra y busca un proveedor activo del directorio. Si falta, usa Nuevo proveedor."
      },
      {
        "title": "Completa la cabecera",
        "description": "Indica Fecha, Tipo de comprobante, Número si corresponde y Notas."
      },
      {
        "title": "Añade los productos",
        "description": "Busca por nombre o código interno. Agrega al menos un producto y completa Cantidad, Costo sin IVA e IVA de cada línea."
      },
      {
        "title": "Revisa el documento y los importes",
        "description": "Comprueba subtotal y total. Puedes añadir un comprobante PDF, JPEG o PNG de hasta 10 MB."
      },
      {
        "title": "Guarda el borrador",
        "description": "Guarda la compra y revisa su detalle. Las existencias se actualizarán cuando recibas la compra."
      }
    ],
    "relatedGuides": [
      "registrar-proveedor",
      "recibir-compra",
      "editar-compra"
    ],
    "updatedAt": "2026-09-10",
    "prerequisites": [
      "Ten registrados el proveedor y los productos de la compra."
    ],
    "tips": [
      "Guardar el borrador no cambia el inventario."
    ]
  },
  {
    "slug": "recibir-compra",
    "title": "Recibir una compra y actualizar inventario",
    "description": "Confirma la recepción de los productos de una compra guardada.",
    "category": "compras",
    "keywords": [
      "recibir",
      "recepcion",
      "compra",
      "entrada",
      "stock",
      "proveedor"
    ],
    "appRoute": "/purchases",
    "appRouteLabel": "Ir a Compras",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre el borrador",
        "description": "En Compras, selecciona una compra en estado Borrador y verifica que los productos hayan llegado."
      },
      {
        "title": "Revisa sus líneas",
        "description": "Comprueba cantidades, costo e IVA. Usa Editar antes de recibir si hay datos incorrectos."
      },
      {
        "title": "Confirma la recepción",
        "description": "Pulsa Recibir compra y revisa Confirmar recepción. Confirma cuando las líneas guardadas coincidan con lo recibido."
      },
      {
        "title": "Comprueba las existencias",
        "description": "La compra queda Recibida. Usa Ver movimientos para consultar las entradas de inventario."
      }
    ],
    "relatedGuides": [
      "registrar-compra",
      "editar-compra",
      "devolucion-compra"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "La recepción aumenta el stock y actualiza el último costo de compra y su IVA. No cambia el precio de venta ni el margen.",
      "Una compra recibida ya no puede editarse."
    ]
  },
  {
    "slug": "adjuntar-compra",
    "title": "Adjuntar documentos a una compra",
    "description": "Carga o reemplaza el comprobante y consulta su historial.",
    "category": "compras",
    "keywords": [
      "adjunto",
      "archivo",
      "comprobante",
      "pdf",
      "factura",
      "documento"
    ],
    "appRoute": "/purchases",
    "appRouteLabel": "Ir a Compras",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Abre la compra",
        "description": "Selecciona la compra y localiza Comprobante."
      },
      {
        "title": "Carga el documento",
        "description": "Usa la acción para adjuntar o reemplazar el comprobante. Selecciona un PDF, JPEG o PNG de hasta 10 MB y guarda."
      },
      {
        "title": "Revisa el archivo",
        "description": "Usa Ver o Descargar. Si reemplazaste el archivo, puedes consultar el historial de comprobantes anteriores."
      }
    ],
    "relatedGuides": [
      "registrar-compra",
      "dashboard-compras"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "Adjuntar o reemplazar un comprobante no cambia las líneas de la compra ni el stock.",
      "Si la compra quedó guardada pero el archivo falló, vuelve a subirlo desde su detalle sin crear otra compra."
    ]
  },
  {
    "slug": "editar-compra",
    "title": "Editar una compra en borrador",
    "description": "Corrige la compra antes de recibir sus productos.",
    "category": "compras",
    "keywords": [
      "editar",
      "compra",
      "borrador",
      "corregir",
      "proveedor"
    ],
    "appRoute": "/purchases",
    "appRouteLabel": "Ir a Compras",
    "estimatedMinutes": 3,
    "steps": [
      {
        "title": "Encuentra el borrador",
        "description": "En Compras, filtra por Borradores y abre la compra que necesitas modificar."
      },
      {
        "title": "Edita sus datos",
        "description": "Pulsa Editar y actualiza proveedor, comprobante o líneas de producto."
      },
      {
        "title": "Guarda y verifica",
        "description": "Revisa cantidades e importes y guarda los cambios antes de recibir."
      }
    ],
    "relatedGuides": [
      "registrar-compra",
      "recibir-compra"
    ],
    "updatedAt": "2026-09-10",
    "tips": [
      "Solo pueden editarse compras en Borrador. Las recibidas, canceladas o con recepción revertida conservan su información histórica."
    ]
  },
  {
    "slug": "devolucion-compra",
    "title": "Registrar una devolución a proveedor",
    "description": "Devuelve cantidades de una compra recibida y registra la salida de inventario.",
    "category": "compras",
    "keywords": [
      "devolucion",
      "devolver",
      "proveedor",
      "nota credito",
      "stock"
    ],
    "appRoute": "/purchases",
    "appRouteLabel": "Ir a Compras",
    "estimatedMinutes": 5,
    "steps": [
      {
        "title": "Abre la compra recibida",
        "description": "Busca la compra original. Si admite devoluciones, pulsa Registrar devolución."
      },
      {
        "title": "Completa los datos",
        "description": "Indica Fecha, Motivo y los datos del documento cuando correspondan."
      },
      {
        "title": "Selecciona las cantidades",
        "description": "Completa A devolver sin superar Disponible. Los precios e IVA se toman de la compra original."
      },
      {
        "title": "Guarda el borrador",
        "description": "Añade el comprobante opcional y guarda. En este punto todavía no cambia el stock."
      },
      {
        "title": "Confirma la devolución",
        "description": "Desde el detalle, pulsa Confirmar devolución y revisa sus efectos antes de confirmar."
      },
      {
        "title": "Revisa los movimientos",
        "description": "La confirmación disminuye las existencias. Consulta Ver movimientos y el resumen de devoluciones de la compra original."
      }
    ],
    "relatedGuides": [
      "recibir-compra",
      "movimientos-inventario",
      "adjuntar-compra"
    ],
    "updatedAt": "2026-09-10",
    "prerequisites": [
      "La compra debe estar recibida y tener cantidades disponibles para devolver.",
      "Debe haber existencias suficientes para la salida."
    ],
    "tips": [
      "Una devolución confirmada no puede editarse ni deshacerse automáticamente. No cambia costos, precios de venta ni margen."
    ]
  }
];
