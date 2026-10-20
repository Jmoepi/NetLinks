"use client";

import { useId, useRef, useState, type FormEvent } from "react";
import { api, errorMessage } from "@/lib/api";
import type { DocumentInfo } from "@/lib/types";
import { Notice } from "./Notice";

interface UploadResult {
  documents: DocumentInfo[];
  responded_info_request_ids: number[];
}

/** Multi-file PDF upload to POST /api/sme/me/documents with progress/status text. */
export function UploadForm({
  label = "Upload documents (PDF, one or more)",
  buttonText = "Upload and extract",
  onUploaded,
}: {
  label?: string;
  buttonText?: string;
  onUploaded: (result: UploadResult) => void;
}) {
  const inputId = useId();
  const hintId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const files = Array.from(inputRef.current?.files || []);
    if (!files.length) {
      setError("Choose at least one PDF file.");
      return;
    }
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    setBusy(true);
    setError(null);
    setStatus(`Uploading ${files.length} file${files.length > 1 ? "s" : ""} and extracting profile data…`);
    try {
      const result = await api.post<UploadResult>("/api/sme/me/documents", form);
      const responded = result.responded_info_request_ids.length;
      setStatus(
        `Extracted ${result.documents.length} document${result.documents.length > 1 ? "s" : ""}: ` +
          result.documents.map((d) => d.filename).join(", ") +
          "." +
          (responded ? ` ${responded} open buyer request${responded > 1 ? "s" : ""} marked as responded.` : ""),
      );
      if (inputRef.current) inputRef.current.value = "";
      onUploaded(result);
    } catch (err) {
      setStatus(null);
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="upload-form">
      <label htmlFor={inputId}>{label}</label>
      <p id={hintId} className="hint">
        Text PDFs up to 10 MB each. In Cached AI mode only the prepared demo documents can be processed.
      </p>
      <input
        id={inputId}
        ref={inputRef}
        type="file"
        name="files"
        accept="application/pdf,.pdf"
        multiple
        aria-describedby={hintId}
        disabled={busy}
      />
      <div className="button-row">
        <button type="submit" disabled={busy}>
          {busy ? "Uploading…" : buttonText}
        </button>
      </div>
      <Notice kind="success">{status}</Notice>
      <Notice kind="error">{error}</Notice>
    </form>
  );
}
