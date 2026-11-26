// One photo for a category, banner, etc.: preview, upload from the PC
// (same /admin/upload endpoint as product photos), remove. Stores the URL
// returned by the server — the owner never types a file path.
import React, { useState } from "react";
import { ImagePlus, Loader2, Trash2 } from "lucide-react";
import { DesktopCmsApi, mediaUrl, PLACEHOLDER_IMG } from "../api/adminClient";
import { notifyClientError } from "../utils/clientNotifier";
import { tr } from "../i18n/translations";

export function ImageUploadField({
  label,
  value,
  onChange,
  hint,
  wide = false,
}: {
  label: string;
  value: string;
  onChange: (url: string) => void;
  hint?: string;
  wide?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const inputId = React.useId();

  async function upload(file: File) {
    setBusy(true);
    try {
      const res: any = await DesktopCmsApi.uploadMediaFile(file);
      onChange(res.url);
    } catch (err) {
      notifyClientError(err, tr("misc.photo_failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-1.5">
      <span className="block font-bold text-[#063D2E]">{label}</span>
      <div className="flex items-center gap-3">
        <img
          src={value ? mediaUrl(value) : PLACEHOLDER_IMG}
          alt=""
          className={`${wide ? "w-32 h-16" : "w-16 h-16"} rounded-xl object-cover border border-gray-200 bg-[#F8F6F0]`}
        />
        <div className="flex flex-wrap gap-2">
          <label
            htmlFor={inputId}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-[#D4AF62] text-[#063D2E] font-bold cursor-pointer hover:bg-[#D4AF62]/10"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ImagePlus className="w-4 h-4" />}
            {value ? tr("misc.change_photo") : tr("misc.upload_photo")}
          </label>
          <input
            id={inputId}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void upload(f);
              e.target.value = "";
            }}
          />
          {value && (
            <button
              type="button"
              onClick={() => onChange("")}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-gray-200 text-gray-600 font-bold hover:bg-gray-50"
            >
              <Trash2 className="w-4 h-4" /> Retirer
            </button>
          )}
        </div>
      </div>
      {hint && <p className="text-[11px] text-gray-500">{hint}</p>}
    </div>
  );
}
