import type { SaleStatus } from "@/types/api";


export function labelSaleStatus(status: SaleStatus) {
  return {
    draft: "Borrador",
    confirmed: "Confirmada",
    cancelled: "Cancelada",
    reversed: "Revertida",
  }[status];
}
