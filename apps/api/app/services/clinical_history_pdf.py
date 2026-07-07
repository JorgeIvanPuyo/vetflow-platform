from __future__ import annotations

import base64
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session
from weasyprint import HTML
from weasyprint.urls import URLFetcher

from app.core.errors import AppError
from app.models.consultation import Consultation
from app.models.exam import Exam
from app.models.owner import Owner
from app.models.patient import Patient
from app.models.patient_file_reference import PatientFileReference
from app.models.patient_preventive_care import PatientPreventiveCare
from app.models.tenant import Tenant
from app.repositories.owner import OwnerRepository
from app.schemas.patient import ClinicalHistoryPdfExportRequest
from app.services.consultation import ConsultationService
from app.services.storage import ClinicalFileStorageService


logger = logging.getLogger(__name__)

SUPPORTED_CLINIC_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_CLINIC_LOGO_SIZE_BYTES = 1024 * 1024
SLOW_PDF_RENDER_SECONDS = 10.0
TEMPLATE_DIRECTORY = Path(__file__).resolve().parent.parent / "templates"
TEMPLATE_NAME = "clinical_history_pdf.html"


class PdfAssetURLFetcher(URLFetcher):
    def fetch(self, url: str, headers=None):
        if urlparse(url).scheme != "data":
            raise ValueError("External PDF assets are not allowed")
        return super().fetch(url, headers)


PDF_ASSET_URL_FETCHER = PdfAssetURLFetcher()


@dataclass(frozen=True)
class ClinicalHistoryPdfExport:
    pdf_bytes: bytes
    filename: str
    text_lines: list[str]


class ClinicalHistoryPdfService:
    def __init__(
        self,
        db: Session,
        *,
        storage_service: ClinicalFileStorageService | None = None,
    ) -> None:
        self.db = db
        self.storage_service = storage_service
        self.consultation_service = ConsultationService(db)
        self.owner_repository = OwnerRepository(db)

    def export_patient_history_pdf(
        self,
        tenant_id: uuid.UUID,
        patient_id: uuid.UUID,
        options: ClinicalHistoryPdfExportRequest,
    ) -> ClinicalHistoryPdfExport:
        self._validate_date_range(options)
        try:
            (
                patient,
                consultations,
                exams,
                preventive_care,
                file_references,
                _follow_ups,
            ) = self.consultation_service.get_patient_clinical_history(
                tenant_id,
                patient_id,
            )
            owner = self._get_owner_for_patient(tenant_id, patient)
            clinic = self.db.get(Tenant, tenant_id)
            consultations = self._filter_by_date(
                consultations, options, self._consultation_event_date
            )
            exams = self._filter_by_date(exams, options, self._exam_event_date)
            preventive_care = self._filter_by_date(
                preventive_care, options, self._preventive_care_event_date
            )
            file_references = self._filter_by_date(
                file_references, options, self._file_reference_event_date
            )

            # Retained for compatibility with callers and existing assertions. It is
            # deliberately not used as the visual source for the PDF.
            text_lines = self.build_text_lines(
                clinic=clinic,
                patient=patient,
                owner=owner,
                consultations=consultations,
                exams=exams,
                preventive_care=preventive_care,
                file_references=file_references,
                options=options,
            )
            context = self._build_template_context(
                clinic=clinic,
                patient=patient,
                owner=owner,
                consultations=consultations,
                exams=exams,
                preventive_care=preventive_care,
                file_references=file_references,
                options=options,
            )

            render_started_at = time.perf_counter()
            pdf_bytes = self._render_pdf_from_template(context, options=options)
            render_duration = time.perf_counter() - render_started_at
            log_method = (
                logger.warning
                if render_duration > SLOW_PDF_RENDER_SECONDS
                else logger.info
            )
            log_method(
                "Clinical history PDF rendered in %.3f seconds. "
                "patient_id=%s tenant_id=%s",
                render_duration,
                patient_id,
                tenant_id,
            )
            return ClinicalHistoryPdfExport(
                pdf_bytes=pdf_bytes,
                filename=self._build_filename(patient.name),
                text_lines=text_lines,
            )
        except AppError:
            raise
        except Exception as exc:
            logger.exception(
                "Clinical history PDF export failed. patient_id=%s tenant_id=%s",
                patient_id,
                tenant_id,
            )
            raise AppError(
                500,
                "pdf_export_failed",
                "Clinical history PDF export failed",
            ) from exc

    def _build_template_context(
        self,
        *,
        clinic: Tenant | None,
        patient: Patient,
        owner: Owner | None,
        consultations: list[Consultation],
        exams: list[Exam],
        preventive_care: list[PatientPreventiveCare],
        file_references: list[PatientFileReference],
        options: ClinicalHistoryPdfExportRequest,
    ) -> dict:
        generated_at = self._format_datetime(datetime.now(timezone.utc))
        clinic_name = self._value(
            (clinic.display_name or clinic.name) if clinic is not None else None,
            "Clínica veterinaria",
        )
        owner_context = None
        if owner is not None:
            owner_context = {
                "full_name": self._value(owner.full_name),
                "phone": self._value(owner.phone),
                "email": self._value(owner.email),
                "address": self._value(owner.address),
            }

        consultation_context = []
        for consultation in consultations:
            attended_by = self._user_label(
                consultation.attending_user_name,
                consultation.attending_user_email,
            )
            created_by = self._user_label(
                consultation.created_by_user_name,
                consultation.created_by_user_email,
            )
            clinical_fields = self._non_empty_fields(
                [
                    self._field("Anamnesis", consultation.anamnesis),
                    self._field("Síntomas", consultation.symptoms),
                    self._field("Duración de síntomas", consultation.symptom_duration),
                    self._field("Antecedentes relevantes", consultation.relevant_history),
                    self._field("Hábitos y dieta", consultation.habits_and_diet),
                    self._field("Examen clínico", consultation.clinical_exam),
                    self._field("Plan diagnóstico", consultation.diagnostic_plan),
                    self._field(
                        "Notas del plan diagnóstico",
                        consultation.diagnostic_plan_notes,
                    ),
                    self._field(
                        "Resultados del plan diagnóstico",
                        consultation.diagnostic_results,
                    ),
                    self._field("Plan terapéutico", consultation.therapeutic_plan),
                    self._field(
                        "Notas del plan terapéutico",
                        consultation.therapeutic_plan_notes,
                    ),
                ]
            )
            consultation_context.append(
                {
                    "visit_date": self._format_datetime(consultation.visit_date),
                    "reason": self._value(consultation.reason),
                    "status": self._status_label(consultation.status),
                    "status_class": self._status_badge_class(consultation.status),
                    "attended_by": self._value(attended_by),
                    "created_by": (
                        created_by
                        if options.detail_level == "full"
                        and created_by
                        and created_by != attended_by
                        else None
                    ),
                    "presumptive_diagnosis": consultation.presumptive_diagnosis,
                    "final_diagnosis": consultation.final_diagnosis,
                    "indications": consultation.indications,
                    "consultation_summary": consultation.consultation_summary,
                    "clinical_fields": (
                        clinical_fields if options.detail_level == "full" else []
                    ),
                    "exam_data": (
                        self._build_consultation_exam_data(
                            consultation,
                            detail_level=options.detail_level,
                        )
                        if options.include_consultations
                        and options.include_consultation_exam_data
                        else None
                    ),
                    "medications": (
                        [
                            {
                                "name": self._value(medication.medication_name),
                                "dose_or_quantity": self._value(
                                    medication.dose_or_quantity
                                ),
                                "instructions": self._value(medication.instructions),
                            }
                            for medication in consultation.medications
                        ]
                        if options.detail_level == "full"
                        else []
                    ),
                    "study_requests": (
                        [
                            {
                                "name": self._value(study_request.name),
                                "study_type": self._study_request_type_label(
                                    study_request.study_type
                                ),
                                "notes": self._value(study_request.notes),
                            }
                            for study_request in consultation.study_requests
                        ]
                        if options.detail_level == "full"
                        else []
                    ),
                }
            )

        return {
            "document": {
                "title": "Historia clínica veterinaria",
                "generated_at": generated_at,
                "date_range": self._format_date_range(options) or "Historia completa",
                "detail_level": (
                    "Resumen"
                    if options.detail_level == "summary"
                    else "Historia completa"
                ),
                "page_size": options.page_size,
                "generated_by": "VetFlow",
            },
            "clinic": {
                "name": clinic_name,
                "phone": self._value(clinic.phone) if clinic is not None else "No indicado",
                "email": self._value(clinic.email) if clinic is not None else "No indicado",
                "address": self._value(clinic.address) if clinic is not None else "No indicado",
                "logo_data_uri": self._clinic_logo_data_uri(clinic),
                "monogram": clinic_name[:1].upper() or "V",
            },
            "patient": {
                "name": self._value(patient.name),
                "species": self._value(patient.species),
                "breed": self._value(patient.breed),
                "sex": self._value(patient.sex),
                "estimated_age": self._format_duration_or_age(patient),
                "weight": self._format_weight(patient.weight_kg),
                "allergies": self._value(patient.allergies, "Sin registros"),
                "chronic_conditions": self._value(
                    patient.chronic_conditions, "Sin registros"
                ),
            },
            "owner": owner_context,
            "sections": {
                "include_patient_data": options.include_patient_data,
                "include_owner_data": options.include_owner_data,
                "include_consultations": options.include_consultations,
                "include_consultation_exam_data": (
                    options.include_consultation_exam_data
                ),
                "include_exams": options.include_exams,
                "include_preventive_care": options.include_preventive_care,
                "include_file_references": options.include_file_references,
            },
            "consultations": consultation_context,
            "exams": [
                {
                    "exam_type": self._value(exam.exam_type),
                    "status": self._exam_status_label(exam.status),
                    "status_class": self._status_badge_class(exam.status),
                    "requested_at": self._format_datetime(exam.requested_at),
                    "performed_at": self._format_datetime(exam.performed_at),
                    "requested_by": self._value(
                        self._user_label(
                            exam.requested_by_user_name,
                            exam.requested_by_user_email,
                        )
                    ),
                    "result_summary": self._value(exam.result_summary),
                    "observations": self._value(exam.observations),
                }
                for exam in exams
            ],
            "preventive_care": [
                {
                    "care_type": self._preventive_care_type_label(record.care_type),
                    "name": self._value(record.name),
                    "applied_at": self._format_datetime(record.applied_at),
                    "next_due_at": self._format_datetime(record.next_due_at),
                    "lot_number": self._value(record.lot_number),
                    "registered_by": self._value(
                        self._user_label(
                            record.created_by_user_name,
                            record.created_by_user_email,
                        )
                    ),
                    "notes": self._value(record.notes),
                }
                for record in preventive_care
            ],
            "file_references": [
                {
                    "name": self._value(file_reference.name),
                    "file_type": self._file_type_label(file_reference.file_type),
                    "original_filename": self._value(
                        file_reference.original_filename
                    ),
                    "uploaded_at": self._format_datetime(
                        file_reference.uploaded_at or file_reference.created_at
                    ),
                    "registered_by": self._value(
                        self._user_label(
                            file_reference.created_by_user_name,
                            file_reference.created_by_user_email,
                        )
                    ),
                }
                for file_reference in file_references
            ],
        }

    def _render_pdf_from_template(
        self,
        context: dict,
        *,
        options: ClinicalHistoryPdfExportRequest,
    ) -> bytes:
        if context["document"]["page_size"] != options.page_size:
            raise ValueError("Template page size does not match export options")
        environment = Environment(
            loader=FileSystemLoader(TEMPLATE_DIRECTORY),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = environment.get_template(TEMPLATE_NAME)
        rendered_html = template.render(**context)
        return HTML(
            string=rendered_html,
            base_url=str(TEMPLATE_DIRECTORY),
            url_fetcher=PDF_ASSET_URL_FETCHER,
        ).write_pdf()

    def _clinic_logo_data_uri(self, clinic: Tenant | None) -> str | None:
        logo_bytes = self._load_clinic_logo_bytes(clinic)
        if logo_bytes is None or clinic is None or not clinic.logo_object_path:
            return None
        mime_type = self._mime_type_for_logo(clinic.logo_object_path)
        if mime_type is None:
            return None
        encoded_logo = base64.b64encode(logo_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded_logo}"

    def _mime_type_for_logo(self, object_path: str) -> str | None:
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(Path(object_path).suffix.lower())

    def _load_clinic_logo_bytes(self, clinic: Tenant | None) -> bytes | None:
        if (
            clinic is None
            or self.storage_service is None
            or not clinic.logo_object_path
        ):
            return None
        if Path(clinic.logo_object_path).suffix.lower() not in SUPPORTED_CLINIC_LOGO_EXTENSIONS:
            logger.warning(
                "Unsupported clinic logo format; continuing without it. tenant_id=%s",
                clinic.id,
            )
            return None
        bucket_name = self._clinic_logo_bucket_name(clinic)
        if not bucket_name:
            return None
        try:
            logo_bytes = self.storage_service.download_object_bytes(
                bucket_name=bucket_name,
                object_path=clinic.logo_object_path,
            )
        except Exception:
            logger.warning(
                "Clinic logo could not be loaded; continuing without it. tenant_id=%s",
                clinic.id,
            )
            return None
        if not logo_bytes or len(logo_bytes) > MAX_CLINIC_LOGO_SIZE_BYTES:
            logger.warning(
                "Clinic logo is empty or too large; continuing without it. tenant_id=%s",
                clinic.id,
            )
            return None
        return logo_bytes

    def _clinic_logo_bucket_name(self, clinic: Tenant) -> str | None:
        parsed_logo_url = urlparse(clinic.logo_url or "")
        if parsed_logo_url.scheme == "gs" and parsed_logo_url.netloc:
            return parsed_logo_url.netloc
        if self.storage_service is None:
            return None
        return self.storage_service.bucket_name

    def _field(self, label: str, value: object | None) -> dict:
        return {"label": label, "value": value}

    def _non_empty_fields(self, fields: list[dict]) -> list[dict]:
        return [
            {"label": field["label"], "value": str(field["value"])}
            for field in fields
            if field["value"] is not None and str(field["value"]).strip()
        ]

    def _status_badge_class(self, status: str) -> str:
        normalized = (status or "").lower()
        if normalized in {"completed", "completada", "performed", "result_loaded"}:
            return "success"
        if normalized in {"draft", "borrador", "requested"}:
            return "warning"
        return "neutral"

    def _format_duration_or_age(self, patient: Patient) -> str:
        if patient.estimated_age:
            return patient.estimated_age
        if patient.birth_date is None:
            return "No indicado"
        today = datetime.now(timezone.utc).date()
        years = today.year - patient.birth_date.year - (
            (today.month, today.day) < (patient.birth_date.month, patient.birth_date.day)
        )
        return f"{years} año{'s' if years != 1 else ''}"

    def build_text_lines(
        self,
        *,
        clinic: Tenant | None = None,
        patient: Patient,
        owner: Owner | None,
        consultations: list[Consultation],
        exams: list[Exam],
        preventive_care: list[PatientPreventiveCare],
        file_references: list[PatientFileReference],
        options: ClinicalHistoryPdfExportRequest,
    ) -> list[str]:
        lines = ["Historia clínica veterinaria"]
        if clinic is not None:
            lines.append(f"Clínica: {clinic.display_name or clinic.name}")
            self._append_optional(lines, "Teléfono de la clínica", clinic.phone)
            self._append_optional(lines, "Correo de la clínica", clinic.email)
            self._append_optional(lines, "Dirección de la clínica", clinic.address)
        lines.extend(
            [
                f"Paciente: {patient.name}",
                f"Generado: {self._format_datetime(datetime.now(timezone.utc))}",
            ]
        )
        if self._format_date_range(options):
            lines.append(f"Rango: {self._format_date_range(options)}")
        lines.append(
            "Nivel de detalle: "
            + ("Resumen" if options.detail_level == "summary" else "Historia completa")
        )
        if options.include_patient_data:
            lines.extend(
                [
                    "",
                    "Datos del paciente",
                    f"Nombre: {patient.name}",
                    f"Especie: {patient.species}",
                    f"Raza: {self._value(patient.breed)}",
                    f"Sexo: {self._value(patient.sex)}",
                    f"Edad estimada: {self._format_duration_or_age(patient)}",
                    f"Peso: {self._format_weight(patient.weight_kg)}",
                    f"Alergias: {self._value(patient.allergies, 'Sin registros')}",
                    "Condiciones crónicas: "
                    + self._value(patient.chronic_conditions, "Sin registros"),
                ]
            )
        if options.include_owner_data and owner is not None:
            lines.extend(
                [
                    "",
                    "Datos del propietario",
                    f"Nombre: {owner.full_name}",
                    f"Teléfono: {owner.phone}",
                    f"Correo: {self._value(owner.email)}",
                    f"Dirección: {self._value(owner.address)}",
                ]
            )
        if options.include_consultations:
            lines.extend(["", "Consultas"])
            if not consultations:
                lines.append("Sin consultas en el rango seleccionado.")
            for consultation in consultations:
                self._append_consultation(lines, consultation, options)
        if options.include_exams:
            lines.extend(["", "Exámenes"])
            if not exams:
                lines.append("Sin exámenes en el rango seleccionado.")
            for exam in exams:
                self._append_exam(lines, exam)
        if options.include_preventive_care:
            lines.extend(["", "Vacunas y desparasitación"])
            if not preventive_care:
                lines.append("Sin registros preventivos en el rango seleccionado.")
            for record in preventive_care:
                self._append_preventive_care(lines, record)
        if options.include_file_references:
            lines.extend(["", "Archivos adjuntos"])
            if not file_references:
                lines.append("Sin archivos en el rango seleccionado.")
            for file_reference in file_references:
                self._append_file_reference(lines, file_reference)
        return lines

    def _append_consultation(
        self,
        lines: list[str],
        consultation: Consultation,
        options: ClinicalHistoryPdfExportRequest,
    ) -> None:
        lines.extend(
            [
                "",
                f"Consulta - {self._format_datetime(consultation.visit_date)}",
                f"Motivo: {consultation.reason}",
                f"Estado: {self._status_label(consultation.status)}",
            ]
        )
        attended_by = self._user_label(
            consultation.attending_user_name, consultation.attending_user_email
        )
        created_by = self._user_label(
            consultation.created_by_user_name, consultation.created_by_user_email
        )
        if attended_by:
            lines.append(f"Atendido por: {attended_by}")
        if options.detail_level == "full" and created_by and created_by != attended_by:
            lines.append(f"Registrado por: {created_by}")
        self._append_optional(
            lines, "Diagnóstico presuntivo", consultation.presumptive_diagnosis
        )
        self._append_optional(lines, "Diagnóstico final", consultation.final_diagnosis)
        self._append_optional(lines, "Indicaciones", consultation.indications)
        self._append_optional(lines, "Resumen", consultation.consultation_summary)
        if options.include_consultation_exam_data:
            exam_data = self._build_consultation_exam_data(
                consultation,
                detail_level=options.detail_level,
            )
            if exam_data["has_data"]:
                lines.append("Signos vitales y examen físico")
                for vital in exam_data["vitals"]:
                    lines.append(f"{vital['label']}: {vital['value']}")
                if exam_data["physical_exam_findings"]:
                    lines.append(
                        "Hallazgos del examen físico: "
                        + exam_data["physical_exam_findings"]
                    )
        if options.detail_level == "summary":
            return
        for field in self._non_empty_fields(
            [
                self._field("Anamnesis", consultation.anamnesis),
                self._field("Síntomas", consultation.symptoms),
                self._field("Duración de síntomas", consultation.symptom_duration),
                self._field("Antecedentes relevantes", consultation.relevant_history),
                self._field("Hábitos y dieta", consultation.habits_and_diet),
                self._field("Examen clínico", consultation.clinical_exam),
                self._field("Plan diagnóstico", consultation.diagnostic_plan),
                self._field("Notas del plan diagnóstico", consultation.diagnostic_plan_notes),
                self._field("Resultados del plan diagnóstico", consultation.diagnostic_results),
                self._field("Plan terapéutico", consultation.therapeutic_plan),
                self._field("Notas del plan terapéutico", consultation.therapeutic_plan_notes),
            ]
        ):
            lines.append(f"{field['label']}: {field['value']}")
        if consultation.medications:
            lines.append("Medicamentos:")
            for medication in consultation.medications:
                details = " · ".join(
                    value
                    for value in [
                        medication.medication_name,
                        medication.dose_or_quantity,
                        medication.instructions,
                    ]
                    if value
                )
                lines.append(f"- {details}")
        if consultation.study_requests:
            lines.append("Solicitudes de estudio:")
            for request in consultation.study_requests:
                details = " · ".join(
                    value
                    for value in [
                        request.name,
                        self._study_request_type_label(request.study_type),
                        request.notes,
                    ]
                    if value
                )
                lines.append(f"- {details}")

    def _append_exam(self, lines: list[str], exam: Exam) -> None:
        lines.extend(
            [
                "",
                f"Examen - {exam.exam_type}",
                f"Estado: {self._exam_status_label(exam.status)}",
                f"Solicitado: {self._format_datetime(exam.requested_at)}",
                f"Realizado: {self._format_datetime(exam.performed_at)}",
            ]
        )
        requested_by = self._user_label(
            exam.requested_by_user_name, exam.requested_by_user_email
        )
        if requested_by:
            lines.append(f"Solicitado por: {requested_by}")
        self._append_optional(lines, "Resumen de resultado", exam.result_summary)
        self._append_optional(lines, "Observaciones", exam.observations)

    def _append_preventive_care(
        self, lines: list[str], record: PatientPreventiveCare
    ) -> None:
        lines.extend(
            [
                "",
                f"{self._preventive_care_type_label(record.care_type)} - {record.name}",
                f"Aplicado: {self._format_datetime(record.applied_at)}",
                f"Próxima dosis: {self._format_datetime(record.next_due_at)}",
                f"Lote: {self._value(record.lot_number)}",
            ]
        )
        registered_by = self._user_label(
            record.created_by_user_name, record.created_by_user_email
        )
        if registered_by:
            lines.append(f"Registrado por: {registered_by}")
        self._append_optional(lines, "Notas", record.notes)

    def _append_file_reference(
        self, lines: list[str], file_reference: PatientFileReference
    ) -> None:
        lines.extend(
            [
                "",
                f"Archivo - {file_reference.name}",
                f"Tipo: {self._file_type_label(file_reference.file_type)}",
                f"Archivo original: {self._value(file_reference.original_filename)}",
                "Subido: "
                + self._format_datetime(
                    file_reference.uploaded_at or file_reference.created_at
                ),
            ]
        )
        registered_by = self._user_label(
            file_reference.created_by_user_name,
            file_reference.created_by_user_email,
        )
        if registered_by:
            lines.append(f"Registrado por: {registered_by}")

    def _get_owner_for_patient(
        self, tenant_id: uuid.UUID, patient: Patient
    ) -> Owner | None:
        return self.owner_repository.get_by_id(tenant_id, patient.owner_id)

    def _filter_by_date(self, records: Iterable, options, date_getter) -> list:
        filtered = []
        for record in records:
            event_date = date_getter(record)
            if event_date is None:
                continue
            event_day = event_date.date()
            if options.date_from and event_day < options.date_from:
                continue
            if options.date_to and event_day > options.date_to:
                continue
            filtered.append(record)
        return filtered

    def _validate_date_range(self, options: ClinicalHistoryPdfExportRequest) -> None:
        if options.date_from and options.date_to and options.date_from > options.date_to:
            raise AppError(
                422,
                "invalid_date_range",
                "date_from must be before or equal to date_to",
            )

    def _format_date_range(self, options: ClinicalHistoryPdfExportRequest) -> str | None:
        if not options.date_from and not options.date_to:
            return None
        date_from = options.date_from.isoformat() if options.date_from else "inicio"
        date_to = options.date_to.isoformat() if options.date_to else "hoy"
        return f"{date_from} a {date_to}"

    def _build_filename(self, patient_name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", patient_name.lower()).strip("-")
        generated_date = datetime.now(timezone.utc).date().isoformat()
        return f"historia-clinica-{slug or 'paciente'}-{generated_date}.pdf"

    def _consultation_event_date(self, consultation: Consultation) -> datetime:
        return consultation.visit_date

    def _exam_event_date(self, exam: Exam) -> datetime:
        return exam.performed_at or exam.requested_at

    def _preventive_care_event_date(self, record: PatientPreventiveCare) -> datetime:
        return record.applied_at

    def _file_reference_event_date(
        self, file_reference: PatientFileReference
    ) -> datetime:
        return file_reference.uploaded_at or file_reference.created_at

    def _append_optional(
        self, lines: list[str], label: str, value: object | None
    ) -> None:
        if value is not None and value != "":
            lines.append(f"{label}: {value}")

    def _value(self, value: object | None, fallback: str = "No indicado") -> str:
        if value is None or value == "":
            return fallback
        return str(value)

    def _format_weight(self, value: object | None) -> str:
        return "No indicado" if value is None else f"{value} kg"

    def _build_consultation_exam_data(
        self,
        consultation: Consultation,
        *,
        detail_level: str,
    ) -> dict:
        vital_fields = [
            self._field(
                "Temperatura",
                self._format_temperature(consultation.temperature_c),
            ),
            self._field(
                "Peso actual",
                self._format_current_weight(consultation.current_weight_kg),
            ),
            self._field(
                "Frecuencia cardíaca",
                self._format_rate(consultation.heart_rate, "lpm"),
            ),
            self._field(
                "Frecuencia respiratoria",
                self._format_rate(consultation.respiratory_rate, "rpm"),
            ),
        ]
        if detail_level == "full":
            vital_fields.extend(
                [
                    self._field("Mucosas", consultation.mucous_membranes),
                    self._field("Hidratación", consultation.hydration),
                ]
            )

        vitals = self._non_empty_fields(vital_fields)
        physical_exam_findings = (
            consultation.physical_exam_findings.strip()
            if detail_level == "full"
            and consultation.physical_exam_findings
            and consultation.physical_exam_findings.strip()
            else None
        )
        return {
            "has_data": bool(vitals or physical_exam_findings),
            "vitals": vitals,
            "physical_exam_findings": physical_exam_findings,
        }

    def _format_temperature(self, value: float | None) -> str | None:
        if value is None:
            return None
        return f"{self._format_decimal_number(value)} °C"

    def _format_current_weight(self, value: float | None) -> str | None:
        if value is None:
            return None
        return f"{self._format_decimal_number(value)} kg"

    def _format_rate(self, value: int | None, unit: str) -> str | None:
        if value is None:
            return None
        return f"{value} {unit}"

    def _format_decimal_number(self, value: float) -> str:
        formatted = f"{value:.2f}".rstrip("0").rstrip(".")
        return formatted.replace(".", ",")

    def _format_datetime(self, value: datetime | None) -> str:
        return "No indicado" if value is None else value.strftime("%Y-%m-%d %H:%M")

    def _user_label(self, full_name: str | None, email: str | None) -> str | None:
        return full_name or email

    def _status_label(self, status: str) -> str:
        return {"draft": "Borrador", "completed": "Completada"}.get(status, status)

    def _exam_status_label(self, status: str) -> str:
        return {
            "requested": "Solicitado",
            "performed": "Realizado",
            "result_loaded": "Resultado cargado",
        }.get(status, status)

    def _preventive_care_type_label(self, care_type: str) -> str:
        return {
            "vaccine": "Vacuna",
            "deworming": "Desparasitación",
            "other": "Otro",
        }.get(care_type, care_type)

    def _file_type_label(self, file_type: str) -> str:
        return {
            "laboratory": "Laboratorio",
            "radiography": "Radiografía",
            "ultrasound": "Ecografía",
            "clinical_photo": "Foto clínica",
            "document": "PDF / Documento",
            "other": "Otro",
        }.get(file_type, file_type)

    def _study_request_type_label(self, study_type: str) -> str:
        return {
            "laboratory": "Laboratorio",
            "exam": "Examen",
            "other": "Otro",
        }.get(study_type, study_type)
