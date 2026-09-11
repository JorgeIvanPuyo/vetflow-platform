import { ArrowLeft, ArrowUpRight, Clock } from "lucide-react";
import Link from "next/link";
import { helpGuides } from "../content";
import { getRelatedGuides, helpRoleLabels } from "../helpers";
import { helpCategories, type HelpGuide } from "../types";
import { HelpGuideCard } from "./help-guide-card";
import { HelpStep } from "./help-step";
import { HelpVideoLink } from "./help-video-link";

export function HelpArticle({ guide }: { guide: HelpGuide }) {
  const related = getRelatedGuides(guide, helpGuides);
  return (
    <div className="page-stack help-page">
      <nav className="help-breadcrumb" aria-label="Ruta de navegación"><Link href="/help">Centro de ayuda</Link><span aria-hidden="true">/</span><Link href={`/help?category=${guide.category}`}>{helpCategories[guide.category].label}</Link><span aria-hidden="true">/</span><span aria-current="page">{guide.title}</span></nav>
      <article className="help-article panel">
        <header className="help-article-header">
          <p className="eyebrow">{helpCategories[guide.category].label}</p>
          <h1>{guide.title}</h1><p>{guide.description}</p>
          <div className="help-meta-row">{guide.estimatedMinutes ? <span className="help-meta"><Clock aria-hidden="true" size={16} />{guide.estimatedMinutes} min de lectura</span> : null}<span className="help-meta">Actualizado el <time dateTime={guide.updatedAt}>{guide.updatedAt.split("-").reverse().join("/")}</time></span></div>
          {guide.requiredRoles?.length ? <p className="panel-note">Solo para {guide.requiredRoles.map((role) => helpRoleLabels[role]).join(", ")}</p> : null}
          {guide.appRoute ? <Link className="primary-button" href={guide.appRoute}>{guide.appRouteLabel ?? "Abrir en Vetflow"}<ArrowUpRight aria-hidden="true" size={18} /></Link> : null}
        </header>
        {guide.prerequisites?.length ? <section><h2>Antes de empezar</h2><ul className="help-text-list">{guide.prerequisites.map((item) => <li key={item}>{item}</li>)}</ul></section> : null}
        <section><h2>Paso a paso</h2><ol className="help-steps">{guide.steps.map((step, index) => <HelpStep key={`${guide.slug}-${index}`} step={step} />)}</ol></section>
        {guide.tips?.length ? <section className="help-tips"><h2>Consejos</h2><ul className="help-text-list">{guide.tips.map((tip) => <li key={tip}>{tip}</li>)}</ul></section> : null}
        <HelpVideoLink url={guide.youtubeUrl} label={guide.youtubeLabel} />
      </article>
      {related.length ? <section aria-labelledby="help-related-title"><div className="section-heading"><h2 id="help-related-title">Guías relacionadas</h2></div><div className="help-grid">{related.map((item) => <HelpGuideCard key={item.slug} guide={item} />)}</div></section> : null}
      <Link className="back-link" href="/help"><ArrowLeft aria-hidden="true" size={18} />Volver al Centro de ayuda</Link>
    </div>
  );
}
