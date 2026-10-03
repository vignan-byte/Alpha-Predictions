import { describe, it, expect, vi } from "vitest";
import { Zones, chartZones } from "./Zones";
describe("Causal chart-zone rendering", () => {
  it("starts zones at confirmation and stops the original zone at invalidation", () => {
    const data = {
      zones: [
        {
          kind: "FVG",
          time: 100,
          confirmed_at: 160,
          invalidated_at: 280,
          transition_kind: "Inverse FVG",
          low: 10,
          high: 12,
          side: 1,
          status: "invalidated",
        },
      ],
    };
    const z = chartZones(data, ["fvg", "breakers"], 400, null);
    expect(z[0].start).toBe(160);
    expect(z[0].end).toBe(280);
    expect(z[1].start).toBe(280);
    expect(z[1].label).toContain("historical");
  });
  it("never draws an unavailable model as a forecast", () => {
    expect(
      chartZones({}, ["forecast"], 300, {
        status: "unavailable",
        expected_low: 1,
        expected_high: 2,
      }),
    ).toEqual([]);
    const z = chartZones({}, ["forecast"], 300, {
      status: "prediction",
      asof: 100,
      due: 200,
      expected_low: 1,
      expected_high: 2,
      direction: "Bullish",
      probability: 0.65,
    });
    expect(z[0].low).toBe(1);
    expect(z[0].label).toContain("65%");
  });
  it("recomputes rectangle coordinates after zoom and pan", () => {
    const z = new Zones();
    let scale = 10,
      offset = 0;
    z.attached({
      chart: {
        timeScale: () => ({
          logicalToCoordinate: (v: number) => v * scale + offset,
        }),
      },
      series: { priceToCoordinate: (p: number) => 100 - p },
      requestUpdate: vi.fn(),
    } as any);
    z.setBars([{ time: 100 }, { time: 160 }, { time: 220 }]);
    z.setZones([
      { start: 160, end: 280, low: 10, high: 20, label: "FVG", color: "#fff" },
    ]);
    const ctx = {
      save: vi.fn(),
      restore: vi.fn(),
      beginPath: vi.fn(),
      rect: vi.fn(),
      clip: vi.fn(),
      fillRect: vi.fn(),
      strokeRect: vi.fn(),
      setLineDash: vi.fn(),
      fillText: vi.fn(),
    };
    const target = {
      useMediaCoordinateSpace: (f: any) =>
        f({ context: ctx, mediaSize: { width: 500, height: 200 } }),
    };
    z.paneViews()[0]
      .renderer()!
      .draw(target as any);
    expect(ctx.fillRect).toHaveBeenLastCalledWith(10, 80, 20, 10);
    scale = 20;
    offset = 5;
    z.paneViews()[0]
      .renderer()!
      .draw(target as any);
    expect(ctx.fillRect).toHaveBeenLastCalledWith(25, 80, 40, 10);
  });
});
