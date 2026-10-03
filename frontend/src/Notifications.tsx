import { useEffect, useRef, useState } from "react";
import { useData, price } from "./api";
let audio: AudioContext | undefined;
export function Notifications() {
  const feed = useData("/api/notifications", 10000),
    seen = useRef<Set<string> | null>(null);
  const [enabled, setEnabled] = useState(false),
    [sound, setSound] = useState(false),
    [message, setMessage] = useState("");
  useEffect(() => {
    if (!feed.data) return;
    if (!seen.current) {
      seen.current = new Set(feed.data.map((n: any) => n.id));
      return;
    }
    for (const n of [...feed.data].reverse()) {
      if (seen.current.has(n.id)) continue;
      seen.current.add(n.id);
      const text = `${n.symbol} · ${n.kind === "signal" ? n.signal : n.kind} · ${price(n.price)} · ${n.source}`;
      setMessage(text);
      if (
        enabled &&
        "Notification" in window &&
        Notification.permission === "granted"
      )
        new Notification("AlphaPredictorsAI alert", { body: text, tag: n.id });
      if (sound && audio?.state === "running") {
        const osc = audio.createOscillator(),
          gain = audio.createGain();
        osc.connect(gain);
        gain.connect(audio.destination);
        gain.gain.setValueAtTime(0.08, audio.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 0.3);
        osc.frequency.value = 660;
        osc.start();
        osc.stop(audio.currentTime + 0.3);
      }
    }
  }, [feed.data, enabled, sound]);
  return (
    <div className="notification-controls">
      <button
        onClick={async () => {
          if (!("Notification" in window)) {
            setMessage("This browser does not support notifications.");
            return;
          }
          const p = await Notification.requestPermission();
          setEnabled(p === "granted");
          setMessage(
            p === "granted"
              ? "Browser notifications enabled while this workspace is open."
              : "Browser notification permission was not granted.",
          );
        }}
      >
        {enabled ? "Notifications on" : "Enable notifications"}
      </button>
      <button
        onClick={async () => {
          if (!sound) {
            audio ??= new AudioContext();
            await audio.resume();
          }
          setSound(!sound);
        }}
      >
        {sound ? "Sound on" : "Sound off"}
      </button>
      {message && <span role="status">{message}</span>}
    </div>
  );
}
