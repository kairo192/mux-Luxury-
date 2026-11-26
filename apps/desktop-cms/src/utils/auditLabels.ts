// Audit-log names (actions and item types) in the language of the CMS, by code
// (i18n areas "audit_action" / "audit_entity"); the server's French name, or
// the code itself, when the CMS does not know the code yet.
import { DICTS, tr } from "../i18n/translations";

export const auditActionLabel = (code: string, fallback?: string) =>
  DICTS.fr[`audit_action.${code}`] ? tr(`audit_action.${code}`) : fallback || code;

export const auditEntityLabel = (code: string, fallback?: string) =>
  DICTS.fr[`audit_entity.${code}`] ? tr(`audit_entity.${code}`) : fallback || code;
