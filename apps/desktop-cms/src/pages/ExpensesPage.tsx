import React, { useState, useEffect } from "react";
import { DesktopCmsApi } from "../api/adminClient";
import {
  RefreshCw,
  Plus,
  AlertTriangle,
  CheckCircle2,
  Search,
  Trash2,
  X,
  CreditCard,
  Building2,
  Receipt,
} from "lucide-react";

interface ExpenseItem {
  id: number;
  description: string;
  category: string;
  amount_dzd: number;
  expense_date: string;
  payment_method: string;
  beneficiary?: string;
  receipt_ref?: string;
  notes?: string;
  payment_status: string;
  created_at: string;
}

const EXPENSE_CATEGORIES = [
  { value: "loyer", label: "Loyer & Local" },
  { value: "salaires", label: "Salaires & Rémunérations" },
  { value: "electricite_eau", label: "Électricité, Gaz & Eau" },
  { value: "internet_tel", label: "Internet & Télécoms" },
  { value: "packaging", label: "Packaging & Sacs Luxe" },
  { value: "publicite_marketing", label: "Publicité & Sponsoring" },
  { value: "transport_logistique", label: "Transport & Coursiers" },
  { value: "maintenance", label: "Maintenance & Entretien" },
  { value: "abonnements_logiciels", label: "Logiciels & Serveurs" },
  { value: "autre", label: "Autres Charges Diverses" },
];

export const ExpensesPage: React.FC = () => {
  const [expenses, setExpenses] = useState<ExpenseItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [expenseToDelete, setExpenseToDelete] = useState<ExpenseItem | null>(null);
  const [deletingExpense, setDeletingExpense] = useState<boolean>(false);

  // New Expense Form State
  const [formDesc, setFormDesc] = useState<string>("");
  const [formCategory, setFormCategory] = useState<string>("loyer");
  const [formAmount, setFormAmount] = useState<string>("");
  const [formDate, setFormDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [formMethod, setFormMethod] = useState<string>("cash");
  const [formBeneficiary, setFormBeneficiary] = useState<string>("");
  const [formReceiptRef, setFormReceiptRef] = useState<string>("");
  const [formNotes, setFormNotes] = useState<string>("");
  const [formStatus, setFormStatus] = useState<string>("paid");

  const loadExpenses = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await DesktopCmsApi.listExpenses(selectedCategory === "all" ? undefined : selectedCategory);
      setExpenses(Array.isArray(data) ? data : (data as any)?.items || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors du chargement des dépenses");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadExpenses();
  }, [selectedCategory]);

  const handleCreateExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formDesc.trim()) {
      setError("Veuillez saisir une description");
      return;
    }
    const parsedAmount = parseInt(formAmount, 10);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError("Le montant doit être un entier positif en DZD");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await DesktopCmsApi.createExpense({
        description: formDesc.trim(),
        category: formCategory,
        amount_dzd: parsedAmount,
        expense_date: formDate,
        payment_method: formMethod,
        beneficiary: formBeneficiary.trim() || undefined,
        receipt_ref: formReceiptRef.trim() || undefined,
        notes: formNotes.trim() || undefined,
        payment_status: formStatus,
      });

      setSuccess("Dépense enregistrée avec succès. Sortie de trésorerie et écriture comptable générées.");
      setShowAddModal(false);
      // Reset form
      setFormDesc("");
      setFormAmount("");
      setFormBeneficiary("");
      setFormReceiptRef("");
      setFormNotes("");
      loadExpenses();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors de l'enregistrement de la dépense");
    } finally {
      setSaving(false);
    }
  };

  const confirmDeleteExpense = async () => {
    if (!expenseToDelete) return;
    setDeletingExpense(true);
    try {
      await DesktopCmsApi.deleteExpense(expenseToDelete.id);
      setSuccess(`Dépense "${expenseToDelete.description}" supprimée avec succès`);
      setExpenseToDelete(null);
      loadExpenses();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Impossible de supprimer la dépense");
    } finally {
      setDeletingExpense(false);
    }
  };

  // Calculations
  const totalAmountDzd = expenses.reduce((sum, item) => sum + (item.amount_dzd || 0), 0);
  const paidExpensesDzd = expenses
    .filter((e) => e.payment_status === "paid")
    .reduce((sum, item) => sum + (item.amount_dzd || 0), 0);
  const pendingExpensesDzd = totalAmountDzd - paidExpensesDzd;

  const filteredExpenses = expenses.filter((e) => {
    const q = (searchQuery || "").toLowerCase();
    const matchSearch =
      !q ||
      (e.description || "").toLowerCase().includes(q) ||
      (e.beneficiary && e.beneficiary.toLowerCase().includes(q)) ||
      (e.receipt_ref && e.receipt_ref.toLowerCase().includes(q));
    return matchSearch;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#063D2E]/10">
        <div>
          <h2 className="text-2xl font-serif font-bold text-[#063D2E] tracking-tight">
            Gestion des Dépenses & Frais Généraux
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Enregistrement et suivi des charges d'exploitation pour le compte de résultat et la trésorerie.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadExpenses()}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-xl border border-[#063D2E]/20 text-[#063D2E] hover:bg-[#063D2E]/5 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5 text-[#063D2E]" />
            <span>Actualiser</span>
          </button>
          <button
            onClick={() => {
              setError(null);
              setSuccess(null);
              setShowAddModal(true);
            }}
            className="px-4 py-2 text-xs font-semibold rounded-xl bg-[#063D2E] text-[#D4AF62] hover:bg-[#0A5C45] shadow-xs transition-all flex items-center gap-2"
          >
            <Plus className="w-4 h-4 text-[#D4AF62]" />
            <span>Nouvelle Dépense</span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex justify-between items-center">
          <span className="flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
            <span>{error}</span>
          </span>
          <button onClick={() => setError(null)} className="text-red-500 font-bold hover:opacity-75 transition">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {success && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-xl flex justify-between items-center">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0" />
            <span>{success}</span>
          </span>
          <button onClick={() => setSuccess(null)} className="text-emerald-600 font-bold hover:opacity-75 transition">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded-lg border border-[#063D2E]/10 shadow-sm">
          <div className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Total Dépenses</div>
          <div className="text-2xl font-bold text-[#063D2E] mt-1">
            {totalAmountDzd.toLocaleString()} <span className="text-sm font-normal text-[#D4AF62]">DZD</span>
          </div>
          <div className="text-[11px] text-gray-400 mt-1">{expenses.length} dépenses enregistrées</div>
        </div>

        <div className="p-4 bg-white rounded-lg border border-[#063D2E]/10 shadow-sm">
          <div className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Dépenses Réglées</div>
          <div className="text-2xl font-bold text-emerald-600 mt-1">
            {paidExpensesDzd.toLocaleString()} <span className="text-sm font-normal text-emerald-500">DZD</span>
          </div>
          <div className="text-[11px] text-gray-400 mt-1">Débitées de la trésorerie</div>
        </div>

        <div className="p-4 bg-white rounded-lg border border-[#063D2E]/10 shadow-sm">
          <div className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Dépenses En Attente</div>
          <div className="text-2xl font-bold text-amber-600 mt-1">
            {pendingExpensesDzd.toLocaleString()} <span className="text-sm font-normal text-amber-500">DZD</span>
          </div>
          <div className="text-[11px] text-gray-400 mt-1">Engagées non encore décaissées</div>
        </div>

        <div className="p-4 bg-white rounded-lg border border-[#063D2E]/10 shadow-sm">
          <div className="text-xs uppercase tracking-wider text-gray-400 font-semibold">Filtre Catégorie</div>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="w-full mt-2 text-xs border border-gray-200 rounded p-1.5 focus:border-[#063D2E] outline-none"
          >
            <option value="all">Toutes les catégories</option>
            {EXPENSE_CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>
                {cat.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-gray-50 p-3 rounded-xl border border-gray-200">
        <div className="relative w-full sm:w-80">
          <input
            type="text"
            placeholder="Rechercher description, bénéficiaire, reçu..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full text-xs pl-8 pr-3 py-2 border border-gray-300 rounded-xl focus:border-[#063D2E] outline-none"
          />
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-gray-400" />
        </div>
        <div className="text-xs text-gray-500">
          Affichage de <span className="font-semibold text-[#063D2E]">{filteredExpenses.length}</span> dépense(s)
        </div>
      </div>

      {/* Expenses Table */}
      <div className="bg-white rounded-2xl border border-[#063D2E]/10 shadow-xs overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-xs text-gray-400">Chargement des dépenses en cours...</div>
        ) : filteredExpenses.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-400">
            Aucune dépense trouvée pour les critères sélectionnés.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#063D2E]/5 border-b border-[#063D2E]/10 text-gray-600 uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Description</th>
                  <th className="py-3 px-4">Catégorie</th>
                  <th className="py-3 px-4">Bénéficiaire / Pièce</th>
                  <th className="py-3 px-4">Règlement</th>
                  <th className="py-3 px-4 text-right">Montant (DZD)</th>
                  <th className="py-3 px-4 text-center">Statut</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredExpenses.map((exp) => {
                  const catLabel =
                    EXPENSE_CATEGORIES.find((c) => c.value === exp.category)?.label || exp.category;
                  return (
                    <tr key={exp.id} className="hover:bg-gray-50/80 transition-colors">
                      <td className="py-3 px-4 font-mono text-gray-600 whitespace-nowrap">
                        {exp.expense_date}
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-semibold text-gray-800">{exp.description}</div>
                        {exp.notes && <div className="text-[11px] text-gray-400 truncate max-w-xs">{exp.notes}</div>}
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-block px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-100 text-gray-700">
                          {catLabel}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-gray-600">
                        <div>{exp.beneficiary || "—"}</div>
                        {exp.receipt_ref && (
                          <div className="text-[11px] font-mono text-gray-400">Réf: {exp.receipt_ref}</div>
                        )}
                      </td>
                      <td className="py-3 px-4 text-gray-600 capitalize">
                        {exp.payment_method === "cash"
                          ? "Espèces"
                          : exp.payment_method === "bank"
                            ? "Virement"
                            : exp.payment_method === "check"
                              ? "Chèque"
                              : exp.payment_method}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-red-600 whitespace-nowrap">
                        -{Number(exp.amount_dzd || 0).toLocaleString()} DZD
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold ${exp.payment_status === "paid"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-amber-100 text-amber-800"
                            }`}
                        >
                          {exp.payment_status === "paid" ? "Payé" : "En attente"}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          type="button"
                          onClick={() => setExpenseToDelete(exp)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] text-red-600 hover:text-red-800 hover:bg-red-50 rounded-lg border border-red-200 transition-colors font-bold shadow-xs"
                          title="Supprimer la dépense"
                        >
                          <Trash2 className="w-3 h-3 text-red-600" />
                          <span>Supprimer</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal: Add Expense */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg border border-[#063D2E]/20 overflow-hidden">
            <div className="bg-[#063D2E] px-6 py-4 flex items-center justify-between">
              <h3 className="text-sm font-serif font-bold text-[#D4AF62] uppercase tracking-wider">
                Enregistrer une Charge / Dépense
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-[#D4AF62]/70 hover:text-[#D4AF62] text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateExpense} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Description / Libellé de la charge *
                </label>
                <input
                  type="text"
                  required
                  placeholder="ex: Loyer local commercial Sidi Yahia - Mars 2026"
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Catégorie de Dépense *
                  </label>
                  <select
                    value={formCategory}
                    onChange={(e) => setFormCategory(e.target.value)}
                    className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none"
                  >
                    {EXPENSE_CATEGORIES.map((cat) => (
                      <option key={cat.value} value={cat.value}>
                        {cat.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Montant (DZD) *
                  </label>
                  <input
                    type="number"
                    required
                    min="1"
                    placeholder="ex: 85000"
                    value={formAmount}
                    onChange={(e) => setFormAmount(e.target.value)}
                    className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none font-mono font-bold"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Date de la Dépense *
                  </label>
                  <input
                    type="date"
                    required
                    value={formDate}
                    onChange={(e) => setFormDate(e.target.value)}
                    className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Mode de Règlement
                  </label>
                  <select
                    value={formMethod}
                    onChange={(e) => setFormMethod(e.target.value)}
                    className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none"
                  >
                    <option value="cash">Espèces (Caisse boutique)</option>
                    <option value="bank">Virement bancaire</option>
                    <option value="check">Chèque de banque</option>
                    <option value="other">Autre</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    Bénéficiaire / Fournisseur
                  </label>
                  <input
                    type="text"
                    placeholder="ex: Propriétaire, Algérie Télécom..."
                    value={formBeneficiary}
                    onChange={(e) => setFormBeneficiary(e.target.value)}
                    className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-700 mb-1">
                    N° Reçu / Facture
                  </label>
                  <input
                    type="text"
                    placeholder="ex: FACT-2026-039"
                    value={formReceiptRef}
                    onChange={(e) => setFormReceiptRef(e.target.value)}
                    className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Statut de Paiement
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 text-xs text-gray-700">
                    <input
                      type="radio"
                      name="payment_status"
                      value="paid"
                      checked={formStatus === "paid"}
                      onChange={() => setFormStatus("paid")}
                    />
                    Payé immédiatement (Déduit de la caisse/banque)
                  </label>
                  <label className="flex items-center gap-2 text-xs text-gray-700">
                    <input
                      type="radio"
                      name="payment_status"
                      value="pending"
                      checked={formStatus === "pending"}
                      onChange={() => setFormStatus("pending")}
                    />
                    En attente de paiement
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Remarques / Justificatif
                </label>
                <textarea
                  rows={2}
                  placeholder="Notes optionnelles..."
                  value={formNotes}
                  onChange={(e) => setFormNotes(e.target.value)}
                  className="w-full text-xs p-2 border border-gray-300 rounded focus:border-[#063D2E] outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 text-xs font-semibold text-[#D4AF62] bg-[#063D2E] hover:bg-[#0A5C45] rounded shadow transition-all disabled:opacity-50"
                >
                  {saving ? "Enregistrement..." : "Valider la Dépense"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Modal: Delete Expense Confirmation */}
      {expenseToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeInBackdrop">
          <div className="bg-[#F8F6F0] rounded-3xl border border-[#D4AF62]/50 shadow-2xl max-w-md w-full overflow-hidden animate-scaleInModal">
            <div className="bg-gradient-to-r from-[#011C15] via-[#063D2E] to-[#02291F] px-6 py-4 flex items-center justify-between border-b border-[#D4AF62]/30">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl bg-red-500/20 text-red-300">
                  <Trash2 className="w-4 h-4 text-red-300" />
                </div>
                <div>
                  <h3 className="text-base font-serif font-bold text-white tracking-wide">
                    Confirmer la Suppression
                  </h3>
                  <p className="text-[11px] text-[#E8D4A5]/80">Annulation de charge comptable</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setExpenseToDelete(null)}
                className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-[#E8D4A5] flex items-center justify-center transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 space-y-4 text-xs">
              <p className="text-gray-700 leading-relaxed">
                Êtes-vous certain de vouloir supprimer définitivement la dépense suivante ?
              </p>
              <div className="p-3.5 rounded-2xl bg-white border border-[#D4AF62]/40 space-y-1.5">
                <div className="font-bold text-[#063D2E] text-sm">{expenseToDelete.description}</div>
                <div className="flex justify-between text-gray-500">
                  <span>Montant :</span>
                  <span className="font-mono font-bold text-red-700">{Number(expenseToDelete.amount_dzd || 0).toLocaleString()} DA</span>
                </div>
                <div className="flex justify-between text-gray-500">
                  <span>Catégorie :</span>
                  <span>{expenseToDelete.category}</span>
                </div>
              </div>
              <p className="text-[11px] text-amber-800 bg-amber-50 p-2.5 rounded-xl border border-amber-200 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0" />
                <span>Cette action est irréversible et recalculera immédiatement le solde net de trésorerie.</span>
              </p>
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setExpenseToDelete(null)}
                  disabled={deletingExpense}
                  className="px-4 py-2 rounded-xl bg-gray-200 hover:bg-gray-300 text-gray-700 font-bold transition"
                >
                  Annuler
                </button>
                <button
                  type="button"
                  onClick={confirmDeleteExpense}
                  disabled={deletingExpense}
                  className="px-5 py-2 rounded-xl bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white font-bold shadow-md transition disabled:opacity-50"
                >
                  {deletingExpense ? "Suppression..." : "Confirmer la suppression"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

