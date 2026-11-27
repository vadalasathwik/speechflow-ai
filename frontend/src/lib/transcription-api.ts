export type Transcription = {
  text: string;
  language: string;
  language_probability: number;
  duration_seconds: number;
  processing_time_seconds: number;
  real_time_factor: number;
  model: string;
  recognition_mode: string;
  conditioned_language: string | null;
  output_script: string;
  script_warning: string | null;
  original_text: string | null;
  quality_warning: string | null;
  retry_performed: boolean;
  segments: { start: number; end: number; text: string }[];
};

export type SavedTranscription = {
  id: string;
  title: string;
  text: string;
  detected_language: string | null;
  source_type: "recording" | "upload";
  duration_seconds: number | null;
  model_name: string | null;
  created_at: string;
  updated_at: string;
};

export type SavedTranscriptionPage = {
  items: SavedTranscription[];
  total: number;
  page: number;
  page_size: number;
};

export type CreateSavedTranscription = Pick<SavedTranscription, "title" | "text" | "detected_language" | "source_type" | "duration_seconds" | "model_name">;
export type UpdateSavedTranscription = Pick<SavedTranscription, "title" | "text">;
export type HistoryQuery = { page: number; pageSize: number; search?: string; language?: string };

type FastApiDetail = string | { msg?: string }[];
type ErrorPayload = { detail?: FastApiDetail };

function detailMessage(payload: ErrorPayload | null): string | undefined {
  if (typeof payload?.detail === "string") return payload.detail;
  if (Array.isArray(payload?.detail)) return payload.detail.map((item) => item.msg).filter(Boolean).join(" ");
  return undefined;
}

async function readPayload(response: Response): Promise<ErrorPayload | Transcription | null> {
  const body = await response.text();
  if (!body) return null;
  try { return JSON.parse(body) as ErrorPayload | Transcription; } catch { return null; }
}

async function historyRequest<T>(apiBaseUrl: string, path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}/api/transcriptions${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new Error("Cannot reach the SpeechFlow API. Confirm the backend is running and permits this frontend origin.");
  }
  const payload = await readPayload(response);
  if (response.ok) return payload as T;
  throw new Error(detailMessage(payload as ErrorPayload | null) || `History request failed (${response.status}).`);
}

export function createSavedTranscription(apiBaseUrl: string, payload: CreateSavedTranscription, signal?: AbortSignal): Promise<SavedTranscription> {
  return historyRequest<SavedTranscription>(apiBaseUrl, "", { method: "POST", body: JSON.stringify(payload), signal });
}

export function listSavedTranscriptions(apiBaseUrl: string, query: HistoryQuery, signal?: AbortSignal): Promise<SavedTranscriptionPage> {
  const params = new URLSearchParams({ page: String(query.page), page_size: String(query.pageSize) });
  if (query.search?.trim()) params.set("search", query.search.trim());
  if (query.language) params.set("language", query.language);
  return historyRequest<SavedTranscriptionPage>(apiBaseUrl, `?${params.toString()}`, { signal });
}

export function getSavedTranscription(apiBaseUrl: string, id: string, signal?: AbortSignal): Promise<SavedTranscription> {
  return historyRequest<SavedTranscription>(apiBaseUrl, `/${encodeURIComponent(id)}`, { signal });
}

export function updateSavedTranscription(apiBaseUrl: string, id: string, payload: UpdateSavedTranscription, signal?: AbortSignal): Promise<SavedTranscription> {
  return historyRequest<SavedTranscription>(apiBaseUrl, `/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload), signal });
}

export function deleteSavedTranscription(apiBaseUrl: string, id: string, signal?: AbortSignal): Promise<void> {
  return historyRequest<void>(apiBaseUrl, `/${encodeURIComponent(id)}`, { method: "DELETE", signal });
}

export async function transcribeAudio(apiBaseUrl: string, file: File): Promise<Transcription> {
  const formData = new FormData();
  formData.append("file", file);
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 180_000);
  try {
    const response = await fetch(`${apiBaseUrl}/api/transcribe`, { method: "POST", body: formData, signal: controller.signal });
    const payload = await readPayload(response);
    if (response.ok && payload && "text" in payload) return payload;
    const detail = detailMessage(payload as ErrorPayload | null);
    const fallback = response.status === 400 ? "The audio request is invalid." : response.status === 413 ? "The audio file is larger than the allowed limit." : response.status === 422 ? "The audio request could not be validated." : response.status === 503 ? "The speech recognition model is unavailable." : response.status >= 500 ? "The transcription service encountered an error." : "The transcription request failed.";
    throw new Error(detail || fallback);
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw new Error("Transcription timed out. Try a shorter recording.");
    if (cause instanceof TypeError) throw new Error("Cannot read the SpeechFlow API response. Confirm that the backend is running and permits this frontend origin.");
    throw cause;
  } finally { window.clearTimeout(timeout); }
}
