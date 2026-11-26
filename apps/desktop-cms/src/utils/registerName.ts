import { tr, translateRaw } from "../i18n/translations";

/** The default register name is saved in the language used when the register was opened:
 *  show it in the language in use. A name the shop chose itself stays as it is. */
export function registerName(name: string | null | undefined): string {
  const n = String(name || "").trim();
  if ((["fr", "en", "ar"] as const).some((l) => translateRaw(l, "posx.main_register") === n)) return tr("posx.main_register");
  return n;
}
