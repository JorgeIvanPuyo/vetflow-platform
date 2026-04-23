"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

import { ApiClientError } from "@/lib/api";
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

export function GlobalSearch() {
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
        error instanceof ApiClientError
          ? error.message
          : "Could not complete search";

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

    return `${state.results.length} result${state.results.length === 1 ? "" : "s"} for "${state.submittedQuery}"`;
  }, [state.errorMessage, state.isLoading, state.results.length, state.submittedQuery]);

  return (
    <div className="global-search">
      <form className="search-form" onSubmit={handleSubmit} role="search">
        <input
          aria-label="Search owners and patients"
          className="search-input"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search owners, phones or patients"
          value={query}
        />
        <button className="search-button" type="submit">
          Search
        </button>
      </form>

      {showResultsPanel ? (
        <div className="search-results">
          <div className="search-results__header">
            <strong>Search</strong>
            <button className="search-results__clear" onClick={clearResults} type="button">
              Clear
            </button>
          </div>

          {state.isLoading ? (
            <div className="panel-note">Searching...</div>
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
            <div className="empty-state">No owners or patients matched that search.</div>
          ) : null}

          {!state.isLoading && !state.errorMessage && hasResults ? (
            <ul className="search-result-list">
              {state.results.map((result) => (
                <li className="search-result-item" key={`${result.type}-${result.id}`}>
                  <Link
                    className="search-result-link"
                    href={result.type === "patient" && result.patient_id ? `/patients/${result.patient_id}` : "/owners"}
                    onClick={clearResults}
                  >
                    <span className={`result-badge result-badge--${result.type}`}>
                      {result.type}
                    </span>
                    <span className="search-result-copy">
                      <span className="search-result-title">{result.title}</span>
                      <span className="search-result-subtitle">{result.subtitle}</span>
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
