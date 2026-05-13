"use client";

import { Copy, RefreshCw, Sparkles, X } from "lucide-react";
import { useRef, useState } from "react";

import { ApiClientError } from "@/lib/api";
import { isAiFeaturesEnabled } from "@/lib/features";
import { generateConsultationAiSummary } from "@/services/consultations";
import type { ConsultationAiSummaryResponse } from "@/types/api";

const AI_SUMMARY_DISCLAIMER =
  "Texto sugerido por IA. Revisa antes de guardar o compartir.";
const AI_PROVIDER_QUOTA_EXCEEDED_MESSAGE =
  "Cuota del proveedor de IA excedida. Espera unos minutos e intenta nuevamente o aumenta el plan del proveedor.";

type AiConsultationSummaryCardProps = {
  consultationId: string | null;
  summary?: string | null;
  generatedAt?: string | null;
  model?: string | null;
  onSummaryChange: (response: ConsultationAiSummaryResponse) => void;
  onToast: (title: string, detail?: string, variant?: "success" | "error") => void;
  className?: string;
  mode?: "card" | "button";
};

export function AiConsultationSummaryCard({
  consultationId,
  summary,
  generatedAt,
  model,
  onSummaryChange,
  onToast,
  className,
  mode = "card",
}: AiConsultationSummaryCardProps) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [disclaimer, setDisclaimer] = useState(AI_SUMMARY_DISCLAIMER);
  const [isCopied, setIsCopied] = useState(false);
  const isRequestInFlightRef = useRef(false);
  const hasSummary = Boolean(summary?.trim());

  if (!isAiFeaturesEnabled) {
    return null;
  }

  async function handleGenerate() {
    if (isRequestInFlightRef.current || isLoading) {
      return;
    }

    if (!consultationId) {
      const message = "Guarda la consulta antes de generar el resumen IA.";
      setErrorMessage(message);
      onToast(message, undefined, "error");
      return;
    }

    isRequestInFlightRef.current = true;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await generateConsultationAiSummary(consultationId);
      setDisclaimer(response.disclaimer || AI_SUMMARY_DISCLAIMER);
      onSummaryChange(response);
      onToast(
        hasSummary ? "Resumen IA regenerado." : "Resumen IA generado.",
        undefined,
        "success",
      );
    } catch (error) {
      const message = getAiSummaryErrorMessage(error);
      setErrorMessage(message);
      onToast(message, undefined, "error");
    } finally {
      isRequestInFlightRef.current = false;
      setIsLoading(false);
    }
  }

  async function handleCopy() {
    if (!summary) {
      return;
    }

    try {
      await navigator.clipboard.writeText(summary);
      setIsCopied(true);
      onToast("Resumen copiado.", undefined, "success");
      window.setTimeout(() => setIsCopied(false), 1800);
    } catch {
      onToast("No se pudo copiar el resumen.", undefined, "error");
    }
  }

  return (
    <>
      {mode === "card" ? (
        <article className={`ai-summary-card${className ? ` ${className}` : ""}`}>
          <div className="ai-summary-card__header">
            <div>
              <h3>
                <Sparkles aria-hidden="true" size={17} />
                Resumen clínico IA
              </h3>
              <p>
                {hasSummary
                  ? generatedAt
                    ? `Resumen generado · ${formatDateTime(generatedAt)}`
                    : "Resumen generado"
                  : "Genera o revisa el resumen clínico de esta consulta."}
              </p>
            </div>
            <AiSummaryTriggerButton
              disabled={!consultationId}
              isLoading={isLoading}
              label={hasSummary ? "Ver resumen IA" : "Resumen clínico IA"}
              mobileLabel={hasSummary ? "Ver resumen" : "Resumen IA"}
              onClick={() => setIsDialogOpen(true)}
            />
          </div>
        </article>
      ) : (
        <AiSummaryTriggerButton
          className={className}
          disabled={!consultationId}
          isLoading={isLoading}
          label="Resumen clínico IA"
          mobileLabel="Resumen IA"
          onClick={() => setIsDialogOpen(true)}
        />
      )}

      {isDialogOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="ai-summary-dialog-title"
            aria-modal="true"
            className="bottom-sheet ai-summary-dialog"
            role="dialog"
          >
            <div className="bottom-sheet__header ai-summary-dialog__header">
              <div>
                <p className="eyebrow">Asistente IA</p>
                <h2 id="ai-summary-dialog-title">
                  <Sparkles aria-hidden="true" size={18} />
                  Resumen clínico IA
                </h2>
              </div>
              <button
                aria-label="Cerrar resumen clínico IA"
                className="icon-button"
                disabled={isLoading}
                onClick={() => setIsDialogOpen(false)}
                type="button"
              >
                <X aria-hidden="true" size={20} />
              </button>
            </div>

            <div className="ai-summary-dialog__body">
              {hasSummary ? (
                <>
                  <div className="ai-summary-dialog__content">
                    <p>{summary}</p>
                  </div>
                  <p className="ai-summary-card__meta">
                    {model ? `Generado con ${model}` : "Resumen IA guardado"}
                    {generatedAt ? ` · ${formatDateTime(generatedAt)}` : ""}
                  </p>
                </>
              ) : (
                <div className="ai-summary-dialog__empty">
                  <strong>Aún no hay un resumen generado para esta consulta.</strong>
                  <span>
                    Puedes generar un resumen breve usando la información registrada.
                  </span>
                </div>
              )}

              {isLoading ? (
                <div className="ai-loading-panel ai-summary-card__loading" role="status">
                  <span className="ai-loading-panel__spinner" aria-hidden="true" />
                  <span>IA generando resumen...</span>
                </div>
              ) : null}

              {errorMessage ? (
                <p className="ai-inline-notice ai-summary-card__notice" role="alert">
                  {errorMessage}
                </p>
              ) : null}

              <p className="ai-disclaimer">{disclaimer}</p>
            </div>

            <div className="modal-actions ai-summary-dialog__actions">
              <button
                className="secondary-button"
                disabled={isLoading}
                onClick={() => setIsDialogOpen(false)}
                type="button"
              >
                Cerrar
              </button>
              {hasSummary ? (
                <button
                  className="secondary-button"
                  disabled={isLoading}
                  onClick={() => void handleCopy()}
                  type="button"
                >
                  <Copy aria-hidden="true" size={16} />
                  {isCopied ? "Copiado" : "Copiar"}
                </button>
              ) : null}
              <button
                aria-busy={isLoading}
                className="primary-button"
                disabled={isLoading || !consultationId}
                onClick={() => void handleGenerate()}
                type="button"
              >
                {isLoading ? (
                  <span className="ai-inline-action__spinner" aria-hidden="true" />
                ) : hasSummary ? (
                  <RefreshCw aria-hidden="true" size={16} />
                ) : (
                  <Sparkles aria-hidden="true" size={16} />
                )}
                {isLoading
                  ? "IA generando resumen..."
                  : hasSummary
                    ? "Regenerar resumen IA"
                    : "Generar resumen IA"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}

function AiSummaryTriggerButton({
  className,
  disabled,
  isLoading,
  label,
  mobileLabel,
  onClick,
}: {
  className?: string;
  disabled: boolean;
  isLoading: boolean;
  label: string;
  mobileLabel: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-busy={isLoading}
      aria-label={label}
      className={`ai-inline-action ai-summary-trigger${className ? ` ${className}` : ""}${
        isLoading ? " ai-inline-action--loading" : ""
      }`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {isLoading ? (
        <span className="ai-inline-action__spinner" aria-hidden="true" />
      ) : (
        <Sparkles aria-hidden="true" className="ai-inline-action__icon" size={15} />
      )}
      <span className="ai-inline-action__label">
        {isLoading ? (
          "IA generando..."
        ) : (
          <>
            <span className="ai-summary-trigger__desktop-label">{label}</span>
            <span className="ai-summary-trigger__mobile-label">{mobileLabel}</span>
          </>
        )}
      </span>
    </button>
  );
}

function getAiSummaryErrorMessage(error: unknown) {
  if (error instanceof ApiClientError && error.status === 429) {
    return AI_PROVIDER_QUOTA_EXCEEDED_MESSAGE;
  }

  if (error instanceof ApiClientError && error.status === 503) {
    return "La función de IA no está disponible en este momento.";
  }

  if (error instanceof ApiClientError && error.status === 422) {
    return "No hay suficiente información clínica para generar un resumen.";
  }

  return "No pudimos generar el resumen en este momento.";
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
