import type { ClinicService, SaleItem, SaleServiceItemInput } from "@/types/api";

export type ServiceLine = {
  key: string;
  type: "service";
  serviceId: string | null;
  description: string;
  quantity: string;
  price: string;
  discount: string;
};

export function serviceLineFromCatalog(service: ClinicService, key: string): ServiceLine {
  return {
    key, type: "service", serviceId: service.id, description: service.name,
    quantity: "1", price: service.price ?? "", discount: "0",
  };
}

export function serviceLineFromSnapshot(item: SaleItem): ServiceLine {
  return {
    key: item.id, type: "service", serviceId: item.service_id,
    description: item.description_snapshot, quantity: item.quantity,
    price: item.unit_price_ars, discount: item.discount_percentage,
  };
}

export function serviceLineToInput(line: ServiceLine): SaleServiceItemInput {
  return {
    line_type: "service", service_id: line.serviceId, description: line.description.trim(),
    quantity: line.quantity, unit_price_ars: line.price, discount_percentage: line.discount,
  };
}

export function hasValidServicePrice(price: string): boolean {
  return price.trim() !== "" && Number.isFinite(Number(price)) && Number(price) >= 0;
}

export function filterSaleServices(services: ClinicService[], query: string): ClinicService[] {
  const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim().replace(/\s+/g, " ");
  const search = normalize(query);
  return services.filter((service) => service.is_active && normalize(service.name).includes(search));
}
