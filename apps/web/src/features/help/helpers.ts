import type { AppRole } from "@/types/api";
import { helpCategories, type HelpCategory, type HelpGuide } from "./types";

export const helpRoleLabels: Record<AppRole, string> = {
  clinic_admin: "Administrador de clínica",
  medico_veterinario: "Médico veterinario",
  contador: "Contador",
  superadmin: "Superadmin",
};

export function normalizeHelpSearch(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim().replace(/\s+/g, " ");
}

export function searchHelpGuides(guides: HelpGuide[], query: string, category?: HelpCategory): HelpGuide[] {
  const terms = normalizeHelpSearch(query).split(" ").filter(Boolean);
  return guides.filter((guide) => {
    if (category && guide.category !== category) return false;
    const searchable = normalizeHelpSearch([guide.title, guide.description, ...guide.keywords, helpCategories[guide.category].label].join(" "));
    return terms.every((term) => searchable.includes(term));
  });
}

export function getRelatedGuides(guide: HelpGuide, guides: HelpGuide[]): HelpGuide[] {
  return (guide.relatedGuides ?? []).flatMap((slug) => {
    const related = guides.find((item) => item.slug === slug && item.slug !== guide.slug);
    return related ? [related] : [];
  }).slice(0, 4);
}

export function isYouTubeUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && ["youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"].includes(url.hostname) && !url.username && !url.password;
  } catch {
    return false;
  }
}
