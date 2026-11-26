import { defineArea } from "./define";

export const users = defineArea("users", {
  "load_failed": ["Chargement impossible", "Could not load", "تعذّر التحميل"],
  "pw_short": ["Le mot de passe doit contenir au moins 10 caractères", "The password must be at least 10 characters long", "يجب أن تتكون كلمة المرور من 10 أحرف على الأقل"],
  "save_refused": ["Enregistrement refusé", "Saving refused", "رُفض الحفظ"],
  "deactivated": ["Compte désactivé", "Account deactivated", "تم تعطيل الحساب"],
  "reactivated": ["Compte réactivé", "Account reactivated", "أُعيد تفعيل الحساب"],
  "action_refused": ["Action refusée", "Action refused", "رُفض الإجراء"],
  "reset_refused": ["Réinitialisation refusée", "Password reset refused", "رُفضت إعادة تعيين كلمة المرور"],
  "subtitle": ["Créez des comptes employés (caissier, gestionnaire…). Les permissions sont appliquées côté serveur.", "Create staff accounts (cashier, manager…). Permissions are enforced by the server.", "أنشئ حسابات الموظفين (أمين صندوق، مسؤول…). يطبّق الخادم الصلاحيات."],
  "last_login": ["Dernière connexion", "Last sign-in", "آخر دخول"],
  "reset_pw": ["Réinitialiser le mot de passe", "Reset the password", "إعادة تعيين كلمة المرور"],
  "deactivate": ["Désactiver", "Deactivate", "تعطيل"],
  "reactivate": ["Réactiver", "Reactivate", "إعادة التفعيل"],
  "roles": ["Rôles & permissions", "Roles & permissions", "الأدوار والصلاحيات"],
  "new_pw_ph": ["Nouveau mot de passe (min. 10)", "New password (min. 10)", "كلمة مرور جديدة (10 على الأقل)"],
});
