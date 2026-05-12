import httpx

from app.core.config import get_settings
from app.services.ai_service import (
    AIProviderRequestError,
    AIService,
    AI_PROVIDER_QUOTA_EXCEEDED_MESSAGE,
)


def _configure_ai(monkeypatch) -> None:
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()


def _configure_gemini(monkeypatch, *, model: str = "gemini-2.5-flash") -> None:
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_MODEL", model)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-api-key")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()


def _tenant_headers(tenant) -> dict[str, str]:
    return {"X-Tenant-Id": str(tenant.id)}


def _gemini_response(payload: dict, *, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
    )


def _patch_gemini_post(monkeypatch, provider_post):
    original_post = httpx.Client.post

    def wrapped_post(self, url, *args, **kwargs):
        if str(url).startswith("/"):
            return original_post(self, url, *args, **kwargs)
        return provider_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "post", wrapped_post)


def test_rewrite_clinical_note_returns_suggestion_when_configured(
    client,
    tenant,
    monkeypatch,
):
    _configure_ai(monkeypatch)
    provider_called = False

    def fake_request(self, *, instructions, input_text, max_output_tokens):
        nonlocal provider_called
        provider_called = True
        assert "diagnostico_presuntivo" in input_text
        assert max_output_tokens == 512
        return "Paciente con cuadro gastrointestinal de 48 horas de evolucion."

    monkeypatch.setattr(AIService, "_request_openai_response", fake_request)

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "diagnostico_presuntivo",
            "text": "vomito hace dos dias, come poco, abdomen sensible",
            "patient_context": {
                "name": "Elias",
                "species": "Canino",
                "breed": "Galgo",
                "sex": "Macho",
                "age": "10 anos",
                "weight_kg": 30.0,
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suggestion"] == (
        "Paciente con cuadro gastrointestinal de 48 horas de evolucion."
    )
    assert body["disclaimer"] == "Texto sugerido por IA. Revisa antes de guardar."
    assert provider_called is True


def test_rewrite_clinical_note_returns_503_when_ai_is_not_configured(
    client,
    tenant,
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-4o-mini")
    get_settings.cache_clear()

    def fail_if_called(self, *, instructions, input_text, max_output_tokens):
        raise AssertionError("Provider should not be called")

    monkeypatch.setattr(AIService, "_request_openai_response", fail_if_called)

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "diagnostico_presuntivo",
            "text": "vomito hace dos dias",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "AI service is not configured."}


def test_rewrite_clinical_note_logs_provider_metadata_without_sensitive_content(
    client,
    tenant,
    monkeypatch,
    caplog,
):
    _configure_ai(monkeypatch)
    caplog.set_level("INFO", logger="app.services.ai_service")

    def fake_request(self, *, instructions, input_text, max_output_tokens):
        raise AIProviderRequestError(
            error_type="provider_http_status",
            provider_status_code=400,
            provider_message=(
                "invalid_request_error | unsupported_parameter | "
                "Unknown parameter: temperature"
            ),
        )

    monkeypatch.setattr(AIService, "_request_openai_response", fake_request)

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "diagnostico_presuntivo",
            "text": "vomito hace dos dias, abdomen sensible",
        },
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI provider request failed."}

    log_record = next(
        record
        for record in caplog.records
        if record.name == "app.services.ai_service"
        and getattr(record, "feature", None) == "rewrite_clinical_note"
    )
    assert log_record.error_type == "provider_http_status"
    assert log_record.provider_status_code == 400
    assert (
        log_record.provider_message
        == "invalid_request_error | unsupported_parameter | Unknown parameter: temperature"
    )
    assert "abdomen sensible" not in caplog.text
    assert "test-api-key" not in caplog.text


def test_rewrite_clinical_note_fails_validation_when_text_is_empty(client, tenant):
    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "diagnostico_presuntivo",
            "text": "",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_rewrite_clinical_note_rejects_excessively_long_text(client, tenant):
    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "diagnostico_presuntivo",
            "text": "a" * 4001,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_generate_consultation_summary_returns_summary_when_configured(
    client,
    tenant,
    monkeypatch,
):
    _configure_ai(monkeypatch)
    provider_called = False

    def fake_request(self, *, instructions, input_text, max_output_tokens):
        nonlocal provider_called
        provider_called = True
        assert "Motivo: Vomito y decaimiento" in input_text
        assert "lenguaje clinico veterinario" in instructions
        assert max_output_tokens == 768
        return "Elias consulta por vomito, hiporexia y decaimiento."

    monkeypatch.setattr(AIService, "_request_openai_response", fake_request)

    response = client.post(
        "/api/v1/ai/generate-consultation-summary",
        headers=_tenant_headers(tenant),
        json={
            "consultation": {
                "patient_name": "Elias",
                "species": "Canino",
                "breed": "Galgo",
                "sex": "Macho",
                "age": "10 anos",
                "weight_kg": 30.0,
                "reason": "Vomito y decaimiento",
                "anamnesis": "Vomito hace dos dias, come poco.",
                "physical_exam": "Sensibilidad abdominal.",
                "presumptive_diagnosis": "Cuadro gastrointestinal en evaluacion.",
                "diagnostic_plan": "Hemograma.",
                "therapeutic_plan": "Manejo sintomatico segun criterio veterinario.",
                "instructions": "Vigilar evolucion.",
            },
            "summary_type": "clinical",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "Elias consulta por vomito, hiporexia y decaimiento."
    assert body["disclaimer"] == "Texto sugerido por IA. Revisa antes de guardar."
    assert provider_called is True


def test_rewrite_clinical_note_returns_suggestion_with_gemini(
    client,
    tenant,
    monkeypatch,
):
    _configure_gemini(monkeypatch)
    provider_called = False

    def fake_request(self, *, instructions, input_text, max_output_tokens):
        nonlocal provider_called
        provider_called = True
        assert "No agregues datos no proporcionados" in instructions
        assert "Texto original:" in input_text
        assert max_output_tokens == 512
        return "Paciente con vomito de dos dias de evolucion."

    def fail_if_called(self, *, instructions, input_text, max_output_tokens):
        raise AssertionError("OpenAI provider should not be called")

    monkeypatch.setattr(AIService, "_request_gemini_response", fake_request)
    monkeypatch.setattr(AIService, "_request_openai_response", fail_if_called)

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "anamnesis",
            "text": "vomito hace dos dias, come poco",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["suggestion"] == "Paciente con vomito de dos dias de evolucion."
    assert body["disclaimer"] == "Texto sugerido por IA. Revisa antes de guardar."
    assert provider_called is True


def test_generate_consultation_summary_returns_summary_with_gemini(
    client,
    tenant,
    monkeypatch,
):
    _configure_gemini(monkeypatch, model="gemini-2.5-flash-lite")
    provider_called = False

    def fake_request(self, *, instructions, input_text, max_output_tokens):
        nonlocal provider_called
        provider_called = True
        assert "Resume unicamente la informacion enviada" in instructions
        assert "Motivo: Vomito y decaimiento" in input_text
        assert max_output_tokens == 768
        return "Consulta por vomito y decaimiento."

    def fail_if_called(self, *, instructions, input_text, max_output_tokens):
        raise AssertionError("OpenAI provider should not be called")

    monkeypatch.setattr(AIService, "_request_gemini_response", fake_request)
    monkeypatch.setattr(AIService, "_request_openai_response", fail_if_called)

    response = client.post(
        "/api/v1/ai/generate-consultation-summary",
        headers=_tenant_headers(tenant),
        json={
            "consultation": {
                "reason": "Vomito y decaimiento",
                "anamnesis": "Vomito hace dos dias.",
            },
            "summary_type": "clinical",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"] == "Consulta por vomito y decaimiento."
    assert body["disclaimer"] == "Texto sugerido por IA. Revisa antes de guardar."
    assert provider_called is True


def test_rewrite_clinical_note_returns_503_when_gemini_key_is_missing(
    client,
    tenant,
    monkeypatch,
):
    _configure_gemini(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()

    def fail_if_called(self, *, instructions, input_text, max_output_tokens):
        raise AssertionError("Provider should not be called")

    monkeypatch.setattr(AIService, "_request_gemini_response", fail_if_called)

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "anamnesis",
            "text": "vomito hace dos dias",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "AI service is not configured."}


def test_rewrite_clinical_note_returns_503_when_provider_is_unsupported(
    client,
    tenant,
    monkeypatch,
):
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_MODEL", "claude-test")
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-api-key")
    get_settings.cache_clear()

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "anamnesis",
            "text": "vomito hace dos dias",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "AI service is not configured."}


def test_rewrite_clinical_note_returns_503_when_gemini_model_is_empty(
    client,
    tenant,
    monkeypatch,
):
    _configure_gemini(monkeypatch, model="")

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "anamnesis",
            "text": "vomito hace dos dias",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "AI service is not configured."}


def test_rewrite_clinical_note_returns_429_when_gemini_quota_is_exceeded(
    client,
    tenant,
    monkeypatch,
    caplog,
):
    _configure_gemini(monkeypatch)
    caplog.set_level("WARNING", logger="app.services.ai_service")

    def fake_request(self, *, instructions, input_text, max_output_tokens):
        raise AIProviderRequestError(
            error_type="provider_http_status",
            provider_status_code=429,
            provider_message="RESOURCE_EXHAUSTED | Too many requests",
        )

    monkeypatch.setattr(AIService, "_request_gemini_response", fake_request)

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "anamnesis",
            "text": "vomito hace dos dias",
        },
    )

    assert response.status_code == 429
    assert response.json() == {"detail": AI_PROVIDER_QUOTA_EXCEEDED_MESSAGE}
    assert "provider_status_code=429" in caplog.text
    assert "provider_http_status" in caplog.text
    assert "RESOURCE_EXHAUSTED" in caplog.text
    assert "vomito hace dos dias" not in caplog.text
    assert "test-gemini-api-key" not in caplog.text


def test_rewrite_clinical_note_returns_502_when_gemini_http_fails(
    client,
    tenant,
    monkeypatch,
):
    _configure_gemini(monkeypatch)

    def fake_request(self, *, instructions, input_text, max_output_tokens):
        raise AIProviderRequestError(
            error_type="provider_http_status",
            provider_status_code=500,
            provider_message="INTERNAL | Provider failure",
        )

    monkeypatch.setattr(AIService, "_request_gemini_response", fake_request)

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "anamnesis",
            "text": "vomito hace dos dias",
        },
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI provider request failed."}


def test_rewrite_clinical_note_returns_502_when_gemini_response_has_no_text(
    client,
    tenant,
    monkeypatch,
):
    _configure_gemini(monkeypatch)

    def fake_request(self, *, instructions, input_text, max_output_tokens):
        return "   "

    monkeypatch.setattr(AIService, "_request_gemini_response", fake_request)

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "anamnesis",
            "text": "vomito hace dos dias",
        },
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI provider request failed."}


def test_gemini_http_400_logs_provider_status_and_returns_502(
    client,
    tenant,
    monkeypatch,
    caplog,
):
    _configure_gemini(monkeypatch)
    caplog.set_level("WARNING", logger="app.services.ai_service")

    def fake_post(self, url, *, headers, json):
        return _gemini_response(
            {
                "error": {
                    "code": 400,
                    "status": "INVALID_ARGUMENT",
                    "message": "Unsupported generationConfig field: thinkingConfig",
                }
            },
            status_code=400,
        )

    _patch_gemini_post(monkeypatch, fake_post)

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "anamnesis",
            "text": "dolor en extremidad anterior derecha",
        },
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI provider request failed."}
    assert "Gemini HTTP error | status_code=400" in caplog.text
    assert "provider_http_status" in caplog.text
    assert "Unsupported generationConfig field: thinkingConfig" in caplog.text
    assert "dolor en extremidad" not in caplog.text
    assert "test-gemini-api-key" not in caplog.text


def test_gemini_payload_with_stop_finish_reason_returns_text(
    monkeypatch,
):
    _configure_gemini(monkeypatch)

    def fake_post(self, url, *, headers, json):
        return _gemini_response(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        "Paciente con antecedente de gastroenteritis "
                                        "severa hace 6 meses."
                                    )
                                }
                            ]
                        },
                    }
                ]
            }
        )

    _patch_gemini_post(monkeypatch, fake_post)

    result = AIService()._request_gemini_response(
        instructions="Instrucciones seguras",
        input_text="Texto clinico",
        max_output_tokens=512,
    )

    assert result == "Paciente con antecedente de gastroenteritis severa hace 6 meses."


def test_gemini_payload_with_multiple_text_parts_concatenates_text(
    monkeypatch,
):
    _configure_gemini(monkeypatch)

    def fake_post(self, url, *, headers, json):
        return _gemini_response(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {"text": "Primera frase completa."},
                                {"text": "Segunda frase completa."},
                            ]
                        },
                    }
                ]
            }
        )

    _patch_gemini_post(monkeypatch, fake_post)

    result = AIService()._request_gemini_response(
        instructions="Instrucciones seguras",
        input_text="Texto clinico",
        max_output_tokens=512,
    )

    assert result == "Primera frase completa.\nSegunda frase completa."


def test_gemini_payload_with_max_tokens_returns_502(
    client,
    tenant,
    monkeypatch,
):
    _configure_gemini(monkeypatch)

    def fake_post(self, url, *, headers, json):
        return _gemini_response(
            {
                "candidates": [
                    {
                        "finishReason": "MAX_TOKENS",
                        "content": {"parts": [{"text": "Respuesta incompleta"}]},
                    }
                ]
            }
        )

    _patch_gemini_post(monkeypatch, fake_post)

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "anamnesis",
            "text": "dolor en extremidad anterior derecha",
        },
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI provider request failed."}


def test_gemini_payload_without_candidates_raises_controlled_error(
    monkeypatch,
):
    _configure_gemini(monkeypatch)

    def fake_post(self, url, *, headers, json):
        return _gemini_response({"promptFeedback": {"blockReason": "SAFETY"}})

    _patch_gemini_post(monkeypatch, fake_post)

    try:
        AIService()._request_gemini_response(
            instructions="Instrucciones seguras",
            input_text="Texto clinico",
            max_output_tokens=512,
        )
    except AIProviderRequestError as exc:
        assert exc.error_type == "provider_response_missing_text"
    else:
        raise AssertionError("Expected AIProviderRequestError")


def test_gemini_payload_with_candidates_but_without_text_raises_controlled_error(
    monkeypatch,
):
    _configure_gemini(monkeypatch)

    def fake_post(self, url, *, headers, json):
        return _gemini_response(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"inlineData": {"mimeType": "text/plain"}}]},
                    }
                ]
            }
        )

    _patch_gemini_post(monkeypatch, fake_post)

    try:
        AIService()._request_gemini_response(
            instructions="Instrucciones seguras",
            input_text="Texto clinico",
            max_output_tokens=512,
        )
    except AIProviderRequestError as exc:
        assert exc.error_type == "provider_response_missing_text"
    else:
        raise AssertionError("Expected AIProviderRequestError")


def test_gemini_rewrite_request_uses_expected_generation_config(
    client,
    tenant,
    monkeypatch,
):
    _configure_gemini(monkeypatch, model="gemini-2.5-flash")
    captured_payload = {}

    def fake_post(self, url, *, headers, json):
        captured_payload.update(json)
        return _gemini_response(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "Texto reescrito completo."}]},
                    }
                ]
            }
        )

    _patch_gemini_post(monkeypatch, fake_post)

    response = client.post(
        "/api/v1/ai/rewrite-clinical-note",
        headers=_tenant_headers(tenant),
        json={
            "field": "anamnesis",
            "text": "dolor en extremidad anterior derecha",
        },
    )

    assert response.status_code == 200
    generation_config = captured_payload["generationConfig"]
    assert generation_config["maxOutputTokens"] == 512
    assert generation_config["topP"] == 0.8
    assert generation_config["thinkingConfig"] == {"thinkingBudget": 0}


def test_gemini_summary_request_uses_expected_generation_config(
    client,
    tenant,
    monkeypatch,
):
    _configure_gemini(monkeypatch, model="gemini-2.5-flash")
    captured_payload = {}

    def fake_post(self, url, *, headers, json):
        captured_payload.update(json)
        return _gemini_response(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "Resumen completo."}]},
                    }
                ]
            }
        )

    _patch_gemini_post(monkeypatch, fake_post)

    response = client.post(
        "/api/v1/ai/generate-consultation-summary",
        headers=_tenant_headers(tenant),
        json={
            "consultation": {
                "reason": "Vomito y decaimiento",
            },
            "summary_type": "clinical",
        },
    )

    assert response.status_code == 200
    generation_config = captured_payload["generationConfig"]
    assert generation_config["maxOutputTokens"] == 768
    assert generation_config["topP"] == 0.8
    assert generation_config["thinkingConfig"] == {"thinkingBudget": 0}


def test_gemini_2_0_request_does_not_send_thinking_config(
    monkeypatch,
):
    _configure_gemini(monkeypatch, model="gemini-2.0-flash")
    captured_payload = {}

    def fake_post(self, url, *, headers, json):
        captured_payload.update(json)
        return _gemini_response(
            {
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "Texto completo."}]},
                    }
                ]
            }
        )

    _patch_gemini_post(monkeypatch, fake_post)

    result = AIService()._request_gemini_response(
        instructions="Instrucciones seguras",
        input_text="Texto clinico",
        max_output_tokens=512,
    )

    assert result == "Texto completo."
    assert "thinkingConfig" not in captured_payload["generationConfig"]


def test_generate_consultation_summary_fails_without_clinical_information(
    client,
    tenant,
):
    response = client.post(
        "/api/v1/ai/generate-consultation-summary",
        headers=_tenant_headers(tenant),
        json={
            "consultation": {
                "patient_name": "Elias",
                "species": "Canino",
            },
            "summary_type": "clinical",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_generate_consultation_summary_returns_503_when_ai_is_not_configured(
    client,
    tenant,
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AI_FEATURES_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_MODEL", "gpt-4o-mini")
    get_settings.cache_clear()

    def fail_if_called(self, *, instructions, input_text, max_output_tokens):
        raise AssertionError("Provider should not be called")

    monkeypatch.setattr(AIService, "_request_openai_response", fail_if_called)

    response = client.post(
        "/api/v1/ai/generate-consultation-summary",
        headers=_tenant_headers(tenant),
        json={
            "consultation": {
                "reason": "Vomito y decaimiento",
            },
            "summary_type": "clinical",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "AI service is not configured."}


def test_generate_consultation_summary_rejects_invalid_summary_type(client, tenant):
    response = client.post(
        "/api/v1/ai/generate-consultation-summary",
        headers=_tenant_headers(tenant),
        json={
            "consultation": {
                "reason": "Vomito y decaimiento",
            },
            "summary_type": "complete_patient",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
