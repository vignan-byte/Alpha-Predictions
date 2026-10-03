# Deterministic ICT/SMC definitions

These operational rules make subjective terminology testable. They do not establish that any rule predicts profitable trades.

- Swing high/low: center exceeds the three prior highs/lows and is at least as extreme as the next three. It becomes available only on the third later candle. Events retain the confirmation candle's open time for chart markers and exclusive close time in `confirmed_at` for alert evaluation.
- HH/LH and HL/LL: compare newly confirmed swing with prior swing of the same type.
- BOS: first close through an unbroken confirmed swing high/low, in the existing direction or before a direction is established.
- CHoCH: a break opposite the last structural direction.
- MSS: CHoCH accompanied by same-direction displacement.
- Displacement: candle body > 1.5 ATR.
- Buy-/sell-side liquidity: most recent confirmed swing high/low; equal highs/lows within 0.1 ATR of the prior confirmed swing mark a liquidity pool proxy.
- Sweep / stop-run proxy: wick breaches a confirmed swing, but the close returns inside. This observes price behavior, not actual stop orders.
- FVG: current low > high two candles ago (bullish), or current high < low two candles ago (bearish). Zone is the gap between those prices, known at current close.
- Inverse FVG event: close passes through the far edge of a previously active FVG. The original zone is marked invalidated; an opposite-side event is emitted. It is not treated as a guaranteed support/resistance flip.
- Order block: last opposite-colored candle among the ten bars preceding BOS/CHoCH; full candle range. It is created at the break's confirmation, never backdated.
- Breaker event: closing invalidation of an order block.
- Mitigation event: first subsequent candle touching an active order-block range without closing through its invalidation edge.
- Inducement proxy: sweep in the direction of the existing structural bias. Actual trader intent cannot be inferred.
- Premium/discount: position between latest confirmed low and high, relative to midpoint .5. Values outside 0–1 mean price has left the dealing range.
- Previous-period levels: UTC calendar levels from indicator engine.
- Session high/low: available loaded candles inside the active civil-session window, not an assumption of complete historical coverage.

Chart overlays use filled native rectangles, current directional OTE, historical session shading and structural confirmation markers. See the rendering rules below. Prefix-invariance tests ensure future bars do not change previously emitted signals; zone status may naturally change as later bars invalidate it.

## Release 2.1 visualization

Chart rectangles start at `confirmed_at` (closed-bar knowledge time), and original zones end at confirmed invalidation. Inverse-FVG/breaker transitions are displayed as muted historical areas after that boundary. Order-block touches annotate mitigation. Current directional OTE spans the 62–79% retracement of the latest confirmed swing range; current liquidity bands surround confirmed swing levels by 0.05 ATR. Those current snapshots are not backdated signals.

Native chart primitives recalculate both time and price coordinates on every viewport draw, including future forecast coordinates. FVG/OB/OTE/liquidity rectangles, civil-session shading and validated forecast ranges coexist with the real streaming candlestick series. Structure markers include HH/HL/LH/LL, BOS/CHoCH/MSS and displacement. Backend prefix-invariance and frontend renderer tests guard causal boundaries and pan/zoom behavior.
