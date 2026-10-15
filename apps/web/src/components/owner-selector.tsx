"use client";

import { SearchSelector, type SelectorMessages } from "@/components/search-selector";
import { getOwners } from "@/services/owners";
import type { Owner } from "@/types/api";

export type OwnerSelectorProps = {
  defaultOpen?: boolean;
  disabled?: boolean;
  emptyLabel?: string;
  idPrefix?: string;
  messages?: SelectorMessages;
  ownerId: string;
  ownerName: string;
  onSelect: (owner: Owner | null) => void;
};

const loadOwners = (options: { search?: string; page: number; pageSize: number }) =>
  // Interactive failures belong to the dropdown; route recovery hides the form.
  getOwners({ ...options, sortBy: "full_name" }, { retryTransient: false });

export function OwnerSelector({ defaultOpen = false, disabled = false, ownerId, ownerName, onSelect, emptyLabel = "Venta de mostrador", idPrefix = "sale-owner", messages }: OwnerSelectorProps) {
  return <SearchSelector key={disabled ? "locked" : "available"} defaultOpen={defaultOpen} disabled={disabled} selectedId={ownerId} selectedLabel={ownerName} onSelect={onSelect}
    emptyLabel={emptyLabel} idPrefix={idPrefix} label="Propietario" plural="Propietarios" messages={messages}
    loadPage={loadOwners} itemLabel={(owner) => owner.full_name} />;
}
