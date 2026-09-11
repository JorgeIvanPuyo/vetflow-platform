# Centro de ayuda

**Nueva funcionalidad de usuario = documentación actualizada.**

Las rutas `/help` y `/help/[slug]` usan contenido estático tipado, sin llamadas a servicios. El layout autenticado de la aplicación sigue siendo el punto de entrada. Los artículos son informativos: `requiredRoles` muestra a quién va dirigida una acción; no concede permisos ni sustituye los controles de la aplicación.

## Para agregar una nueva funcionalidad a Vetflow

1. Crea o actualiza una guía en el archivo de su módulo dentro de `content/`. Si creas un módulo, impórtalo en `content/index.ts`.
2. Añade keywords y sinónimos que usaría una persona buscando la tarea.
3. Configura `appRoute` y `appRouteLabel` con una ruta canónica existente. Para registros concretos, enlaza al listado y explica cómo abrir el detalle.
4. Si existen screenshots, guárdalos en `apps/web/public/help/` y añade `imageSrc` e `imageAlt` al paso correspondiente. Usa rutas como `/help/inventory/import-step-1.png`. No es necesario modificar componentes. No publiques datos personales en las capturas.
5. Añade `youtubeUrl` (HTTPS de YouTube) y opcionalmente `youtubeLabel` cuando exista un tutorial real. Sin URL no se muestra la sección de video.
6. Actualiza `updatedAt` con la fecha de revisión (`AAAA-MM-DD`).
7. Enlaza de dos a cuatro guías relacionadas mediante sus slugs únicos.

Ejemplo mínimo:

```ts
import type { HelpGuide } from "../types";

const guide: HelpGuide = {
  slug: "mi-nueva-guia",
  title: "Consultar un producto",
  description: "Encuentra las existencias y los precios de un artículo.",
  category: "inventario",
  keywords: ["producto", "stock", "precio"],
  appRoute: "/inventory",
  appRouteLabel: "Ir a Inventario",
  steps: [
    { title: "Busca el artículo", description: "Ingresa su nombre en Inventario." },
    { title: "Abre el detalle", description: "Selecciona el producto encontrado." },
    { title: "Revisa los datos", description: "Consulta existencias y precios." },
  ],
  relatedGuides: ["crear-producto", "editar-producto"],
  updatedAt: "2026-09-10",
};
```

Las categorías se definen en `types.ts`; la selección de tareas frecuentes está en `content/index.ts`. Los componentes y estilos viven fuera del contenido. La búsqueda normaliza mayúsculas, acentos y espacios y combina texto con categoría.

## Revisión y validación

Comprueba los pasos y labels contra los componentes de cada feature, y los permisos contra los controles reales. No uses propuestas históricas ni documentes acciones que todavía muestran «Próximamente». Al cambiar flujos de stock, revisa el momento exacto en que se aplica cada movimiento.

Dentro del contenedor de validación frontend, desde `apps/web`, ejecuta:

```sh
node --test src/features/help/help.test.cjs
pnpm exec tsc --noEmit
pnpm run lint
pnpm run build
```

Las pruebas usan Node y el TypeScript ya instalado. Verifican búsqueda, referencias, rutas, metadatos, visibilidad de la entrada por rol y renderizado de artículos con y sin contenido multimedia. No necesitan backend ni base de datos.
