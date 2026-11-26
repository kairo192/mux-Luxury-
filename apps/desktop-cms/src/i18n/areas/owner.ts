import { defineArea } from "./define";

export const owner = defineArea("owner", {
  "badge": ["Première ouverture — configuration initiale", "First start — initial setup", "أول تشغيل — الإعداد الأولي"],
  "title": ["Accès propriétaire & direction", "Owner access", "دخول المالك"],
  "sub": ["Configurez vos accès et vos numéros de secours. Après enregistrement sécurisé, vos accès seront verrouillés.", "Set up your access and your contact number. Once saved, this screen is locked.", "اضبط بيانات دخولك ورقم الاتصال. بعد الحفظ تُقفل هذه الشاشة."],
  "name": ["Nom complet", "Full name", "الاسم الكامل"],
  "name_ph": ["Nom et prénom", "First and last name", "الاسم واللقب"],
  "email": ["Email / Identifiant", "Email / Login", "البريد الإلكتروني / اسم الدخول"],
  "password": ["Mot de passe (≥ 10 car.)", "Password (≥ 10 characters)", "كلمة المرور (10 أحرف على الأقل)"],
  "confirm": ["Confirmer mot de passe", "Confirm the password", "تأكيد كلمة المرور"],
  "contact": ["Numéro de contact :", "Contact number:", "رقم الاتصال:"],
  "phone": ["Téléphone propriétaire", "Owner phone", "هاتف المالك"],
  "forgot": ["Mot de passe oublié ? Réinitialisation via la console serveur par l'administrateur système.", "Forgot your password? The system administrator resets it on the server.", "نسيت كلمة المرور؟ يعيد مسؤول النظام تعيينها على الخادم."],
  "submit": ["Enregistrer et sécuriser l'accès administrateur", "Save and secure the owner access", "حفظ وتأمين دخول المالك"],
});
