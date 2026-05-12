import logging
import time
import uuid
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException

from app.core.config import get_settings
from app.schemas.ai import ConsultationSummaryInput, AIPatientContext

logger = logging.getLogger(__name__)


AI_NOT_CONFIGURED_MESSAGE = "AI service is not configured."
AI_PROVIDER_FAILED_MESSAGE = "AI provider request failed."
AI_PROVIDER_QUOTA_EXCEEDED_MESSAGE = (
    "AI provider quota exceeded. Please wait and try again later or upgrade the "
    "provider plan."
)
PROVIDER_MESSAGE_MAX_LENGTH = 240


class AIProviderRequestError(Exception):
    def __init__(
        self,
        *,
        error_type: str,
        provider_status_code: int | None = None,
        provider_message: str | None = None,
    ) -> None:
        self.error_type = error_type
        self.provider_status_code = provider_status_code
        self.provider_message = provider_message
        super().__init__(error_type)


class AIService:
    def rewrite_clinical_note(
        self,
        *,
        field: str,
        text: str,
        patient_context: AIPatientContext | None,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> str:
        return self._run_feature(
            feature="rewrite_clinical_note",
            tenant_id=tenant_id,
            user_id=user_id,
            instructions=self._rewrite_instructions(),
            input_text=self._build_rewrite_input(field, text, patient_context),
            max_output_tokens=512,
        )

    def generate_consultation_summary(
        self,
        *,
        consultation: ConsultationSummaryInput,
        summary_type: str,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
    ) -> str:
        return self._run_feature(
            feature="generate_consultation_summary",
            tenant_id=tenant_id,
            user_id=user_id,
            instructions=self._summary_instructions(summary_type),
            input_text=self._build_summary_input(consultation),
            max_output_tokens=768,
        )

    def _run_feature(
        self,
        *,
        feature: str,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
    ) -> str:
        started_at = time.monotonic()
        settings = get_settings()
        provider = settings.ai_provider.lower().strip()
        model = settings.ai_model.strip()
        try:
            self._ensure_configured(provider=provider, model=model)
            result = self._request_provider_response(
                provider=provider,
                instructions=instructions,
                input_text=input_text,
                max_output_tokens=max_output_tokens,
            )
            normalized_result = self._normalize_response_text(result)
            self._log_request(
                feature=feature,
                provider=provider,
                model=model,
                tenant_id=tenant_id,
                user_id=user_id,
                status="success",
                started_at=started_at,
            )
            return normalized_result
        except HTTPException as exc:
            self._log_request(
                feature=feature,
                provider=provider,
                model=model,
                tenant_id=tenant_id,
                user_id=user_id,
                status="error",
                started_at=started_at,
                error_type=str(exc.status_code),
            )
            raise
        except AIProviderRequestError as exc:
            self._log_request(
                feature=feature,
                provider=provider,
                model=model,
                tenant_id=tenant_id,
                user_id=user_id,
                status="error",
                started_at=started_at,
                error_type=exc.error_type,
                provider_status_code=exc.provider_status_code,
                provider_message=exc.provider_message,
            )
            if exc.provider_status_code == 429:
                raise HTTPException(
                    status_code=429,
                    detail=AI_PROVIDER_QUOTA_EXCEEDED_MESSAGE,
                ) from exc

            raise HTTPException(
                status_code=502,
                detail=AI_PROVIDER_FAILED_MESSAGE,
            ) from exc
        except Exception as exc:
            self._log_request(
                feature=feature,
                provider=provider,
                model=model,
                tenant_id=tenant_id,
                user_id=user_id,
                status="error",
                started_at=started_at,
                error_type=exc.__class__.__name__,
            )
            raise HTTPException(
                status_code=502,
                detail=AI_PROVIDER_FAILED_MESSAGE,
            ) from exc

    def _ensure_configured(self, *, provider: str, model: str) -> None:
        settings = get_settings()
        if not settings.ai_features_enabled or not provider or not model:
            raise HTTPException(status_code=503, detail=AI_NOT_CONFIGURED_MESSAGE)

        if provider == "openai" and (settings.openai_api_key or "").strip():
            return

        if provider == "gemini" and (settings.gemini_api_key or "").strip():
            return

        raise HTTPException(status_code=503, detail=AI_NOT_CONFIGURED_MESSAGE)

    def _request_provider_response(
        self,
        *,
        provider: str,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
    ) -> str:
        if provider == "openai":
            return self._request_openai_response(
                instructions=instructions,
                input_text=input_text,
                max_output_tokens=max_output_tokens,
            )

        if provider == "gemini":
            return self._request_gemini_response(
                instructions=instructions,
                input_text=input_text,
                max_output_tokens=max_output_tokens,
            )

        raise HTTPException(status_code=503, detail=AI_NOT_CONFIGURED_MESSAGE)

    def _request_openai_response(
        self,
        *,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
    ) -> str:
        settings = get_settings()
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.post(
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.ai_model,
                        "instructions": instructions,
                        "input": input_text,
                        "max_output_tokens": max_output_tokens,
                        "store": False,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AIProviderRequestError(
                error_type="provider_http_status",
                provider_status_code=exc.response.status_code,
                provider_message=self._extract_provider_error_message(exc.response),
            ) from exc
        except httpx.RequestError as exc:
            raise AIProviderRequestError(
                error_type=exc.__class__.__name__,
                provider_message=self._sanitize_provider_message(str(exc)),
            ) from exc

        return self._extract_response_text(response.json())

    def _request_gemini_response(
        self,
        *,
        instructions: str,
        input_text: str,
        max_output_tokens: int,
    ) -> str:
        settings = get_settings()
        model = settings.ai_model.strip()
        model_path = quote(model, safe="")
        try:
            with httpx.Client(timeout=20.0) as client:
                response = client.post(
                    (
                        "https://generativelanguage.googleapis.com/v1beta/"
                        f"models/{model_path}:generateContent"
                    ),
                    headers={
                        "x-goog-api-key": settings.gemini_api_key or "",
                        "Content-Type": "application/json",
                    },
                    json={
                        "systemInstruction": {
                            "parts": [
                                {
                                    "text": instructions,
                                },
                            ],
                        },
                        "contents": [
                            {
                                "role": "user",
                                "parts": [
                                    {
                                        "text": input_text,
                                    },
                                ],
                            },
                        ],
                        "generationConfig": {
                            "maxOutputTokens": max_output_tokens,
                            "temperature": 0.2,
                            "topP": 0.8,
                            **self._gemini_thinking_config(model),
                        },
                    },
                )
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError as exc:
                    self._log_gemini_debug(
                        "Gemini response JSON parse error | "
                        f"error_type={exc.__class__.__name__}"
                    )
                    raise AIProviderRequestError(
                        error_type="provider_response_invalid_json"
                    ) from exc
                self._log_gemini_payload_metadata(payload)
                return self._extract_gemini_response_text(payload)
        except httpx.HTTPStatusError as exc:
            provider_message = self._extract_provider_error_message(exc.response)
            logger.warning(
                "Gemini HTTP error | "
                f"status_code={exc.response.status_code} | "
                f"provider_message={provider_message}"
            )
            raise AIProviderRequestError(
                error_type="provider_http_status",
                provider_status_code=exc.response.status_code,
                provider_message=provider_message,
            ) from exc
        except httpx.RequestError as exc:
            provider_message = self._sanitize_provider_message(str(exc))
            logger.warning(
                "Gemini request error | "
                f"error_type={exc.__class__.__name__} | "
                f"provider_message={provider_message}"
            )
            raise AIProviderRequestError(
                error_type=exc.__class__.__name__,
                provider_message=provider_message,
            ) from exc

    def _gemini_thinking_config(self, model: str) -> dict[str, Any]:
        normalized_model = model.lower().strip()
        supports_disabled_thinking = (
            normalized_model.startswith("gemini-2.5-flash")
            or normalized_model.startswith("models/gemini-2.5-flash")
        )
        if not supports_disabled_thinking:
            return {}

        return {
            "thinkingConfig": {
                "thinkingBudget": 0,
            },
        }

    def _extract_response_text(self, payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        for output_item in payload.get("output", []):
            if not isinstance(output_item, dict):
                continue
            for content_item in output_item.get("content", []):
                if (
                    isinstance(content_item, dict)
                    and content_item.get("type") == "output_text"
                    and isinstance(content_item.get("text"), str)
                ):
                    text = content_item["text"].strip()
                    if text:
                        return text

        raise AIProviderRequestError(error_type="provider_response_missing_text")

    def _log_gemini_debug(self, message: str, *, extra: dict[str, Any] | None = None) -> None:
        if get_settings().ai_debug_logs:
            logger.warning(message, extra=extra)

    def _log_gemini_payload_metadata(self, payload: dict[str, Any]) -> None:
        candidates = payload.get("candidates")
        prompt_feedback = payload.get("promptFeedback")

        self._log_gemini_debug(
            "Gemini payload received | "
            f"payload_keys={list(payload.keys())} | "
            f"has_candidates={isinstance(candidates, list)} | "
            f"candidates_count={len(candidates) if isinstance(candidates, list) else None} | "
            f"has_prompt_feedback={isinstance(prompt_feedback, dict)} | "
            "prompt_feedback_block_reason="
            f"{prompt_feedback.get('blockReason') if isinstance(prompt_feedback, dict) else None}",
            extra={
                "payload_keys": list(payload.keys()),
                "candidates_count": len(candidates)
                if isinstance(candidates, list)
                else None,
                "prompt_feedback_present": isinstance(prompt_feedback, dict),
                "prompt_feedback_block_reason": prompt_feedback.get("blockReason")
                if isinstance(prompt_feedback, dict)
                else None,
            },
        )

        if not isinstance(candidates, list):
            return

        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                self._log_gemini_debug(
                    "Gemini candidate metadata | "
                    f"candidate_index={index} | "
                    "is_dict=False",
                    extra={"candidate_index": index},
                )
                continue

            content = candidate.get("content")
            parts = None
            if isinstance(content, dict):
                parts = content.get("parts")

            text_parts_count = 0
            total_text_length = 0

            if isinstance(parts, list):
                for part in parts:
                    if (
                        isinstance(part, dict)
                        and isinstance(part.get("text"), str)
                        and part.get("text").strip()
                    ):
                        text_parts_count += 1
                        total_text_length += len(part["text"].strip())

            self._log_gemini_debug(
                "Gemini candidate metadata | "
                f"candidate_index={index} | "
                f"finish_reason={candidate.get('finishReason')} | "
                f"has_content={isinstance(content, dict)} | "
                f"parts_count={len(parts) if isinstance(parts, list) else None} | "
                f"text_parts_count={text_parts_count} | "
                f"total_text_length={total_text_length} | "
                "safety_ratings_count="
                f"{len(candidate.get('safetyRatings', [])) if isinstance(candidate.get('safetyRatings'), list) else None}",
                extra={
                    "candidate_index": index,
                    "finish_reason": candidate.get("finishReason"),
                    "has_content": isinstance(content, dict),
                    "parts_count": len(parts) if isinstance(parts, list) else None,
                    "text_parts_count": text_parts_count,
                    "total_text_length": total_text_length,
                    "safety_ratings_count": len(candidate.get("safetyRatings", []))
                    if isinstance(candidate.get("safetyRatings"), list)
                    else None,
                },
            )

    def _extract_gemini_response_text(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            self._log_gemini_debug(
                "Gemini response missing text | "
                f"payload_keys={list(payload.keys())} | "
                "reason=missing_candidates"
            )
            raise AIProviderRequestError(error_type="provider_response_missing_text")

        for candidate_index, candidate in enumerate(candidates):
            if not isinstance(candidate, dict):
                self._log_gemini_debug(
                    "Skipping invalid Gemini candidate | "
                    f"candidate_index={candidate_index}",
                    extra={"candidate_index": candidate_index},
                )
                continue

            finish_reason = candidate.get("finishReason")

            content = candidate.get("content")
            parts = content.get("parts") if isinstance(content, dict) else None

            text_parts = []
            if isinstance(parts, list):
                text_parts = [
                    part.get("text").strip()
                    for part in parts
                    if isinstance(part, dict)
                    and isinstance(part.get("text"), str)
                    and part.get("text").strip()
                ]

            self._log_gemini_debug(
                "Extracting Gemini response text | "
                f"candidate_index={candidate_index} | "
                f"finish_reason={finish_reason} | "
                f"has_content={isinstance(content, dict)} | "
                f"parts_count={len(parts) if isinstance(parts, list) else None} | "
                f"text_parts_count={len(text_parts)} | "
                f"total_text_length={sum(len(text) for text in text_parts)}",
                extra={
                    "candidate_index": candidate_index,
                    "finish_reason": finish_reason,
                    "has_content": isinstance(content, dict),
                    "parts_count": len(parts) if isinstance(parts, list) else None,
                    "text_parts_count": len(text_parts),
                    "total_text_length": sum(len(text) for text in text_parts),
                },
            )

            if finish_reason == "MAX_TOKENS":
                raise AIProviderRequestError(
                    error_type="provider_response_max_tokens",
                    provider_message=(
                        "Gemini response reached max output tokens."
                        if text_parts
                        else "Gemini response reached max output tokens without text."
                    ),
                )

            if text_parts:
                return "\n".join(text_parts)

        self._log_gemini_debug(
            "Gemini response missing text | "
            f"candidates_count={len(candidates)} | "
            "reason=no_text_parts"
        )
        raise AIProviderRequestError(error_type="provider_response_missing_text")

    def _normalize_response_text(self, text: str) -> str:
        normalized = text.strip().strip('"').strip()
        if not normalized:
            raise AIProviderRequestError(error_type="provider_response_empty_text")
        return normalized

    def _extract_provider_error_message(self, response: httpx.Response) -> str | None:
        candidate: str | None = None
        try:
            payload = response.json()
        except ValueError:
            candidate = response.text
        else:
            if isinstance(payload, dict):
                error_payload = payload.get("error")
                if isinstance(error_payload, dict):
                    message = error_payload.get("message")
                    error_type = error_payload.get("type") or error_payload.get("status")
                    error_code = error_payload.get("code")
                    parts = [
                        str(value)
                        for value in [error_type, error_code, message]
                        if value is not None and str(value).strip()
                    ]
                    candidate = " | ".join(parts)
                else:
                    message = payload.get("message")
                    if isinstance(message, str):
                        candidate = message

        return self._sanitize_provider_message(candidate)

    def _sanitize_provider_message(self, message: str | None) -> str | None:
        if not message:
            return None

        compact_message = " ".join(message.split())
        if not compact_message:
            return None

        sensitive_markers = [
            "authorization",
            "bearer ",
            "openai_api_key",
            "sk-",
            "campo clinico:",
            "contexto del paciente:",
            "texto original:",
            "motivo:",
            "anamnesis:",
            "examen fisico:",
            "diagnostico presuntivo:",
            "plan diagnostico:",
            "plan terapeutico:",
            "indicaciones:",
            "paciente:",
            "especie:",
            "raza:",
            "sexo:",
            "edad:",
        ]
        normalized_message = compact_message.lower()
        if any(marker in normalized_message for marker in sensitive_markers):
            return None

        return compact_message[:PROVIDER_MESSAGE_MAX_LENGTH]

    def _rewrite_instructions(self) -> str:
        return (
            "Eres un asistente de redaccion clinica veterinaria. "
            "Tu funcion es mejorar claridad, estructura y tono profesional. "
            "No agregues datos no proporcionados. "
            "No emitas diagnostico definitivo. "
            "No sugieras tratamientos. "
            "No inventes signos, sintomas, hallazgos, resultados ni antecedentes. "
            "Conserva el sentido clinico del texto original. "
            "Manten una extension proporcional al texto original. "
            "No resumas en exceso. "
            "No cortes frases. "
            "Devuelve una redaccion completa, coherente y terminada. "
            "Responde solo con el texto mejorado, sin explicacion adicional. "
            "Idioma: espanol clinico claro."
        )

    def _summary_instructions(self, summary_type: str) -> str:
        tone_instruction = (
            "Para clinical, usa lenguaje clinico veterinario."
            if summary_type == "clinical"
            else "Para owner_friendly, usa lenguaje claro para propietario sin alarmismo."
        )
        return (
            "Resume unicamente la informacion enviada. "
            "No inventes diagnosticos. "
            "No agregues tratamientos no incluidos. "
            "No prometas evolucion. "
            "No reemplaces el criterio veterinario. "
            "Manten tono profesional. "
            f"{tone_instruction} "
            "Responde solo con el resumen."
        )

    def _build_rewrite_input(
        self,
        field: str,
        text: str,
        patient_context: AIPatientContext | None,
    ) -> str:
        context = self._format_patient_context(patient_context)
        return (
            f"Campo clinico: {field}\n"
            f"Contexto del paciente:\n{context}\n"
            f"Texto original:\n{text}"
        )

    def _build_summary_input(self, consultation: ConsultationSummaryInput) -> str:
        fields = [
            ("Paciente", consultation.patient_name),
            ("Especie", consultation.species),
            ("Raza", consultation.breed),
            ("Sexo", consultation.sex),
            ("Edad", consultation.age),
            ("Peso kg", consultation.weight_kg),
            ("Motivo", consultation.reason),
            ("Anamnesis", consultation.anamnesis),
            ("Examen fisico", consultation.physical_exam),
            ("Diagnostico presuntivo", consultation.presumptive_diagnosis),
            ("Plan diagnostico", consultation.diagnostic_plan),
            ("Plan terapeutico", consultation.therapeutic_plan),
            ("Indicaciones", consultation.instructions),
        ]
        return "\n".join(
            f"{label}: {value}" for label, value in fields if value is not None
        )

    def _format_patient_context(
        self,
        patient_context: AIPatientContext | None,
    ) -> str:
        if patient_context is None:
            return "No proporcionado."

        fields = [
            ("Nombre", patient_context.name),
            ("Especie", patient_context.species),
            ("Raza", patient_context.breed),
            ("Sexo", patient_context.sex),
            ("Edad", patient_context.age),
            ("Peso kg", patient_context.weight_kg),
        ]
        values = [f"{label}: {value}" for label, value in fields if value is not None]
        return "\n".join(values) if values else "No proporcionado."

    def _log_request(
        self,
        *,
        feature: str,
        provider: str,
        model: str,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID | None,
        status: str,
        started_at: float,
        error_type: str | None = None,
        provider_status_code: int | None = None,
        provider_message: str | None = None,
    ) -> None:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.warning(
            "AI feature request finished | "
            f"feature={feature} | "
            f"provider={provider} | "
            f"model={model} | "
            f"tenant_id={tenant_id} | "
            f"user_id={user_id} | "
            f"status={status} | "
            f"duration_ms={duration_ms} | "
            f"error_type={error_type} | "
            f"provider_status_code={provider_status_code} | "
            f"provider_message={provider_message}",
            extra={
                "feature": feature,
                "provider": provider,
                "model": model,
                "tenant_id": str(tenant_id),
                "user_id": str(user_id) if user_id is not None else None,
                "status": status,
                "duration_ms": duration_ms,
                "error_type": error_type,
                "provider_status_code": provider_status_code,
                "provider_message": provider_message,
            },
        )
