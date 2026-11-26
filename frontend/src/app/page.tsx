"use client";

import { ChangeEvent, DragEvent, useMemo, useRef, useState } from "react";
import { useAudioRecorder } from "@/hooks/use-audio-recorder";
import { wordErrorRate } from "@/lib/word-error-rate";
import { transcribeAudio, type Transcription } from "@/lib/transcription-api";

type Scenario = { name: string; language: string; reference: string };
const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const maxSeconds = Number(
  process.env.NEXT_PUBLIC_MAX_AUDIO_DURATION_SECONDS ?? 120,
);
const scenarios: Scenario[] = [
  {
    name: "English",
    language: "en",
    reference:
      "Hello, I am developing a real-time speech recognition application.",
  },
  {
    name: "Hindi",
    language: "hi",
    reference: "नमस्ते, आज हम आर्टिफिशियल इंटेलिजेंस के बारे में बात करेंगे।",
  },
  {
    name: "Hindi-English mixed 1",
    language: "hi-en",
    reference:
      "Hello everyone, आज हम Python और Artificial Intelligence के बारे में बात करेंगे।",
  },
  {
    name: "Hindi-English mixed 2",
    language: "hi-en",
    reference:
      "आज हमारी meeting में हम project requirements और deployment के बारे में discuss करेंगे।",
  },
];
const seconds = (value: number) =>
  `${Math.floor(value / 60)}:${(value % 60).toFixed(1).padStart(4, "0")}`;

export default function Home() {
  const inputRef = useRef<HTMLInputElement>(null);
  const recorder = useAudioRecorder(maxSeconds);
  const [mode, setMode] = useState<"record" | "upload">("record");
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState("auto");
  const [result, setResult] = useState<Transcription | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const activeFile = mode === "record" ? recorder.recording : file;
  const comparison = useMemo(
    () =>
      scenario && result
        ? wordErrorRate(scenario.reference, result.text)
        : null,
    [result, scenario],
  );
  const choose = (candidate?: File) => {
    if (!candidate) return;
    if (!/[.](wav|mp3|m4a|mp4|webm)$/i.test(candidate.name)) {
      setError("Choose a WAV, MP3, M4A, MP4, or WebM audio file.");
      return;
    }
    setFile(candidate);
    setResult(null);
    setError(null);
  };
  const submit = async () => {
    if (!activeFile) {
      setError("Record or select audio before transcribing.");
      return;
    }
    if (!apiBaseUrl) {
      setError(
        "The frontend API URL is not configured. Restart Next.js after setting NEXT_PUBLIC_API_BASE_URL.",
      );
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await transcribeAudio(apiBaseUrl, activeFile, language));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to reach the transcription service.",
      );
    } finally {
      setLoading(false);
    }
  };
  const clear = () => {
    setFile(null);
    recorder.clearRecording();
    setResult(null);
    setError(null);
    setScenario(null);
    if (inputRef.current) inputRef.current.value = "";
  };
  const chooseScenario = (item: Scenario) => {
    setScenario(item);
    setLanguage(item.language);
    setMode("record");
    setResult(null);
    setError(null);
  };
  return (
    <main className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100 sm:px-6">
      <div className="mx-auto max-w-5xl">
        <header className="mb-10 text-center">
          <p className="mb-3 text-sm font-bold tracking-[.24em] text-cyan-300">
            SPEECHFLOW AI
          </p>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Multilingual speech, made clear.
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-slate-400">
            Record from your Mac microphone or upload audio for local
            Faster-Whisper transcription.
          </p>
        </header>
        <section className="rounded-2xl border border-slate-700 bg-slate-900/70 p-5 shadow-2xl sm:p-8">
          <div className="flex border-b border-slate-700" role="tablist">
            <button
              role="tab"
              aria-selected={mode === "record"}
              onClick={() => setMode("record")}
              className={`px-4 py-3 font-semibold ${mode === "record" ? "border-b-2 border-cyan-300 text-cyan-200" : "text-slate-400"}`}
            >
              Record Audio
            </button>
            <button
              role="tab"
              aria-selected={mode === "upload"}
              onClick={() => setMode("upload")}
              className={`px-4 py-3 font-semibold ${mode === "upload" ? "border-b-2 border-cyan-300 text-cyan-200" : "text-slate-400"}`}
            >
              Upload Audio
            </button>
          </div>
          {mode === "record" ? (
            <div className="py-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold">
                    Microphone recording
                  </h2>
                  <p className="mt-1 text-sm text-slate-400">
                    Maximum recording: {maxSeconds / 60} minutes
                  </p>
                </div>
                <span
                  className={`rounded-full px-3 py-1 text-xs font-bold ${recorder.status === "recording" ? "bg-red-400/20 text-red-200" : "bg-slate-800 text-slate-300"}`}
                >
                  {recorder.status === "recording"
                    ? "● Recording"
                    : recorder.status}
                </span>
              </div>
              <div className="mt-6 rounded-xl bg-slate-800 p-5">
                <div
                  className="flex h-16 items-center gap-1"
                  aria-label="Microphone audio level"
                >
                  {Array.from({ length: 24 }, (_, index) => (
                    <span
                      key={index}
                      className="w-full rounded-full bg-cyan-300 transition-all"
                      style={{
                        height: `${Math.max(8, Math.min(100, recorder.level * 160 + (index % 4) * 9))}%`,
                        opacity:
                          recorder.status === "recording"
                            ? 0.45 + recorder.level
                            : 0.15,
                      }}
                    />
                  ))}
                </div>
                <div className="mt-3 flex items-center justify-between font-mono text-sm">
                  <span>{seconds(recorder.duration)}</span>
                  <span>
                    {recorder.status === "recording"
                      ? "Listening to microphone"
                      : "Audio-level visualization"}
                  </span>
                </div>
              </div>
              <div className="mt-5 flex flex-wrap gap-3">
                {recorder.status !== "recording" && (
                  <button
                    disabled={
                      recorder.capability !== "supported" ||
                      recorder.status === "requesting"
                    }
                    onClick={recorder.start}
                    className="rounded-lg bg-cyan-400 px-5 py-2.5 font-bold text-slate-950 disabled:opacity-50"
                  >
                    {recorder.capability === "checking"
                      ? "Checking microphone support…"
                      : recorder.recording
                        ? "Record Again"
                        : "Start Recording"}
                  </button>
                )}
                {recorder.status === "recording" && (
                  <>
                    <button
                      onClick={recorder.stop}
                      className="rounded-lg bg-red-400 px-5 py-2.5 font-bold text-slate-950"
                    >
                      Stop Recording
                    </button>
                    <button
                      onClick={recorder.cancel}
                      className="rounded-lg border border-slate-600 px-5 py-2.5 font-semibold"
                    >
                      Cancel
                    </button>
                  </>
                )}
              </div>
              {recorder.capability === "unsupported" && (
                <p className="mt-4 text-sm text-amber-200" role="status">
                  Microphone recording is not supported in this browser. You can
                  still upload audio.
                </p>
              )}
              {recorder.previewUrl && (
                <>
                  <audio
                    className="mt-5 w-full"
                    controls
                    src={recorder.previewUrl}
                  >
                    Your browser cannot play this recording.
                  </audio>
                  <a
                    href={recorder.previewUrl}
                    download={recorder.recording?.name}
                    className="mt-3 inline-block rounded-lg border border-cyan-400/70 px-3 py-2 text-sm font-semibold text-cyan-200"
                  >
                    Download Recording
                  </a>
                </>
              )}
              {recorder.metadata && (
                <details className="mt-4 rounded-lg bg-slate-800 p-3 text-sm">
                  <summary className="cursor-pointer font-semibold text-slate-300">
                    Recording diagnostics
                  </summary>
                  <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                    <div>
                      <dt className="text-slate-400">MIME type</dt>
                      <dd>{recorder.metadata.mimeType}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-400">File size</dt>
                      <dd>
                        {(recorder.metadata.size / 1024 / 1024).toFixed(2)} MB
                      </dd>
                    </div>
                    <div>
                      <dt className="text-slate-400">Duration</dt>
                      <dd>{seconds(recorder.metadata.duration)}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-400">Audio chunks</dt>
                      <dd>{recorder.metadata.chunkCount}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-400">Peak input level</dt>
                      <dd>{recorder.metadata.peakLevel.toFixed(4)}</dd>
                    </div>
                  </dl>
                </details>
              )}
              {recorder.error && (
                <p className="mt-4 text-sm text-red-200" role="alert">
                  {recorder.error}
                </p>
              )}
            </div>
          ) : (
            <div
              className={`my-6 cursor-pointer rounded-xl border-2 border-dashed p-8 text-center ${dragging ? "border-cyan-300 bg-cyan-300/10" : "border-slate-600"}`}
              onClick={() => inputRef.current?.click()}
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event: DragEvent<HTMLDivElement>) => {
                event.preventDefault();
                setDragging(false);
                choose(event.dataTransfer.files[0]);
              }}
              role="button"
              tabIndex={0}
              onKeyDown={(event) =>
                event.key === "Enter" && inputRef.current?.click()
              }
            >
              <input
                ref={inputRef}
                className="sr-only"
                type="file"
                accept=".wav,.mp3,.m4a,.mp4,.webm,audio/*"
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  choose(event.target.files?.[0])
                }
              />
              <p className="text-lg font-medium">
                Drop audio here, or click to browse
              </p>
              <p className="mt-2 text-sm text-slate-400">
                WAV, MP3, M4A, MP4, or WebM · up to 10 MB · 2 minutes
              </p>
            </div>
          )}
          {activeFile && (
            <div className="mt-3 flex justify-between rounded-lg bg-slate-800 px-4 py-3 text-sm">
              <span className="truncate pr-3">{activeFile.name}</span>
              <span>{(activeFile.size / 1024 / 1024).toFixed(2)} MB</span>
            </div>
          )}
          <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <label className="text-sm font-medium">
              Recognition mode
              <select
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
                className="mt-2 block w-56 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2.5"
              >
                <option value="auto">Auto Detect</option>
                <option value="en">English</option>
                <option value="hi">Hindi</option>
                <option value="hi-en">Hindi-English mixed</option>
              </select>
            </label>
            <div className="flex gap-3">
              <button
                onClick={clear}
                className="rounded-lg border border-slate-600 px-4 py-2.5 font-semibold"
              >
                Clear
              </button>
              <button
                disabled={
                  !activeFile || loading || recorder.status === "recording"
                }
                onClick={submit}
                className="rounded-lg bg-cyan-400 px-5 py-2.5 font-bold text-slate-950 disabled:opacity-50"
              >
                {loading ? "Transcribing…" : "Transcribe"}
              </button>
            </div>
          </div>
          {loading && (
            <p className="mt-5 text-sm text-cyan-200" role="status">
              Processing your actual audio with Faster-Whisper…
            </p>
          )}
          {error && (
            <p
              className="mt-5 rounded-lg bg-red-950/40 p-3 text-sm text-red-200"
              role="alert"
            >
              {error}
            </p>
          )}
        </section>
        <section className="mt-6 rounded-2xl border border-slate-700 bg-slate-900/70 p-5 sm:p-8">
          <h2 className="text-xl font-semibold">Recognition test panel</h2>
          <p className="mt-1 text-sm text-slate-400">
            The reference is never sent to the model; it is only compared after
            your actual recording.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {scenarios.map((item) => (
              <button
                key={item.name}
                onClick={() => chooseScenario(item)}
                className={`rounded-lg border p-4 text-left ${scenario?.name === item.name ? "border-cyan-300 bg-cyan-300/10" : "border-slate-700 hover:border-slate-500"}`}
              >
                <strong>{item.name}</strong>
                <span className="mt-1 block text-sm text-slate-400">
                  {item.reference}
                </span>
              </button>
            ))}
          </div>
        </section>
        {result && (
          <section className="mt-6 rounded-2xl border border-slate-700 bg-slate-900/70 p-5 sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-xl font-semibold">Actual transcription</h2>
              <button
                onClick={() => navigator.clipboard.writeText(result.text)}
                className="rounded-lg border border-cyan-400/70 px-3 py-2 text-sm font-semibold text-cyan-200"
              >
                Copy text
              </button>
            </div>
            <p className="mt-5 whitespace-pre-wrap text-lg leading-8">
              {result.text || "No speech was detected."}
            </p>
            <details className="mt-5 rounded-lg bg-slate-800 p-4 text-sm">
              <summary className="cursor-pointer font-semibold text-slate-200">
                Transcription diagnostics
              </summary>
              <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <div className="rounded-lg bg-slate-800 p-3 sm:col-span-2 lg:col-span-3">
                  <dt className="text-slate-400">Loaded model</dt>
                  <dd className="mt-1 break-all font-semibold">{result.model}</dd>
                </div>
                <div className="rounded-lg bg-slate-800 p-3">
                  <dt className="text-slate-400">Selected recognition mode</dt>
                  <dd className="mt-1 font-semibold">
                    {result.recognition_mode}
                  </dd>
                </div>
                <div className="rounded-lg bg-slate-800 p-3">
                  <dt className="text-slate-400">Conditioned language</dt>
                  <dd className="mt-1 font-semibold">
                    {result.conditioned_language ?? "None (automatic detection)"}
                  </dd>
                </div>
                <div className="rounded-lg bg-slate-800 p-3">
                  <dt className="text-slate-400">Detected language</dt>
                  <dd className="mt-1 font-semibold">
                    {result.language} (
                    {Math.round(result.language_probability * 100)}%)
                  </dd>
                </div>
                <div className="rounded-lg bg-slate-800 p-3">
                  <dt className="text-slate-400">Output script</dt>
                  <dd className="mt-1 font-semibold">{result.output_script}</dd>
                </div>
                <div className="rounded-lg bg-slate-800 p-3">
                  <dt className="text-slate-400">Audio duration</dt>
                  <dd className="mt-1 font-semibold">
                    {seconds(result.duration_seconds)}
                  </dd>
                </div>
                <div className="rounded-lg bg-slate-800 p-3">
                  <dt className="text-slate-400">Processing time</dt>
                  <dd className="mt-1 font-semibold">
                    {result.processing_time_seconds.toFixed(2)}s
                  </dd>
                </div>
              </dl>
              {(result.script_warning || result.quality_warning) && (
                <p
                  className="mt-4 rounded-lg bg-amber-950/40 p-3 text-sm text-amber-100"
                  role="status"
                >
                  {result.script_warning ?? result.quality_warning}
                </p>
              )}
            </details>
            {scenario ? (
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div className="rounded-lg bg-slate-800 p-4">
                  <h3 className="font-semibold">Reference sentence</h3>
                  <p className="mt-2">{scenario.reference}</p>
                </div>
                <div className="rounded-lg bg-slate-800 p-4">
                  <h3 className="font-semibold">Recognized text</h3>
                  <p className="mt-2">{result.text}</p>
                </div>
                <p className="text-sm text-slate-400 md:col-span-2">
                  {comparison !== null
                    ? `Word Error Rate: ${(comparison * 100).toFixed(1)}%`
                    : ""}{" "}
                  Normalization lowercases text and removes punctuation. This is
                  not a universal accuracy score; transliteration and scripts
                  can change the comparison.
                </p>
              </div>
            ) : null}
            <div className="mt-6 border-t border-slate-700 pt-5">
              <h3 className="font-semibold">Timestamped segments</h3>
              <ol className="mt-3 space-y-3">
                {result.segments.map((segment, index) => (
                  <li
                    key={`${segment.start}-${index}`}
                    className="grid gap-2 rounded-lg bg-slate-800 p-3 sm:grid-cols-[7rem_1fr]"
                  >
                    <span className="font-mono text-sm text-cyan-200">
                      {seconds(segment.start)} – {seconds(segment.end)}
                    </span>
                    <span>{segment.text}</span>
                  </li>
                ))}
              </ol>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
