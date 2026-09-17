"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { api, ApiError, type UploadResult } from "@/lib/api";
import { PipelinePreview } from "@/components/pipeline-preview";
import { Spinner } from "@/components/spinner";
import {
  MAX_ATTACHMENTS,
  MAX_IDEA_LENGTH,
  MAX_TARGET_AUDIENCE_LENGTH,
  validateRawIdea,
  validateSourceUrl,
  validateTargetAudience,
} from "@/lib/intake-validation";

interface PendingAsset extends UploadResult {
  id: string;
  filename: string;
}

interface UploadingFile {
  id: string;
  filename: string;
  status: "uploading" | "error";
  error?: string;
}

export default function NewRequestPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [rawIdea, setRawIdea] = useState("");
  const [targetAudience, setTargetAudience] = useState("");
  const [sourceUrls, setSourceUrls] = useState<string[]>([""]);
  const [notes, setNotes] = useState("");
  const [assets, setAssets] = useState<PendingAsset[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const uploading = uploadingFiles.some((f) => f.status === "uploading");
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const ideaError = validateRawIdea(rawIdea);
  const sourceUrlErrors = sourceUrls.map(validateSourceUrl);
  const audienceError = validateTargetAudience(targetAudience);
  const filledSourceUrls = sourceUrls.map((u) => u.trim()).filter(Boolean);
  const noContentError =
    !rawIdea.trim() && filledSourceUrls.length === 0 && assets.length === 0
      ? "give a raw idea, a source URL, or an attachment"
      : null;
  const tooManyAttachmentsError =
    filledSourceUrls.length + assets.length > MAX_ATTACHMENTS
      ? `too many attachments — max ${MAX_ATTACHMENTS} total (source URLs + files)`
      : null;

  const formIsValid =
    !ideaError && !sourceUrlErrors.some(Boolean) && !audienceError && !noContentError && !tooManyAttachmentsError;

  function updateSourceUrl(index: number, value: string) {
    setSourceUrls((prev) => prev.map((u, i) => (i === index ? value : u)));
  }

  function addSourceUrlField() {
    setSourceUrls((prev) => [...prev, ""]);
  }

  function removeSourceUrlField(index: number) {
    setSourceUrls((prev) => (prev.length === 1 ? [""] : prev.filter((_, i) => i !== index)));
    setTouched((t) => ({ ...t, [`sourceUrl-${index}`]: false }));
  }

  async function handleFileSelect(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploadError(null);

    if (filledSourceUrls.length + assets.length + files.length > MAX_ATTACHMENTS) {
      setUploadError(`too many attachments — max ${MAX_ATTACHMENTS} total (source URLs + files)`);
      return;
    }

    const batch = Array.from(files).map((file) => ({
      file,
      id: crypto.randomUUID(),
    }));
    setUploadingFiles((prev) => [
      ...prev,
      ...batch.map(({ id, file }) => ({ id, filename: file.name, status: "uploading" as const })),
    ]);

    try {
      for (const { file, id } of batch) {
        try {
          const result = await api.uploadAsset(file);
          setAssets((prev) => [...prev, { ...result, id, filename: file.name }]);
          setUploadingFiles((prev) => prev.filter((f) => f.id !== id));
        } catch (err) {
          const message = err instanceof ApiError ? err.message : "upload failed";
          setUploadError(`${file.name}: ${message}`);
          setUploadingFiles((prev) => prev.map((f) => (f.id === id ? { ...f, status: "error", error: message } : f)));
        }
      }
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function dismissUploadFailure(id: string) {
    setUploadingFiles((prev) => prev.filter((f) => f.id !== id));
  }

  function removeAsset(id: string) {
    setAssets((prev) => prev.filter((a) => a.id !== id));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched((t) => ({
      ...t,
      idea: true,
      audience: true,
      ...Object.fromEntries(sourceUrls.map((_, i) => [`sourceUrl-${i}`, true])),
    }));
    setError(null);
    if (!formIsValid) return;

    setSubmitting(true);
    try {
      const created = await api.createRequest({
        raw_idea: rawIdea.trim() || null,
        target_audience: targetAudience.trim(),
        supporting_material: notes.trim() ? { notes: notes.trim() } : null,
        attachments: [
          ...filledSourceUrls.map((url) => ({ type: "url" as const, url })),
          ...assets.map((a) => ({
            type: (a.content_type.startsWith("image/") ? "image" : "file") as "image" | "file",
            storage_path: a.storage_path,
            description: a.filename,
          })),
        ],
      });
      router.push(`/requests/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "failed to submit request");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-3xl animate-fade-in-up gap-8 lg:grid-cols-[1fr_260px]">
      <div>
        <h1 className="text-lg font-semibold text-foreground">New content request</h1>
        <p className="mt-1 text-sm text-muted">
          Give a raw idea, a source URL, an attachment, or any combination — the system researches, drafts,
          evaluates, and prepares channel-ready content for review.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-5" noValidate>
          <Field
            label="Content idea"
            hint={`${rawIdea.length}/${MAX_IDEA_LENGTH}`}
            error={touched.idea ? ideaError : null}
          >
            <textarea
              id="raw_idea"
              rows={3}
              value={rawIdea}
              onChange={(e) => setRawIdea(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, idea: true }))}
              maxLength={MAX_IDEA_LENGTH}
              className={inputClass(touched.idea && !!ideaError)}
              placeholder="e.g. why small agencies are moving off retainers and into productized services"
            />
          </Field>

          <Field label="Source URLs" optional hint={`${filledSourceUrls.length}/${MAX_ATTACHMENTS}`}>
            <div className="space-y-2">
              {sourceUrls.map((url, i) => {
                const fieldError = touched[`sourceUrl-${i}`] ? sourceUrlErrors[i] : null;
                return (
                  <div key={i}>
                    <div className="flex min-w-0 gap-2">
                      <input
                        type="url"
                        value={url}
                        onChange={(e) => updateSourceUrl(i, e.target.value)}
                        onBlur={() => setTouched((t) => ({ ...t, [`sourceUrl-${i}`]: true }))}
                        className={`min-w-0 ${inputClass(!!fieldError)}`}
                        placeholder="https://..."
                      />
                      {(sourceUrls.length > 1 || url) && (
                        <button
                          type="button"
                          onClick={() => removeSourceUrlField(i)}
                          className="shrink-0 rounded-md border border-surface-border px-2.5 text-sm text-muted transition-colors duration-150 hover:bg-surface-card-hover hover:text-foreground"
                          aria-label={`Remove source URL ${i + 1}`}
                        >
                          ×
                        </button>
                      )}
                    </div>
                    {fieldError && <p className="mt-1 animate-fade-in text-xs text-red-600">{fieldError}</p>}
                  </div>
                );
              })}
              {tooManyAttachmentsError && <p className="text-xs text-red-600">{tooManyAttachmentsError}</p>}
              <button
                type="button"
                onClick={addSourceUrlField}
                disabled={filledSourceUrls.length + assets.length >= MAX_ATTACHMENTS}
                className="text-xs font-medium text-primary hover:underline disabled:pointer-events-none disabled:opacity-50"
              >
                + Add another source URL
              </button>
            </div>
          </Field>

          <Field
            label="Target audience"
            hint={`${targetAudience.length}/${MAX_TARGET_AUDIENCE_LENGTH}`}
            error={touched.audience ? audienceError : null}
          >
            <input
              id="target_audience"
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, audience: true }))}
              maxLength={MAX_TARGET_AUDIENCE_LENGTH}
              className={inputClass(touched.audience && !!audienceError)}
              placeholder="e.g. B2B marketing leads at 10-50 person agencies"
            />
          </Field>

          <Field label="Attachments" optional hint={`${filledSourceUrls.length + assets.length}/${MAX_ATTACHMENTS}`}>
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading || filledSourceUrls.length + assets.length >= MAX_ATTACHMENTS}
                className="flex w-full items-center justify-center gap-2 rounded-md border border-dashed border-surface-border bg-surface-base px-3 py-4 text-sm text-muted transition-colors duration-150 hover:border-primary hover:text-primary disabled:pointer-events-none disabled:opacity-50"
              >
                {uploading ? (
                  <Spinner />
                ) : (
                  <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4">
                    <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                )}
                {uploading ? "Uploading…" : "Add image or file"}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept="image/png,image/jpeg,image/webp,image/gif,application/pdf,text/plain,text/csv"
                className="hidden"
                onChange={(e) => handleFileSelect(e.target.files)}
              />
              {(assets.length > 0 || uploadingFiles.length > 0) && (
                <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {uploadingFiles.map((f) => (
                    <li
                      key={f.id}
                      className={`relative flex h-20 animate-fade-in-up flex-col items-center justify-center gap-1 overflow-hidden rounded-md border px-2 text-center text-xs ${
                        f.status === "error"
                          ? "border-red-300 bg-red-50 text-red-600"
                          : "border-surface-border bg-surface-card text-muted"
                      }`}
                    >
                      {f.status === "uploading" ? (
                        <>
                          <Spinner />
                          <span className="truncate">{f.filename}</span>
                        </>
                      ) : (
                        <>
                          <span className="truncate">{f.filename}</span>
                          <span>failed</span>
                          <button
                            type="button"
                            onClick={() => dismissUploadFailure(f.id)}
                            className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/10 text-red-700 hover:bg-black/20"
                            aria-label={`Dismiss ${f.filename}`}
                          >
                            ×
                          </button>
                        </>
                      )}
                    </li>
                  ))}
                  {assets.map((a) => (
                    <li
                      key={a.id}
                      className="group relative animate-fade-in-up overflow-hidden rounded-md border border-surface-border bg-surface-card"
                    >
                      {a.content_type.startsWith("image/") ? (
                        // eslint-disable-next-line @next/next/no-img-element -- Supabase Storage public URL, not a local/optimized asset
                        <img src={a.url} alt={a.filename} className="h-20 w-full object-cover" />
                      ) : (
                        <div className="flex h-20 items-center justify-center text-xs text-muted">{a.filename}</div>
                      )}
                      <span
                        className="absolute left-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-[10px] leading-none text-white"
                        aria-label="Uploaded"
                        title="Uploaded"
                      >
                        ✓
                      </span>
                      <button
                        type="button"
                        onClick={() => removeAsset(a.id)}
                        className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white opacity-0 transition-opacity duration-150 group-hover:opacity-100"
                        aria-label={`Remove ${a.filename}`}
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {uploadError && <p className="text-sm text-red-600">{uploadError}</p>}
            </div>
          </Field>

          <Field label="Supporting notes" optional>
            <textarea
              id="notes"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className={inputClass(false)}
              placeholder="anything else worth telling the writer"
            />
          </Field>

          {touched.idea && touched.audience && noContentError && (
            <p className="text-sm text-red-600">{noContentError}</p>
          )}
          {error && <p className="animate-fade-in text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={submitting || uploading || !formIsValid}
            className="glow-primary rounded-md bg-primary px-4 py-2 text-sm font-medium text-white transition-transform duration-150 hover:-translate-y-px hover:brightness-110 disabled:pointer-events-none disabled:opacity-50"
          >
            {submitting ? "Submitting..." : "Submit request"}
          </button>
        </form>
      </div>

      <div className="lg:pt-14">
        <PipelinePreview />
      </div>
    </div>
  );
}

function inputClass(hasError: boolean): string {
  return `mt-1 w-full rounded-md border bg-surface-card px-3 py-2 text-sm transition-colors duration-150 focus:outline-none ${
    hasError ? "border-red-400 focus:border-red-500" : "border-surface-border focus:border-primary"
  }`;
}

function Field({
  label,
  hint,
  error,
  optional,
  children,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  optional?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <label className="block text-sm font-medium text-foreground">
          {label} {optional && <span className="font-normal text-muted">(optional)</span>}
        </label>
        {hint && <span className="text-xs text-muted">{hint}</span>}
      </div>
      {children}
      {error && <p className="mt-1 animate-fade-in text-xs text-red-600">{error}</p>}
    </div>
  );
}
