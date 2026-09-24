"use client";

import { SearchSelector } from "@/components/search-selector";
import { getOwners } from "@/services/owners";
import type { Owner } from "@/types/api";

export type OwnerSelectorProps = {
  disabled?: boolean;
  emptyLabel?: string;
  idPrefix?: string;
  ownerId: string;
  ownerName: string;
  onSelect: (owner: Owner | null) => void;
};

const loadOwners = (options: { search?: string; page: number; pageSize: number }) =>
  getOwners({ ...options, sortBy: "full_name" });

export function OwnerSelector({ disabled = false, ownerId, ownerName, onSelect, emptyLabel = "Venta de mostrador", idPrefix = "sale-owner" }: OwnerSelectorProps) {
  return <SearchSelector key={disabled ? "locked" : "available"} disabled={disabled} selectedId={ownerId} selectedLabel={ownerName} onSelect={onSelect}
    emptyLabel={emptyLabel} idPrefix={idPrefix} label="Propietario" plural="Propietarios"
    loadPage={loadOwners} itemLabel={(owner) => owner.full_name} />;
}
