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

export async function transcribeAudio(apiBaseUrl: string, file: File, language: string): Promise<Transcription> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("language", language);
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
