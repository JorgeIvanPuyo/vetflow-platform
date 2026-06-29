from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from sqlalchemy.orm import Session

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
MAX_CLINIC_LOGO_SIZE_BYTES = 5 * 1024 * 1024


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
            filtered_consultations = self._filter_by_date(
                consultations,
                options,
                self._consultation_event_date,
            )
            filtered_exams = self._filter_by_date(
                exams,
                options,
                self._exam_event_date,
            )
            filtered_preventive_care = self._filter_by_date(
                preventive_care,
                options,
                self._preventive_care_event_date,
            )
            filtered_file_references = self._filter_by_date(
                file_references,
                options,
                self._file_reference_event_date,
            )
            text_lines = self.build_text_lines(
                clinic=clinic,
                patient=patient,
                owner=owner,
                consultations=filtered_consultations,
                exams=filtered_exams,
                preventive_care=filtered_preventive_care,
                file_references=filtered_file_references,
                options=options,
            )
            pdf_bytes = self._render_pdf(
                text_lines,
                options=options,
                clinic=clinic,
            )
            filename = self._build_filename(patient.name)
            return ClinicalHistoryPdfExport(
                pdf_bytes=pdf_bytes,
                filename=filename,
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
        lines: list[str] = [
            "Historia clínica veterinaria",
        ]
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

        date_range = self._format_date_range(options)
        if date_range:
            lines.append(f"Rango: {date_range}")
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
                    f"Edad estimada: {self._value(patient.estimated_age)}",
                    f"Peso: {self._format_weight(patient.weight_kg)}",
                    f"Alergias: {self._value(patient.allergies, 'Sin registros')}",
                    (
                        "Condiciones crónicas: "
                        f"{self._value(patient.chronic_conditions, 'Sin registros')}"
                    ),
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
                self._append_consultation(lines, consultation, options.detail_level)

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
        detail_level: str,
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
            consultation.attending_user_name,
            consultation.attending_user_email,
        )
        created_by = self._user_label(
            consultation.created_by_user_name,
            consultation.created_by_user_email,
        )
        if attended_by:
            lines.append(f"Atendido por: {attended_by}")
        if created_by and created_by != attended_by:
            lines.append(f"Registrado por: {created_by}")

        if detail_level == "summary":
            self._append_optional(lines, "Diagnóstico presuntivo", consultation.presumptive_diagnosis)
            self._append_optional(lines, "Diagnóstico final", consultation.final_diagnosis)
            self._append_optional(lines, "Indicaciones", consultation.indications)
            self._append_optional(lines, "Resumen", consultation.consultation_summary)
            return

        self._append_optional(lines, "Anamnesis", consultation.anamnesis)
        self._append_optional(lines, "Síntomas", consultation.symptoms)
        self._append_optional(lines, "Duración de síntomas", consultation.symptom_duration)
        self._append_optional(lines, "Antecedentes relevantes", consultation.relevant_history)
        self._append_optional(lines, "Hábitos y dieta", consultation.habits_and_diet)
        self._append_optional(lines, "Examen clínico", consultation.clinical_exam)
        self._append_optional(lines, "Hallazgos físicos", consultation.physical_exam_findings)
        self._append_optional(lines, "Plan diagnóstico", consultation.diagnostic_plan)
        self._append_optional(lines, "Notas del plan diagnóstico", consultation.diagnostic_plan_notes)
        self._append_optional(
            lines,
            "Resultados del plan diagnóstico",
            consultation.diagnostic_results,
        )
        self._append_optional(lines, "Plan terapéutico", consultation.therapeutic_plan)
        self._append_optional(lines, "Notas del plan terapéutico", consultation.therapeutic_plan_notes)
        self._append_optional(lines, "Diagnóstico final", consultation.final_diagnosis)
        self._append_optional(lines, "Indicaciones", consultation.indications)
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
            for study_request in consultation.study_requests:
                details = " · ".join(
                    value
                    for value in [
                        study_request.name,
                        self._study_request_type_label(study_request.study_type),
                        study_request.notes,
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
            exam.requested_by_user_name,
            exam.requested_by_user_email,
        )
        if requested_by:
            lines.append(f"Solicitado por: {requested_by}")
        self._append_optional(lines, "Resumen de resultado", exam.result_summary)
        self._append_optional(lines, "Observaciones", exam.observations)

    def _append_preventive_care(
        self,
        lines: list[str],
        record: PatientPreventiveCare,
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
            record.created_by_user_name,
            record.created_by_user_email,
        )
        if registered_by:
            lines.append(f"Registrado por: {registered_by}")
        self._append_optional(lines, "Notas", record.notes)

    def _append_file_reference(
        self,
        lines: list[str],
        file_reference: PatientFileReference,
    ) -> None:
        lines.extend(
            [
                "",
                f"Archivo - {file_reference.name}",
                f"Tipo: {self._file_type_label(file_reference.file_type)}",
                f"Archivo original: {self._value(file_reference.original_filename)}",
                f"Subido: {self._format_datetime(file_reference.uploaded_at)}",
            ]
        )
        registered_by = self._user_label(
            file_reference.created_by_user_name,
            file_reference.created_by_user_email,
        )
        if registered_by:
            lines.append(f"Registrado por: {registered_by}")

    def _render_pdf(
        self,
        text_lines: list[str],
        *,
        options: ClinicalHistoryPdfExportRequest,
        clinic: Tenant | None,
    ) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from reportlab.platypus import (
            HRFlowable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        buffer = BytesIO()
        page_size = self._page_size_for(options.page_size)
        document = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            rightMargin=42,
            leftMargin=42,
            topMargin=54,
            bottomMargin=48,
            title="Historia clínica veterinaria",
        )
        styles = getSampleStyleSheet()
        teal = colors.HexColor("#245B4F")
        teal_light = colors.HexColor("#EAF4F1")
        text_color = colors.HexColor("#27332F")
        muted = colors.HexColor("#66736E")

        title_style = ParagraphStyle(
            "ClinicalHistoryTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=teal,
            spaceAfter=5,
        )
        clinic_style = ParagraphStyle(
            "ClinicalHistoryClinic",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=text_color,
        )
        metadata_style = ParagraphStyle(
            "ClinicalHistoryMetadata",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=11,
            textColor=muted,
        )
        section_style = ParagraphStyle(
            "ClinicalHistorySection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=teal,
            backColor=teal_light,
            borderPadding=(5, 7, 5, 7),
            spaceBefore=8,
            spaceAfter=6,
        )
        record_style = ParagraphStyle(
            "ClinicalHistoryRecord",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=teal,
            spaceBefore=5,
            spaceAfter=3,
        )
        body_style = ParagraphStyle(
            "ClinicalHistoryBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=12,
            textColor=text_color,
            spaceAfter=2,
        )
        bullet_style = ParagraphStyle(
            "ClinicalHistoryBullet",
            parent=body_style,
            leftIndent=12,
            firstLineIndent=-7,
        )

        clinic_name = (clinic.display_name or clinic.name) if clinic is not None else None
        logo = self._build_logo_flowable(clinic)
        header_end = next(
            (index for index, line in enumerate(text_lines) if not line),
            len(text_lines),
        )
        header_story = []
        for index, line in enumerate(text_lines[:header_end]):
            if index == 0:
                header_story.append(Paragraph(escape(line), title_style))
                continue
            if line.startswith("Clínica:"):
                header_story.append(Paragraph(self._format_pdf_line(line), clinic_style))
                continue
            if line.startswith(
                (
                    "Teléfono de la clínica:",
                    "Correo de la clínica:",
                    "Dirección de la clínica:",
                    "Generado:",
                    "Rango:",
                    "Nivel de detalle:",
                )
            ):
                header_story.append(
                    Paragraph(self._format_pdf_line(line), metadata_style)
                )
                continue
            header_story.append(Paragraph(self._format_pdf_line(line), body_style))

        story = []
        if logo is not None:
            logo_column_width = 78
            story.append(
                Table(
                    [[logo, header_story]],
                    colWidths=[logo_column_width, document.width - logo_column_width],
                    style=TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (0, 0), 10),
                            ("RIGHTPADDING", (1, 0), (1, 0), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 0),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                        ]
                    ),
                )
            )
        else:
            story.extend(header_story)
        story.append(Spacer(1, 5))
        story.append(HRFlowable(width="100%", thickness=1, color=teal))
        story.append(Spacer(1, 7))

        for line in text_lines[header_end + 1 :]:
            if not line:
                story.append(Spacer(1, 4))
                continue
            if self._is_section_heading(line):
                story.append(Paragraph(escape(line), section_style))
                continue
            if self._is_record_heading(line):
                story.append(Paragraph(escape(line), record_style))
                continue
            if line.startswith("Clínica:"):
                story.append(Paragraph(self._format_pdf_line(line), clinic_style))
                continue
            if line.startswith(
                (
                    "Teléfono de la clínica:",
                    "Correo de la clínica:",
                    "Dirección de la clínica:",
                    "Generado:",
                    "Rango:",
                    "Nivel de detalle:",
                )
            ):
                story.append(Paragraph(self._format_pdf_line(line), metadata_style))
                continue
            if line.startswith("- "):
                story.append(
                    Paragraph(
                        f"• {escape(line[2:])}",
                        bullet_style,
                    )
                )
                continue
            story.append(Paragraph(self._format_pdf_line(line), body_style))

        def draw_footer(canvas, doc) -> None:
            canvas.saveState()
            page_width, _page_height = doc.pagesize
            footer_text = self._footer_text(clinic_name, doc.page)
            font_name = "Helvetica"
            font_size = 7.5
            max_width = page_width - 84
            while (
                stringWidth(footer_text, font_name, font_size) > max_width
                and font_size > 6
            ):
                font_size -= 0.5
            canvas.setStrokeColor(colors.HexColor("#C8D8D3"))
            canvas.setLineWidth(0.5)
            canvas.line(42, 34, page_width - 42, 34)
            canvas.setFillColor(muted)
            canvas.setFont(font_name, font_size)
            canvas.drawCentredString(page_width / 2, 21, footer_text)
            canvas.restoreState()

        document.build(
            story,
            onFirstPage=draw_footer,
            onLaterPages=draw_footer,
        )
        return buffer.getvalue()

    def _build_logo_flowable(self, clinic: Tenant | None):
        logo_bytes = self._load_clinic_logo_bytes(clinic)
        if logo_bytes is None:
            return None

        try:
            from reportlab.platypus import Image

            logo = Image(BytesIO(logo_bytes))
            scale = min(68 / logo.imageWidth, 54 / logo.imageHeight)
            logo.drawWidth = logo.imageWidth * scale
            logo.drawHeight = logo.imageHeight * scale
            return logo
        except Exception:
            logger.warning(
                "Clinic logo could not be rendered; continuing without it. tenant_id=%s",
                clinic.id if clinic is not None else None,
            )
            return None

    def _load_clinic_logo_bytes(self, clinic: Tenant | None) -> bytes | None:
        if (
            clinic is None
            or self.storage_service is None
            or not clinic.logo_object_path
        ):
            return None

        extension = Path(clinic.logo_object_path).suffix.lower()
        if extension not in SUPPORTED_CLINIC_LOGO_EXTENSIONS:
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

    def _page_size_for(self, page_size: str) -> tuple[float, float]:
        from reportlab.lib.pagesizes import A4, legal, letter

        return {
            "letter": letter,
            "a4": A4,
            "legal": legal,
        }[page_size]

    def _format_pdf_line(self, line: str) -> str:
        label, separator, value = line.partition(":")
        if separator:
            return f"<b>{escape(label)}:</b> {escape(value.strip())}"
        return escape(line)

    def _footer_text(self, clinic_name: str | None, page_number: int) -> str:
        prefix = f"VetFlow / {clinic_name}" if clinic_name else "VetFlow"
        return f"{prefix} · Historia clínica veterinaria · Página {page_number}"

    def _is_record_heading(self, line: str) -> bool:
        return " - " in line and ":" not in line

    def _get_owner_for_patient(
        self,
        tenant_id: uuid.UUID,
        patient: Patient,
    ) -> Owner | None:
        owner = self.owner_repository.get_by_id(tenant_id, patient.owner_id)
        if owner is None:
            return None
        return owner

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
        slug = slug or "paciente"
        generated_date = datetime.now(timezone.utc).date().isoformat()
        return f"historia-clinica-{slug}-{generated_date}.pdf"

    def _is_section_heading(self, line: str) -> bool:
        return line in {
            "Datos del paciente",
            "Datos del propietario",
            "Consultas",
            "Exámenes",
            "Vacunas y desparasitación",
            "Archivos adjuntos",
        }

    def _consultation_event_date(self, consultation: Consultation) -> datetime:
        return consultation.visit_date

    def _exam_event_date(self, exam: Exam) -> datetime:
        return exam.performed_at or exam.requested_at

    def _preventive_care_event_date(self, record: PatientPreventiveCare) -> datetime:
        return record.applied_at

    def _file_reference_event_date(self, file_reference: PatientFileReference) -> datetime:
        return file_reference.uploaded_at or file_reference.created_at

    def _append_optional(
        self,
        lines: list[str],
        label: str,
        value: object | None,
    ) -> None:
        if value is None or value == "":
            return
        lines.append(f"{label}: {value}")

    def _value(self, value: object | None, fallback: str = "No indicado") -> str:
        if value is None or value == "":
            return fallback
        return str(value)

    def _format_weight(self, value: object | None) -> str:
        if value is None:
            return "No indicado"
        return f"{value} kg"

    def _format_datetime(self, value: datetime | None) -> str:
        if value is None:
            return "No indicado"
        return value.strftime("%Y-%m-%d %H:%M")

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
