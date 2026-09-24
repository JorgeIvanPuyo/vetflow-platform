"use client";

import { BookOpen } from "lucide-react";
import { useState } from "react";
import { helpGuides, frequentGuideSlugs } from "../content";
import { searchHelpGuides } from "../helpers";
import { helpCategories, type HelpCategory } from "../types";
import { HelpGuideCard } from "./help-guide-card";
import { HelpSearch } from "./help-search";

export function HelpHome({ initialCategory }: { initialCategory?: HelpCategory }) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<HelpCategory | undefined>(initialCategory);
  const results = searchHelpGuides(helpGuides, query, category);
  const filtering = Boolean(query.trim() || category);

  return (
    <div className="page-stack help-page">
      <header className="help-hero">
        <BookOpen aria-hidden="true" size={30} />
        <h1>Centro de ayuda</h1>
        <p>Encuentra guías paso a paso para realizar las tareas más importantes en Vetflow.</p>
        <HelpSearch value={query} onChange={setQuery} />
      </header>

      {!filtering ? <section aria-labelledby="help-frequent-title">
        <div className="section-heading"><h2 id="help-frequent-title">Tareas frecuentes</h2></div>
        <div className="help-grid">{frequentGuideSlugs.map((slug) => {
          const guide = helpGuides.find((item) => item.slug === slug);
          return guide ? <HelpGuideCard key={slug} guide={guide} /> : null;
        })}</div>
      </section> : null}

      <section aria-labelledby="help-categories-title">
        <div className="section-heading"><h2 id="help-categories-title">Explorar por módulo</h2></div>
        <div className="help-category-grid">
          {Object.entries(helpCategories).map(([key, item]) => (
            <button key={key} type="button" className={`help-category${category === key ? " help-category--active" : ""}`} aria-pressed={category === key} aria-controls="help-results" onClick={() => setCategory(category === key ? undefined : key as HelpCategory)}>
              <strong>{item.label}</strong><span>{item.description}</span>
              <small>{helpGuides.filter((guide) => guide.category === key).length} guías</small>
            </button>
          ))}
        </div>
      </section>

      <section id="help-results" aria-labelledby="help-results-title">
        <div className="help-results-heading">
          <div><h2 id="help-results-title">{filtering ? "Resultados" : "Todas las guías"}</h2><p role="status">{results.length} {results.length === 1 ? "guía disponible" : "guías disponibles"}{category ? ` · ${helpCategories[category].label}` : ""}</p></div>
          {filtering ? <button className="secondary-button" type="button" onClick={() => { setQuery(""); setCategory(undefined); }}>Limpiar filtros</button> : null}
        </div>
        {results.length ? <div className="help-grid">{results.map((guide) => <HelpGuideCard key={guide.slug} guide={guide} />)}</div> : <div className="empty-state"><strong>No encontramos una guía para esa búsqueda.</strong><p>Prueba con otra palabra o explora las categorías.</p></div>}
      </section>
    </div>
  );
}
