import { useEffect, useState } from "react";
export async function api(path: string, method = "GET", body?: unknown) {
  const response = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
export function useData(path: string, interval = 0) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [version, setVersion] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setError("");
    setLoading(true);
    const load = async () => {
      try {
        const d = await api(path);
        if (active) {
          setData(d);
          setError("");
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    const timer = interval ? setInterval(load, interval) : undefined;
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [path, interval, version]);
  return {
    data,
    error,
    loading,
    refresh: () => setVersion((v) => v + 1),
    setData,
  };
}
export const number = (v: number | null | undefined, digits = 2) =>
  v == null || !Number.isFinite(v)
    ? "—"
    : v.toLocaleString("en-US", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
export const pct = (v: number | null | undefined) =>
  v == null ? "—" : number(v * 100, 1) + "%";
export const price = (v: number | null | undefined) =>
  number(v, v != null && v < 10 ? 5 : 2);
