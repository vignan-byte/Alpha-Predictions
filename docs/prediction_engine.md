# Prediction engine

Horizon mapping:

| Label | Model timeframe | Future bars |
|---|---|---:|
| 5 minutes | 5m | 1 |
| 15 minutes | 5m | 3 |
| 30 minutes | 5m | 6 |
| 1 hour | 5m | 12 |
| Next civil session | 1h | Session-specific window |
| Next day | 1d | 1 |
| Next 7 days | 1d | 7 |
| Next 30 days | 1d | 30 |
| Next 12 months | 1d | 365 |

These are rolling horizons from the last closed candle, not “until today's close” or the current calendar week's/month's end. Gapped target windows are excluded; long forex horizons may consequently lack sufficient contiguous samples. Next-session targets use a distinct model identity and the next civil-session window; they never relabel a fixed-hour forecast. Missing or rejected models return unavailable.

Class label uses future close return relative to ±0.15 current ATR/close: Bearish, Neutral, Bullish. Future-high/low targets use only the following H candles, excluding the origin candle. Separate regressors estimate return, high excursion, low excursion and future return standard deviation. Forecast ranges are estimates of extrema, **not** calibrated prediction intervals or exact future prices.

Inference uses a promoted source/instrument/timeframe/horizon-specific model. Calibrated probabilities sum to one. The UI displays maximum probability and its class; the API retains all three probabilities. If no promoted model exists or the feed is stale, an explicit unavailable response is returned. No heuristic percentage fills the gap.

Conditional bull/base/bear scenarios use observed support/resistance and ATR scaled by square-root horizon. Their conditions and absence of probabilities are explicit. Observed-factor explanations list actual EMA order, RSI and recent detected structure events. They are context summaries, not claims of causal feature attribution. Validation permutation importance is stored separately in the model registry.

Predictions are stored once per immutable identity. Outcomes settle only when a complete matching source/timeframe target window is available. Directional correctness, realized extrema and absolute return error are retained. Displayed forward metrics require at least 30 non-overlapping forecast windows. Model test performance remains separate from forward performance and strategy P&L.
