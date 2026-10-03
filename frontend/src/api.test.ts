import { describe, it, expect, vi, afterEach } from "vitest";
import { api, number, pct, price } from "./api";
afterEach(() => vi.unstubAllGlobals());
describe("Honest financial display", () => {
  it("does not invent zero for missing values", () => {
    expect(number(null)).toBe("—");
    expect(pct(undefined)).toBe("—");
    expect(price(1.12345)).toBe("1.12345");
  });
  it("propagates provider errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Forex unavailable" }),
      }),
    );
    await expect(api("/api/test")).rejects.toThrow("Forex unavailable");
  });
  it("encodes mutation bodies", async () => {
    const f = vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    vi.stubGlobal("fetch", f);
    await api("/api/watchlist", "PUT", { symbols: ["BTCUSDT"] });
    expect(f.mock.calls[0][1].body).toBe('{"symbols":["BTCUSDT"]}');
  });
});
