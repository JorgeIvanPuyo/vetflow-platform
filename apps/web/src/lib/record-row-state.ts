import type {
  AppointmentStatus,
  FollowUpStatus,
  InventoryBulkOperationItemStatus,
  InventoryBulkOperationStatus,
  InventoryReversalStatus,
  PurchaseReturnStatus,
  PurchaseStatus,
  SalePayment,
  SaleStatus,
} from "@/types/api";

type RecordStatus =
  | SaleStatus
  | PurchaseStatus
  | PurchaseReturnStatus
  | AppointmentStatus
  | FollowUpStatus
  | InventoryReversalStatus
  | InventoryBulkOperationStatus
  | InventoryBulkOperationItemStatus;

export function isDiscardedStatus(status: RecordStatus | null | undefined): boolean {
  // A compensating inventory movement (`reversal`) remains active. Partial
  // reversals, returns, missed appointments and failures are separate states.
  return status === "cancelled" || status === "reversed" || status === "reverted";
}

export function getRecordRowState(status: RecordStatus | null | undefined): "discarded" | undefined {
  return isDiscardedStatus(status) ? "discarded" : undefined;
}

// Payments expose a boolean rather than a cancellation status in the API.
export function getPaymentRowState(payment: Pick<SalePayment, "is_active">): "discarded" | undefined {
  return payment.is_active === false ? "discarded" : undefined;
}
