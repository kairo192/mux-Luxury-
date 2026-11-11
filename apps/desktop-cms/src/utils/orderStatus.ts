// Order statuses as the server stores them, with the names staff read.
export const ORDER_STATUSES = [
  "new", "pending_confirmation", "confirmed", "preparing", "ready_for_shipment",
  "shipped", "delivered", "cancelled", "returned",
] as const;

export const ORDER_STATUS_LABEL: Record<string, string> = {
  new: "Nouvelle",
  pending_confirmation: "À confirmer (rappeler)",
  confirmed: "Confirmée",
  preparing: "En préparation",
  ready_for_shipment: "Prête à expédier",
  shipped: "Expédiée",
  delivered: "Livrée (encaissée)",
  cancelled: "Annulée",
  returned: "Retournée",
};

export const orderStatusLabel = (s: string) => ORDER_STATUS_LABEL[s] || s;

/** Same rule as the server: cancelled / returned are final, a delivered
 *  order can only become "returned" (customer return). */
export function allowedOrderStatuses(current: string): string[] {
  if (current === "cancelled" || current === "returned") return [current];
  if (current === "delivered") return ["delivered", "returned"];
  return [...ORDER_STATUSES];
}
