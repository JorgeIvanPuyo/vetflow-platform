import type { HelpGuide } from "../types";
import { guides as guides0 } from "./getting-started";
import { guides as guides1 } from "./agenda";
import { guides as guides2 } from "./patients";
import { guides as guides3 } from "./consultations";
import { guides as guides4 } from "./inventory";
import { guides as guides5 } from "./suppliers";
import { guides as guides6 } from "./purchases";
import { guides as guides7 } from "./sales";
import { guides as guides8 } from "./settings";
import { guides as guides9 } from "./users";
import { guides as guides10 } from "./clinics";

export const helpGuides: HelpGuide[] = [...guides0, ...guides1, ...guides2, ...guides3, ...guides4, ...guides5, ...guides6, ...guides7, ...guides8, ...guides9, ...guides10];

export const frequentGuideSlugs = [
  "registrar-paciente",
  "agendar-cita",
  "iniciar-consulta",
  "importar-inventario",
  "registrar-compra",
  "registrar-venta",
];
