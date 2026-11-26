"use client";

import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { transcribeAudio, type Transcription } from "@/lib/transcription-api";
import { useLiveTranscription } from "@/hooks/use-live-transcription";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
const formatDuration = (seconds: number) => `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`;
const languageName = (language?: string | null) => language === "en" ? "English" : language === "hi" ? "Hindi" : "Language not detected";
const Icon = ({ name }: { name: "mic" | "upload" | "stop" | "copy" | "download" | "trash" | "chevron" }) => {
  const paths = { mic: <><rect x="9" y="2" width="6" height="11" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v4M8 21h8"/></>, upload: <><path d="M12 16V3M7 8l5-5 5 5M5 14v5h14v-5"/></>, stop: <rect x="6" y="6" width="12" height="12" rx="1"/>, copy: <><rect x="9" y="9" width="10" height="10" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></>, download: <><path d="M12 3v12M7 10l5 5 5-5M5 21h14"/></>, trash: <><path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6"/></>, chevron: <path d="m6 9 6 6 6-6"/> };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
};

export default function Home() {
  const live = useLiveTranscription();
  const inputRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<"record" | "upload">("record");
  const [file, setFile] = useState<File | null>(null);
  const [batch, setBatch] = useState<Transcription | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [uploadUrl, setUploadUrl] = useState<string | null>(null);
  const recording = tab === "record";
  const transcript = recording ? live.finalText || live.partial : batch?.text;
  const detected = recording ? live.detectedLanguage : batch?.language;
  const status = live.status === "recording" ? "Recording" : live.status === "stopping" ? "Finalizing transcription..." : "Ready to record";
  const bars = Array.from({ length: 50 }, (_, index) => Math.max(8, Math.min(70, 8 + live.level * 420 * (0.55 + ((index * 17) % 10) / 20))));
  const choose = (candidate?: File) => { if (!candidate) return; if (!/[.](wav|mp3|m4a|mp4|webm)$/i.test(candidate.name)) { setError("Choose WAV, MP3, M4A, MP4, or WebM audio."); return; } if (uploadUrl) URL.revokeObjectURL(uploadUrl); setUploadUrl(URL.createObjectURL(candidate)); setFile(candidate); setBatch(null); setError(null); };
  const submit = async () => { if (!file || !apiBaseUrl) { setError(file ? "API URL is not configured." : "Choose an audio file first."); return; } setLoading(true); setError(null); try { setBatch(await transcribeAudio(apiBaseUrl, file)); } catch (cause) { setError(cause instanceof Error ? cause.message : "Transcription failed."); } finally { setLoading(false); } };
  const clear = () => { live.clear(); if (uploadUrl) URL.revokeObjectURL(uploadUrl); setUploadUrl(null); setFile(null); setBatch(null); setError(null); if (inputRef.current) inputRef.current.value = ""; };
  const audioUrl = recording ? live.previewUrl : uploadUrl; const audioFile = recording ? live.recording : file;
  return <main className="sf-page"><div className="sf-shell"><header className="sf-header"><p>SPEECHFLOW AI</p><h1>English and Hindi speech-to-text</h1><span>Speak naturally. Get real-time transcription.</span></header><section className="sf-app"><div className="sf-tabs"><button className={recording ? "is-active" : ""} onClick={() => { live.clear(); setTab("record"); }}><Icon name="mic"/><span>Record Audio</span></button><button className={!recording ? "is-active" : ""} onClick={() => { live.clear(); setTab("upload"); }}><Icon name="upload"/><span>Upload Audio</span></button></div><div className="sf-language"><span>Detected language</span><strong>{detected ? languageName(detected) : recording && live.status !== "idle" ? "Detecting language..." : "Language not detected"}</strong></div>{recording ? <section className="sf-recorder"><div className={`sf-status ${live.status === "recording" ? "is-recording" : ""}`}><i/><span>{status}</span></div><time>{formatDuration(live.duration)}</time><div className="sf-wave" aria-label="Live microphone level">{bars.map((height, index) => <i key={index} style={{ height: `${live.status === "recording" ? height : 8}px` }}/>)}</div>{live.status === "recording" ? <button className="sf-record-button sf-stop" onClick={live.stop}><Icon name="stop"/>Stop Recording</button> : <button disabled={live.status === "stopping"} className="sf-record-button sf-start" onClick={() => live.start()}><Icon name="mic"/>{live.status === "stopping" ? "Finalizing transcription..." : "Start Recording"}</button>}</section> : <section className={`sf-upload ${dragging ? "is-dragging" : ""}`} onClick={() => inputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event: DragEvent<HTMLDivElement>) => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files[0]); }}><input ref={inputRef} type="file" accept=".wav,.mp3,.m4a,.mp4,.webm,audio/*" onChange={(event: ChangeEvent<HTMLInputElement>) => choose(event.target.files?.[0])}/><Icon name="upload"/><p>{file ? file.name : "Drag and drop audio here, or click to browse"}</p><small>WAV, MP3, M4A, MP4, or WebM · up to 10 MB · 2 minutes</small><button disabled={!file || loading} onClick={(event) => { event.stopPropagation(); void submit(); }}>{loading ? "Transcribing..." : "Transcribe Audio"}</button></section>}{audioUrl && <section className="sf-player"><audio controls src={audioUrl}/><span>{audioFile?.type || "audio"}</span></section>}{(live.error || error) && <p className="sf-error">{live.error || error}</p>}<section className="sf-transcript"><div><h2>Transcription</h2>{transcript && <button onClick={() => navigator.clipboard.writeText(transcript)}><Icon name="copy"/>Copy</button>}</div><p>{transcript || ""}</p></section><div className="sf-actions">{audioUrl && audioFile ? <a href={audioUrl} download={audioFile.name}><Icon name="download"/>Download Audio</a> : <button disabled><Icon name="download"/>Download Audio</button>}<button onClick={clear}><Icon name="trash"/>Clear</button></div><details className="sf-diagnostics"><summary>Technical diagnostics and timestamped segments <Icon name="chevron"/></summary>{batch && <ol>{batch.segments.map((segment, index) => <li key={index}>{formatDuration(segment.start)} – {formatDuration(segment.end)}: {segment.text}</li>)}</ol>}<p>{recording ? `Connection: ${live.status}. Captured PCM samples: ${live.capturedSamples}.` : `Model: ${batch?.model ?? "not run"}`}</p></details></section></div></main>;
}
