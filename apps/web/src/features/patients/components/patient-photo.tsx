"use client";

import { Cat, Dog, PawPrint } from "lucide-react";
import { ChangeEvent, ReactNode, useEffect, useId, useState } from "react";

import type { Patient } from "@/types/api";

const allowedPatientPhotoExtensions = [".jpg", ".jpeg", ".png", ".webp"];
const allowedPatientPhotoTypes = ["image/jpeg", "image/png", "image/webp"];
const maxPatientPhotoSizeBytes = 5 * 1024 * 1024;

type PatientAvatarProps = {
  patient?: Pick<Patient, "name" | "photo_url" | "sex" | "species"> | null;
  photoUrl?: string | null;
  name?: string | null;
  sex?: string | null;
  species?: string | null;
  size?: "default" | "large";
};

type PatientPhotoInputProps = {
  currentPhotoUrl?: string | null;
  disabled?: boolean;
  errorMessage?: string | null;
  name?: string;
  onChange: (file: File | null) => void;
  onError: (message: string | null) => void;
  onMarkDelete?: () => void;
  onRestore?: () => void;
  previewUrl?: string | null;
  selectedFile: File | null;
  shouldDelete?: boolean;
  species?: string;
};

export function PatientAvatar({
  patient,
  photoUrl,
  name,
  sex,
  species,
  size = "default",
}: PatientAvatarProps) {
  const resolvedPhotoUrl = photoUrl ?? patient?.photo_url ?? null;
  const resolvedName = name ?? patient?.name ?? null;
  const resolvedSex = sex ?? patient?.sex ?? null;
  const resolvedSpecies = species ?? patient?.species ?? "";
  const [hasImageError, setHasImageError] = useState(false);

  useEffect(() => {
    setHasImageError(false);
  }, [resolvedPhotoUrl]);

  if (resolvedPhotoUrl && !hasImageError) {
    return (
      <span
        className={`pet-avatar pet-avatar--photo${size === "large" ? " pet-avatar--large" : ""}`}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          alt={resolvedName ? `Foto de ${resolvedName}` : "Foto del paciente"}
          src={resolvedPhotoUrl}
          onError={() => setHasImageError(true)}
        />
      </span>
    );
  }

  return (
    <span
      aria-hidden="true"
      className={`pet-avatar ${size === "large" ? "pet-avatar--large " : ""}${getSexAvatarClass(resolvedSex)}`}
    >
      {getSpeciesIcon(resolvedSpecies, size === "large" ? 22 : 20)}
    </span>
  );
}

export function PatientPhotoInput({
  currentPhotoUrl,
  disabled = false,
  errorMessage,
  name,
  onChange,
  onError,
  onMarkDelete,
  onRestore,
  previewUrl,
  selectedFile,
  shouldDelete = false,
  species = "",
}: PatientPhotoInputProps) {
  const inputId = useId();
  const visiblePhotoUrl = previewUrl ?? (shouldDelete ? null : currentPhotoUrl ?? null);
  const hasCurrentPhoto = Boolean(currentPhotoUrl && !shouldDelete);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;

    if (!file) {
      return;
    }

    const validationError = getPatientPhotoValidationError(file);
    if (validationError) {
      onError(validationError);
      event.target.value = "";
      return;
    }

    onError(null);
    onChange(file);
    event.target.value = "";
  }

  return (
    <section className="patient-photo-field" aria-label="Foto del paciente">
      <PatientAvatar
        photoUrl={visiblePhotoUrl}
        name={name}
        species={species}
        size="large"
      />

      <div className="patient-photo-field__body">
        <div>
          <strong>Foto del paciente</strong>
          <span>Tomar foto o seleccionar imagen. PNG, JPG o WEBP. Máximo 5 MB.</span>
        </div>

        {selectedFile ? (
          <p className="patient-photo-field__file">
            {selectedFile.name} · {formatPatientPhotoSize(selectedFile.size)}
          </p>
        ) : null}
        {shouldDelete && !selectedFile ? (
          <p className="patient-photo-field__file">La foto actual se eliminará al guardar.</p>
        ) : null}
        {errorMessage ? <p className="field-error">{errorMessage}</p> : null}

        <div className="patient-photo-field__actions">
          <label
            className={`secondary-button patient-photo-field__button${disabled ? " patient-photo-field__button--disabled" : ""}`}
            htmlFor={inputId}
          >
            {visiblePhotoUrl ? "Cambiar foto" : "Agregar foto"}
          </label>
          <input
            accept="image/*"
            capture="environment"
            disabled={disabled}
            id={inputId}
            type="file"
            onChange={handleFileChange}
          />

          {selectedFile ? (
            <button
              className="secondary-button"
              disabled={disabled}
              type="button"
              onClick={() => {
                onChange(null);
                onError(null);
              }}
            >
              Quitar
            </button>
          ) : null}

          {!selectedFile && hasCurrentPhoto && onMarkDelete ? (
            <button
              className="secondary-button secondary-button--danger"
              disabled={disabled}
              type="button"
              onClick={onMarkDelete}
            >
              Eliminar foto
            </button>
          ) : null}

          {!selectedFile && shouldDelete && onRestore ? (
            <button
              className="secondary-button"
              disabled={disabled}
              type="button"
              onClick={onRestore}
            >
              Conservar foto
            </button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

export function getPatientPhotoValidationError(file: File) {
  const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  const hasValidExtension = allowedPatientPhotoExtensions.includes(extension);
  const hasValidType = allowedPatientPhotoTypes.includes(file.type);

  if (!hasValidExtension || !hasValidType) {
    return "Formato no permitido. Usa PNG, JPG o WEBP.";
  }

  if (file.size > maxPatientPhotoSizeBytes) {
    return "La imagen no puede superar 5 MB.";
  }

  return null;
}

export function getPatientPhotoUploadErrorMessage() {
  return "No fue posible subir la foto del paciente.";
}

export function getPatientPhotoDeleteErrorMessage() {
  return "No fue posible eliminar la foto del paciente.";
}

function getSpeciesIcon(species: string, size = 24): ReactNode {
  const normalized = species.trim().toLowerCase();
  if (["canino", "perro", "dog", "canine"].some((word) => normalized.includes(word))) {
    return <Dog size={size} />;
  }
  if (["felino", "gato", "cat", "feline"].some((word) => normalized.includes(word))) {
    return <Cat size={size} />;
  }
  return <PawPrint size={size} />;
}

function getSexAvatarClass(sex: string | null) {
  const normalized = sex?.trim().toLowerCase() ?? "";
  if (["macho", "masculino", "male"].includes(normalized)) {
    return "pet-avatar--male";
  }
  if (["hembra", "femenino", "female"].includes(normalized)) {
    return "pet-avatar--female";
  }
  return "pet-avatar--neutral";
}

function formatPatientPhotoSize(sizeBytes: number) {
  if (sizeBytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(sizeBytes / 1024))} KB`;
  }

  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}
