// Order statuses as the server stores them, with the names staff read
// (i18n area "order_status").
import { tr } from "../i18n/translations";

export const ORDER_STATUSES = [
  "new", "pending_confirmation", "confirmed", "preparing", "ready_for_shipment",
  "shipped", "delivered", "cancelled", "returned",
] as const;

export const orderStatusLabel = (s: string) => ((ORDER_STATUSES as readonly string[]).includes(s) ? tr(`order_status.${s}`) : s);

/** Same rule as the server: cancelled / returned are final, a delivered
 *  order can only become "returned" (customer return). */
export function allowedOrderStatuses(current: string): string[] {
  if (current === "cancelled" || current === "returned") return [current];
  if (current === "delivered") return ["delivered", "returned"];
  return [...ORDER_STATUSES];
}
