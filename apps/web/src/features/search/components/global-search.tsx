"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

import { getApiErrorMessage } from "@/lib/api";
import { searchGlobal } from "@/services/search";
import type { SearchResult } from "@/types/api";

type SearchState = {
  isLoading: boolean;
  results: SearchResult[];
  errorMessage: string | null;
  submittedQuery: string;
};

const initialState: SearchState = {
  isLoading: false,
  results: [],
  errorMessage: null,
  submittedQuery: "",
};

type GlobalSearchProps = {
  onResultSelected?: () => void;
};

export function GlobalSearch({ onResultSelected }: GlobalSearchProps) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<SearchState>(initialState);

  const hasResults = state.results.length > 0;
  const showResultsPanel =
    state.isLoading ||
    Boolean(state.errorMessage) ||
    Boolean(state.submittedQuery) ||
    hasResults;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      setState(initialState);
      return;
    }

    setState({
      isLoading: true,
      results: [],
      errorMessage: null,
      submittedQuery: trimmedQuery,
    });

    try {
      const response = await searchGlobal(trimmedQuery);
      setState({
        isLoading: false,
        results: response.data,
        errorMessage: null,
        submittedQuery: response.meta.query,
      });
    } catch (error) {
      const message =
        getApiErrorMessage(error);

      setState({
        isLoading: false,
        results: [],
        errorMessage: message,
        submittedQuery: trimmedQuery,
      });
    }
  }

  function clearResults() {
    setState(initialState);
    setQuery("");
  }

  const resultCountLabel = useMemo(() => {
    if (!state.submittedQuery || state.isLoading || state.errorMessage) {
      return null;
    }

    return `${state.results.length} resultado${state.results.length === 1 ? "" : "s"} para "${state.submittedQuery}"`;
  }, [state.errorMessage, state.isLoading, state.results.length, state.submittedQuery]);

  return (
    <div className="global-search">
      <form className="search-form" onSubmit={handleSubmit} role="search">
        <input
          aria-label="Buscar propietarios y pacientes"
          className="search-input"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar propietarios, teléfonos o pacientes"
          value={query}
        />
        <button className="search-button" type="submit">
          Buscar
        </button>
      </form>

      {showResultsPanel ? (
        <div className="search-results">
          <div className="search-results__header">
            <strong>Búsqueda</strong>
            <button className="search-results__clear" onClick={clearResults} type="button">
              Limpiar
            </button>
          </div>

          {state.isLoading ? (
            <div className="panel-note">Buscando...</div>
          ) : null}

          {!state.isLoading && state.errorMessage ? (
            <div className="error-state">{state.errorMessage}</div>
          ) : null}

          {!state.isLoading && !state.errorMessage && resultCountLabel ? (
            <p className="search-results__meta">{resultCountLabel}</p>
          ) : null}

          {!state.isLoading &&
          !state.errorMessage &&
          state.submittedQuery &&
          state.results.length === 0 ? (
            <div className="empty-state">No se encontraron propietarios ni pacientes.</div>
          ) : null}

          {!state.isLoading && !state.errorMessage && hasResults ? (
            <ul className="search-result-list">
              {state.results.map((result) => (
                <li className="search-result-item" key={`${result.type}-${result.id}`}>
                  <Link
                    className="search-result-link"
                    href={result.type === "patient" && result.patient_id ? `/patients/${result.patient_id}` : "/owners"}
                    onClick={() => {
                      clearResults();
                      onResultSelected?.();
                    }}
                  >
                    <span className={`result-badge result-badge--${result.type}`}>
                      {result.type === "owner" ? "propietario" : "paciente"}
                    </span>
                    <span className="search-result-copy">
                      <span className="search-result-title">{result.title}</span>
                      <span className="search-result-subtitle">
                        {translateSearchSubtitle(result.subtitle)}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function translateSearchSubtitle(subtitle: string) {
  return subtitle.replace("Owner:", "Propietario:");
}
