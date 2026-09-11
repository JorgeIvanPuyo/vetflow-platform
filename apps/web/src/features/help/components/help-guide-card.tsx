import { ArrowUpRight, Clock } from "lucide-react";
import Link from "next/link";
import { helpCategories, type HelpGuide } from "../types";
import { helpRoleLabels } from "../helpers";

export function HelpGuideCard({ guide }: { guide: HelpGuide }) {
  return (
    <Link className="help-guide-card" href={`/help/${guide.slug}`}>
      <span className="help-meta">{helpCategories[guide.category].label}</span>
      <h3>{guide.title}<ArrowUpRight aria-hidden="true" size={18} /></h3>
      <p>{guide.description}</p>
      <span className="help-card-footer">
        {guide.estimatedMinutes ? <span className="help-meta"><Clock aria-hidden="true" size={14} />{guide.estimatedMinutes} min</span> : null}
        {guide.requiredRoles?.length ? <span className="help-meta">Solo para {guide.requiredRoles.map((role) => helpRoleLabels[role]).join(", ")}</span> : null}
      </span>
    </Link>
  );
}
