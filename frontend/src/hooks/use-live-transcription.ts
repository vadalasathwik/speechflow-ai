"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Status = "idle" | "connecting" | "recording" | "stopping" | "completed" | "cancelled" | "error";
type ServerMessage = { type: string; text?: string; message?: string; detected_language?: string | null; language_probability?: number | null };

function wavFile(chunks: Float32Array[], sampleRate: number): File {
  const sampleCount = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const bytes = new ArrayBuffer(44 + sampleCount * 2);
  const view = new DataView(bytes);
  const write = (offset: number, value: string) => [...value].forEach((character, index) => view.setUint8(offset + index, character.charCodeAt(0)));
  write(0, "RIFF"); view.setUint32(4, 36 + sampleCount * 2, true); write(8, "WAVE"); write(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, sampleCount * 2, true);
  let offset = 44;
  for (const chunk of chunks) for (const sample of chunk) { const value = Math.max(-1, Math.min(1, sample)); view.setInt16(offset, value < 0 ? value * 0x8000 : value * 0x7fff, true); offset += 2; }
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  return new File([bytes], `speechflow-recording-${stamp}.wav`, { type: "audio/wav" });
}

function websocketEndpoint(api?: string): string {
  // An empty API base intentionally means the same public origin. This keeps the
  // WebSocket, session cookie, and CSRF Origin on one site behind the demo proxy.
  const url = new URL(api || window.location.origin, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/transcribe";
  return url.toString();
}

export function useLiveTranscription() {
  const [status, setStatus] = useState<Status>("idle");
  const [partial, setPartial] = useState("");
  const [finalText, setFinalText] = useState("");
  const [detectedLanguage, setDetectedLanguage] = useState<string | null>(null);
  const [languageProbability, setLanguageProbability] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [duration, setDuration] = useState(0);
  const [level, setLevel] = useState(0);
  const [recording, setRecording] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [capturedSampleCount, setCapturedSampleCount] = useState(0);
  const socket = useRef<WebSocket | null>(null);
  const media = useRef<MediaStream | null>(null);
  const context = useRef<AudioContext | null>(null);
  const worklet = useRef<AudioWorkletNode | null>(null);
  const animation = useRef<number | null>(null);
  const timer = useRef<number | null>(null);
  const finalizationTimer = useRef<number | null>(null);
  const acceptingAudio = useRef(false);
  const stopSent = useRef(false);
  const startedAt = useRef(0);
  const capturedFrames = useRef<Float32Array[]>([]);
  const sampleRate = useRef(0);
  const capturedSamples = useRef(0);
  const maxCapturedSamples = useRef(0);

  const stopVisuals = useCallback(() => {
    if (animation.current) cancelAnimationFrame(animation.current);
    if (timer.current) clearInterval(timer.current);
    animation.current = timer.current = null;
    setLevel(0);
  }, []);
  const releaseCapture = useCallback(() => {
    acceptingAudio.current = false;
    if (worklet.current) worklet.current.port.onmessage = null;
    worklet.current?.disconnect(); worklet.current = null;
    media.current?.getTracks().forEach((track) => track.stop()); media.current = null;
    void context.current?.close(); context.current = null;
    stopVisuals();
  }, [stopVisuals]);
  const clearRecording = useCallback(() => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null); setRecording(null); capturedFrames.current = []; capturedSamples.current = 0; setCapturedSampleCount(0);
  }, [previewUrl]);
  const closeSession = useCallback(() => {
    releaseCapture();
    if (finalizationTimer.current) clearTimeout(finalizationTimer.current);
    finalizationTimer.current = null;
    socket.current?.close(); socket.current = null;
  }, [releaseCapture]);
  const clear = useCallback(() => { closeSession(); clearRecording(); stopSent.current = false; setPartial(""); setFinalText(""); setDetectedLanguage(null); setLanguageProbability(null); setError(null); setDuration(0); setStatus("idle"); }, [clearRecording, closeSession]);

  const start = useCallback(async () => {
    const address = websocketEndpoint(process.env.NEXT_PUBLIC_API_BASE_URL);
    clear(); setStatus("connecting");
    try {
      const input = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      media.current = input;
      const audio = new AudioContext(); context.current = audio; sampleRate.current = audio.sampleRate; maxCapturedSamples.current = audio.sampleRate * 120; capturedFrames.current = []; capturedSamples.current = 0; setCapturedSampleCount(0);
      await audio.audioWorklet.addModule("/worklets/pcm-recorder-processor.js");
      const source = audio.createMediaStreamSource(input), analyser = audio.createAnalyser(), processor = new AudioWorkletNode(audio, "pcm-recorder");
      analyser.fftSize = 512; source.connect(analyser); source.connect(processor); worklet.current = processor;
      const ws = new WebSocket(address); socket.current = ws;
      ws.onopen = () => ws.send(JSON.stringify({ type: "start", sample_rate: audio.sampleRate, channels: 1, pcm_format: "s16le" }));
      processor.port.onmessage = ({ data }: MessageEvent<Float32Array>) => {
        if (!acceptingAudio.current || ws.readyState !== WebSocket.OPEN) return;
        if (capturedSamples.current + data.length <= maxCapturedSamples.current) { capturedFrames.current.push(data.slice()); capturedSamples.current += data.length; if (capturedSamples.current % 4096 < data.length) setCapturedSampleCount(capturedSamples.current); }
        const pcm = new Int16Array(data.length);
        data.forEach((sample, index) => { pcm[index] = Math.max(-1, Math.min(1, sample)) * 32767; });
        ws.send(pcm.buffer);
      };
      ws.onmessage = ({ data }) => {
        const message = JSON.parse(data) as ServerMessage;
        if (message.type === "ready") { acceptingAudio.current = true; startedAt.current = performance.now(); setStatus("recording"); timer.current = window.setInterval(() => setDuration((performance.now() - startedAt.current) / 1000), 100); }
        if (message.type === "partial") setPartial(message.text ?? "");
        if (message.type === "final") { if (message.text) setFinalText(message.text); setPartial(""); }
        if (message.detected_language) { setDetectedLanguage(message.detected_language); setLanguageProbability(message.language_probability ?? null); }
        if (message.type === "completed") { if (message.text) setFinalText(message.text); closeSession(); setStatus(message.type === "completed" ? "completed" : "cancelled"); }
        if (message.type === "error") { setError(message.message ?? "Live transcription failed."); closeSession(); setStatus("error"); }
      };
      ws.onerror = () => { setError("WebSocket connection failed. Confirm the backend is running."); closeSession(); setStatus("error"); };
      const draw = () => { const values = new Float32Array(analyser.fftSize); analyser.getFloatTimeDomainData(values); setLevel(Math.sqrt(values.reduce((sum, value) => sum + value * value, 0) / values.length)); animation.current = requestAnimationFrame(draw); }; draw();
    } catch (cause) { setError(cause instanceof DOMException && cause.name === "NotAllowedError" ? "Microphone permission was denied." : "Unable to start live transcription."); closeSession(); setStatus("error"); }
  }, [clear, closeSession]);

  const stop = useCallback(() => {
    const ws = socket.current;
    if (stopSent.current || !ws || ws.readyState !== WebSocket.OPEN) return;
    stopSent.current = true; setStatus("stopping");
    if (capturedFrames.current.length && sampleRate.current) { const file = wavFile(capturedFrames.current, sampleRate.current); if (previewUrl) URL.revokeObjectURL(previewUrl); setRecording(file); setPreviewUrl(URL.createObjectURL(file)); }
    releaseCapture();
    ws.send(JSON.stringify({ type: "stop" }));
    finalizationTimer.current = window.setTimeout(() => { setError("Finalization timed out. Any received transcript was preserved."); ws.close(); setStatus("error"); }, 45_000);
  }, [previewUrl, releaseCapture]);
  useEffect(() => () => { closeSession(); }, [closeSession]);
  return { status, partial, finalText, detectedLanguage, languageProbability, error, duration, level, recording, previewUrl, capturedSamples: capturedSampleCount, start, stop, clear };
}
