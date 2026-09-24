"use client";

import { useEffect, useState } from "react";

import { OwnerSelector } from "@/components/owner-selector";
import { getOwner } from "@/services/owners";
import type { Owner } from "@/types/api";

type Props = {
  disabled?: boolean;
  ownerId: string;
  onSelect: (owner: Owner | null) => void;
};

export function AgendaOwnerSelector({ disabled = false, ownerId, onSelect }: Props) {
  const [selectedOwner, setSelectedOwner] = useState<Owner | null>(null);

  useEffect(() => {
    if (!ownerId || selectedOwner?.id === ownerId) return;
    let cancelled = false;
    getOwner(ownerId).then(({ data }) => {
      if (!cancelled) setSelectedOwner(data);
    }).catch(() => {
      // Keep the saved ID even if its display name cannot be loaded.
    });
    return () => { cancelled = true; };
  }, [ownerId, selectedOwner?.id]);

  return <OwnerSelector
    disabled={disabled}
    idPrefix="agenda-owner"
    emptyLabel="Sin propietario seleccionado"
    ownerId={ownerId}
    ownerName={selectedOwner?.id === ownerId ? selectedOwner.full_name : ""}
    onSelect={(owner) => { setSelectedOwner(owner); onSelect(owner); }}
  />;
}
