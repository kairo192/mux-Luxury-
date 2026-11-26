import { defineArea } from "./define";

export const order_status = defineArea("order_status", {
  "new": ["Nouvelle", "New", "جديدة"],
  "pending_confirmation": ["À confirmer (rappeler)", "To confirm (call back)", "للتأكيد (إعادة الاتصال)"],
  "confirmed": ["Confirmée", "Confirmed", "مؤكدة"],
  "preparing": ["En préparation", "Being prepared", "قيد التحضير"],
  "ready_for_shipment": ["Prête à expédier", "Ready to ship", "جاهزة للشحن"],
  "shipped": ["Expédiée", "Shipped", "مشحونة"],
  "delivered": ["Livrée (encaissée)", "Delivered (paid)", "مُسلّمة (مُحصّلة)"],
  "cancelled": ["Annulée", "Cancelled", "ملغاة"],
  "returned": ["Retournée", "Returned", "مُرجعة"],
});
