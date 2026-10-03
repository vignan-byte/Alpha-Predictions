import type {
  ISeriesPrimitive,
  SeriesAttachedParameter,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  Logical,
  Time,
} from "lightweight-charts";
export type Zone = {
  start: number;
  end: number;
  low?: number;
  high?: number;
  label: string;
  color: string;
  session?: boolean;
  faded?: boolean;
};
/** Native chart primitive: coordinates are recomputed for every pan, zoom and price-scale draw. */
export class Zones implements ISeriesPrimitive<Time> {
  private context?: SeriesAttachedParameter<Time>;
  private times: number[] = [];
  private zones: Zone[] = [];
  private view: IPrimitivePaneView = {
    zOrder: () => "bottom",
    renderer: () => this.renderer,
  };
  private renderer: IPrimitivePaneRenderer = {
    draw: (target) =>
      target.useMediaCoordinateSpace((scope) => {
        const api = this.context;
        if (!api || this.times.length < 2) return;
        const ctx = scope.context,
          w = scope.mediaSize.width,
          h = scope.mediaSize.height;
        const x = (stamp: number) =>
          api.chart
            .timeScale()
            .logicalToCoordinate(this.logical(stamp) as Logical);
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, 0, w, h);
        ctx.clip();
        for (const z of this.zones) {
          const left = x(z.start),
            right = x(z.end);
          const top = z.session ? 0 : api.series.priceToCoordinate(z.high!),
            bottom = z.session ? h : api.series.priceToCoordinate(z.low!);
          if (
            left == null ||
            right == null ||
            top == null ||
            bottom == null ||
            right < 0 ||
            left > w
          )
            continue;
          const a = Math.max(0, left),
            b = Math.min(w, right),
            y = Math.min(top, bottom),
            height = Math.max(2, Math.abs(bottom - top));
          ctx.globalAlpha = z.session ? 0.045 : z.faded ? 0.07 : 0.14;
          ctx.fillStyle = z.color;
          ctx.fillRect(a, y, b - a, height);
          if (!z.session) {
            ctx.globalAlpha = z.faded ? 0.22 : 0.55;
            ctx.strokeStyle = z.color;
            ctx.setLineDash(z.faded ? [3, 3] : []);
            ctx.strokeRect(a, y, b - a, height);
          }
          if (b - a > 55) {
            ctx.globalAlpha = 0.8;
            ctx.fillStyle = z.color;
            ctx.font = "10px system-ui";
            ctx.fillText(
              z.label.slice(0, 48),
              a + 5,
              z.session ? 17 : Math.max(12, y + 12),
              b - a - 10,
            );
          }
        }
        ctx.restore();
      }),
  };
  private logical(stamp: number): number {
    const t = this.times,
      n = t.length,
      step = t[n - 1] - t[n - 2] || 60;
    if (stamp >= t[n - 1]) return n - 1 + (stamp - t[n - 1]) / step;
    if (stamp <= t[0]) return (stamp - t[0]) / (t[1] - t[0] || step);
    let lo = 0,
      hi = n - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (t[mid] <= stamp) lo = mid;
      else hi = mid;
    }
    return lo + (stamp - t[lo]) / (t[hi] - t[lo]);
  }
  attached(params: SeriesAttachedParameter<Time>) {
    this.context = params;
  }
  detached() {
    this.context = undefined;
  }
  paneViews() {
    return [this.view];
  }
  setBars(bars: { time: number }[]) {
    this.times = bars.map((b) => b.time);
    this.context?.requestUpdate();
  }
  setZones(zones: Zone[]) {
    this.zones = zones;
    this.context?.requestUpdate();
  }
}
export function chartZones(
  analysis: any,
  layers: string[],
  end: number,
  prediction: any,
): Zone[] {
  const out: Zone[] = [];
  for (const z of analysis?.zones || []) {
    const enabled =
      z.kind === "FVG"
        ? layers.includes("fvg")
        : z.kind === "Order block"
          ? layers.includes("blocks")
          : z.kind === "OTE"
            ? layers.includes("ote")
            : z.kind === "Liquidity"
              ? layers.includes("liquidity")
              : false;
    const start = z.confirmed_at || z.time;
    if (enabled)
      out.push({
        start,
        end: z.invalidated_at || end,
        low: z.low,
        high: z.high,
        label: z.kind + (z.mitigated_at ? " · mitigated" : ""),
        color:
          z.kind === "Order block"
            ? "#b495ee"
            : z.kind === "OTE"
              ? "#d9b86c"
              : z.side > 0
                ? "#48cfac"
                : "#e98798",
        faded: z.status === "invalidated",
      });
    if (layers.includes("breakers") && z.invalidated_at && z.transition_kind)
      out.push({
        start: z.invalidated_at,
        end,
        low: z.low,
        high: z.high,
        label: z.transition_kind + " · historical",
        color: "#d49b64",
        faded: true,
      });
  }
  if (layers.includes("sessions"))
    for (const s of analysis?.session_history || [])
      out.push({
        start: s.start,
        end: s.end,
        label: s.name,
        color: s.name.includes("London") ? "#8eacf2" : "#a9a0e8",
        session: true,
      });
  if (layers.includes("forecast") && prediction?.status === "prediction")
    out.push({
      start: prediction.asof,
      end: prediction.due,
      low: prediction.expected_low,
      high: prediction.expected_high,
      label: `${prediction.direction} · ${(prediction.probability * 100).toFixed(0)}% estimated range`,
      color: "#c4b0ff",
    });
  return out;
}
