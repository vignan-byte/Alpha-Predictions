# Backtesting

Three deterministic strategies: EMA20/50 crossover, first structural break/CHoCH, and RSI14 mean reversion (below 30 long / above 70 short). Signals use candle i−1; entries occur at candle i's open. Only one position is open. Positions are capped at account notional (no leverage). Initial cash is 10,000 account units.

Stop distance is ATR × stop multiplier (default 2). Target distance is stop distance × reward/risk (default 2). Position sizing includes an approximate round-trip cost/slippage allowance. Actual realized loss can exceed the planned amount on gaps.

Adverse slippage applies at entry and exit; per-side transaction cost applies to both notionals. If a gap crosses a stop, exit is at the worse opening price. If both stop and target are inside the same candle, stop is assumed first. Last position is liquidated on the last close. No intrabar path is invented to favor results.

Equity and drawdown mark open positions to market at bar closes, including estimated closing fees. Metrics include trade count, win/loss rates, average win/loss, expectancy, profit factor, net return, maximum drawdown, streaks, monthly P&L and UTC-block P&L. “Session performance” in the API is explicitly UTC 8-hour blocks, not DST-adjusted exchange sessions.

Sharpe uses daily equity returns and sqrt(365), and is null below 21 daily observations. This is a crypto-style annualization convention, not universal across instruments. A null profit factor means no measured negative gross loss denominator, not a fabricated infinite value. No-trade cases have null rates.

UI loads at most 1,000 candles per run and shows actual date coverage. Chosen start/end dates may have less provider history than requested. The current backtest does not model funding, borrow costs, bid/ask historical spreads, market impact, order-book liquidity or forex contract multipliers. It is a research simulator, not an execution simulator validated against a broker.

## Release 2.1 evaluation

Optional spread contributes half the spread per execution side in addition to slippage. Fixed units and fixed-risk sizing both cap exposure at available unlevered notional including entry fee. Wins/losses and Sortino (when enough daily observations exist) accompany existing metrics.

A fixed 60% research / 40% holdout split and three sequential holdout windows report the selected strategy without optimization. Features retain historical warmup; positions and capital restart at each segment. These are chronological walk-forward evaluation windows, not a trained adaptive optimizer. Partial exits remain unsupported.
