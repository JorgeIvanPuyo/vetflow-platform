"use client";

import { Check, Copy, Sparkles, X } from "lucide-react";
import { useRef, useState } from "react";

import { ApiClientError } from "@/lib/api";
import { isAiFeaturesEnabled } from "@/lib/features";
import {
  generateConsultationSummary,
  rewriteClinicalNote,
} from "@/services/ai";
import type {
  AiPatientContext,
  ConsultationSummaryPayload,
} from "@/types/api";

const AI_DISCLAIMER = "Texto sugerido por IA. Revisa antes de guardar.";
const MIN_REWRITE_LENGTH = 5;
const AI_PROVIDER_QUOTA_EXCEEDED_MESSAGE =
  "Cuota del proveedor de IA excedida. Espera unos minutos e intenta nuevamente o aumenta el plan del proveedor.";

type AiReviewState =
  | {
      kind: "rewrite";
      title: "Redacción sugerida";
      originalText: string;
      suggestion: string;
      disclaimer: string;
      onUse: (value: string) => void;
    }
  | {
      kind: "summary";
      title: "Resumen clínico sugerido";
      originalText?: never;
      suggestion: string;
      disclaimer: string;
      onUse?: (value: string) => void;
    };

type AiClinicalRewriteActionProps = {
  field: string;
  text: string;
  patientContext: AiPatientContext | null;
  onUseSuggestion: (value: string) => void;
  onToast: (title: string, detail?: string, variant?: "success" | "error") => void;
};

type AiConsultationSummaryActionProps = {
  consultation: ConsultationSummaryPayload;
  onInsertSummary?: (value: string) => void;
  onToast: (title: string, detail?: string, variant?: "success" | "error") => void;
};

type AiAssistButtonProps = {
  ariaLabel: string;
  disabled: boolean;
  isLoading: boolean;
  label: string;
  loadingLabel: string;
  onClick: () => void;
};

export function AiClinicalRewriteAction({
  field,
  text,
  patientContext,
  onUseSuggestion,
  onToast,
}: AiClinicalRewriteActionProps) {
  const [isLoading, setIsLoading] = useState(false);
  const isRequestInFlightRef = useRef(false);
  const [review, setReview] = useState<AiReviewState | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const hasEnoughText = text.trim().length >= MIN_REWRITE_LENGTH;

  if (!isAiFeaturesEnabled) {
    return null;
  }

  async function handleGenerate() {
    if (isRequestInFlightRef.current) {
      return;
    }

    const originalText = text.trim();

    if (originalText.length < MIN_REWRITE_LENGTH) {
      onToast(
        "Escribe una nota clínica antes de usar la sugerencia IA.",
        undefined,
        "error",
      );
      return;
    }

    isRequestInFlightRef.current = true;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await rewriteClinicalNote({
        field,
        text: originalText,
        patient_context: patientContext,
      });

      setReview({
        kind: "rewrite",
        title: "Redacción sugerida",
        originalText,
        suggestion: response.suggestion,
        disclaimer: response.disclaimer ?? AI_DISCLAIMER,
        onUse: onUseSuggestion,
      });
    } catch (error) {
      const message = getRewriteErrorMessage(error);
      setErrorMessage(message);
      onToast(message, undefined, "error");
    } finally {
      isRequestInFlightRef.current = false;
      setIsLoading(false);
    }
  }

  return (
    <span className="ai-assist">
      <AiAssistButton
        ariaLabel="Mejorar redacción clínica con IA"
        disabled={isLoading || !hasEnoughText}
        isLoading={isLoading}
        label="Asistente IA"
        loadingLabel="IA trabajando..."
        onClick={() => void handleGenerate()}
      />
      {isLoading ? <AiLoadingInlinePanel /> : null}
      {errorMessage ? (
        <AiInlineNotice
          message={errorMessage}
          onDismiss={() => setErrorMessage(null)}
        />
      ) : null}
      {review ? (
        <AiSuggestionInlinePanel
          review={review}
          onClose={() => setReview(null)}
          onToast={onToast}
        />
      ) : null}
    </span>
  );
}

export function AiConsultationSummaryAction({
  consultation,
  onInsertSummary,
  onToast,
}: AiConsultationSummaryActionProps) {
  const [isLoading, setIsLoading] = useState(false);
  const isRequestInFlightRef = useRef(false);
  const [review, setReview] = useState<AiReviewState | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const hasEnoughClinicalContent = hasConsultationClinicalContent(consultation);

  if (!isAiFeaturesEnabled) {
    return null;
  }

  async function handleGenerate() {
    if (isRequestInFlightRef.current) {
      return;
    }

    if (!hasEnoughClinicalContent) {
      onToast(
        "Agrega información clínica antes de generar un resumen.",
        undefined,
        "error",
      );
      return;
    }

    isRequestInFlightRef.current = true;
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await generateConsultationSummary({
        consultation,
        summary_type: "clinical",
      });

      setReview({
        kind: "summary",
        title: "Resumen clínico sugerido",
        suggestion: response.summary,
        disclaimer: response.disclaimer ?? AI_DISCLAIMER,
        onUse: onInsertSummary,
      });
    } catch (error) {
      const message = getSummaryErrorMessage(error);
      setErrorMessage(message);
      onToast(message, undefined, "error");
    } finally {
      isRequestInFlightRef.current = false;
      setIsLoading(false);
    }
  }

  return (
    <span className="ai-assist">
      <AiAssistButton
        ariaLabel="Generar resumen clínico con IA"
        disabled={isLoading || !hasEnoughClinicalContent}
        isLoading={isLoading}
        label="Asistente IA"
        loadingLabel="IA trabajando..."
        onClick={() => void handleGenerate()}
      />
      {isLoading ? <AiLoadingInlinePanel /> : null}
      {errorMessage ? (
        <AiInlineNotice
          message={errorMessage}
          onDismiss={() => setErrorMessage(null)}
        />
      ) : null}
      {review ? (
        <AiSuggestionInlinePanel
          review={review}
          onClose={() => setReview(null)}
          onToast={onToast}
        />
      ) : null}
    </span>
  );
}

function AiAssistButton({
  ariaLabel,
  disabled,
  isLoading,
  label,
  loadingLabel,
  onClick,
}: AiAssistButtonProps) {
  return (
    <button
      aria-label={ariaLabel}
      aria-busy={isLoading}
      className={`ai-inline-action${isLoading ? " ai-inline-action--loading" : ""}`}
      disabled={disabled}
      onClick={onClick}
      title="Mejorar redacción clínica"
      type="button"
    >
      {isLoading ? (
        <span className="ai-inline-action__spinner" aria-hidden="true" />
      ) : (
        <Sparkles aria-hidden="true" className="ai-inline-action__icon" size={15} />
      )}
      <span className="ai-inline-action__label">
        {isLoading ? loadingLabel : label}
      </span>
    </button>
  );
}

function AiSuggestionInlinePanel({
  review,
  onClose,
  onToast,
}: {
  review: AiReviewState;
  onClose: () => void;
  onToast: (title: string, detail?: string, variant?: "success" | "error") => void;
}) {
  const [isCopied, setIsCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(review.suggestion);
      setIsCopied(true);
      onToast("Sugerencia copiada.", undefined, "success");
      window.setTimeout(() => setIsCopied(false), 1800);
    } catch {
      onToast("No se pudo copiar el texto.", undefined, "error");
    }
  }

  function handleUse() {
    review.onUse?.(review.suggestion);
    onClose();
  }

  return (
    <span className="ai-suggestion-card" role="status">
      <span className="ai-suggestion-card__header">
        <span className="ai-suggestion-card__title">
          <Sparkles aria-hidden="true" size={16} />
          {review.kind === "summary" ? "Resumen IA" : "Sugerencia de redacción"}
        </span>
        <button
          aria-label="Descartar sugerencia"
          className="ai-suggestion-card__close"
          onClick={onClose}
          type="button"
        >
          <X aria-hidden="true" size={15} />
        </button>
      </span>
      <span className="ai-suggestion-card__context">
        {review.kind === "summary"
          ? "Revisa el resumen antes de aplicarlo."
          : "Revisa la sugerencia antes de aplicarla."}
      </span>
      <span className="ai-suggestion-card__comparison">
        {review.kind === "rewrite" ? (
          <span className="ai-suggestion-card__block ai-suggestion-card__block--original">
            <span className="ai-suggestion-card__block-title">Texto original</span>
            <span className="ai-suggestion-card__text">{review.originalText}</span>
          </span>
        ) : null}
        <span className="ai-suggestion-card__block ai-suggestion-card__block--suggestion">
          <span className="ai-suggestion-card__block-title">
            {review.kind === "summary" ? "Resumen sugerido" : "Sugerencia mejorada"}
          </span>
          <span className="ai-suggestion-card__text">{review.suggestion}</span>
        </span>
      </span>
      <span className="ai-suggestion-card__clinical-note">
        La sugerencia mejora la redacción del texto escrito. No reemplaza el criterio médico.
      </span>
      <span className="ai-disclaimer">{review.disclaimer}</span>
      <span className="ai-suggestion-card__actions">
        <button className="secondary-button" onClick={onClose} type="button">
          Descartar
        </button>
        <button
          className="secondary-button"
          onClick={() => void handleCopy()}
          type="button"
        >
          <Copy aria-hidden="true" size={16} />
          {isCopied ? "Copiada" : "Copiar"}
        </button>
        {review.onUse ? (
          <button className="primary-button" onClick={handleUse} type="button">
            <Check aria-hidden="true" size={16} />
            {review.kind === "summary" ? "Insertar en consulta" : "Usar sugerencia"}
          </button>
        ) : null}
      </span>
    </span>
  );
}

function AiLoadingInlinePanel() {
  return (
    <span className="ai-loading-panel" role="status">
      <span className="ai-loading-panel__spinner" aria-hidden="true" />
      <span>El asistente está preparando una sugerencia...</span>
    </span>
  );
}

function AiInlineNotice({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  return (
    <span className="ai-inline-notice" role="alert">
      <span>{message}</span>
      <button
        aria-label="Cerrar mensaje de IA"
        className="ai-suggestion-card__close"
        onClick={onDismiss}
        type="button"
      >
        <X aria-hidden="true" size={15} />
      </button>
    </span>
  );
}

function hasConsultationClinicalContent(consultation: ConsultationSummaryPayload) {
  return [
    consultation.reason,
    consultation.anamnesis,
    consultation.physical_exam,
    consultation.presumptive_diagnosis,
    consultation.diagnostic_plan,
    consultation.therapeutic_plan,
    consultation.instructions,
  ].some((value) => Boolean(value?.trim()));
}

function getRewriteErrorMessage(error: unknown) {
  if (error instanceof ApiClientError && error.status === 429) {
    return AI_PROVIDER_QUOTA_EXCEEDED_MESSAGE;
  }

  if (error instanceof ApiClientError && error.status === 503) {
    return "La función de IA no está disponible en este momento.";
  }

  return "No pudimos generar la sugerencia en este momento.";
}

function getSummaryErrorMessage(error: unknown) {
  if (error instanceof ApiClientError && error.status === 429) {
    return AI_PROVIDER_QUOTA_EXCEEDED_MESSAGE;
  }

  if (error instanceof ApiClientError && error.status === 503) {
    return "La función de IA no está disponible en este momento.";
  }

  return "No pudimos generar el resumen en este momento.";
}
