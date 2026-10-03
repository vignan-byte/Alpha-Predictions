# Sessions

Civil windows: Asian 09:00–18:00 Asia/Tokyo; London 08:00–17:00 Europe/London; New York 08:00–17:00 America/New_York. These are documented analytical conventions, not universal exchange hours. Weekend windows are skipped. Regional holidays are not modeled. Crypto trades continuously even outside these windows.

Python zoneinfo and tzdata resolve daylight-saving changes from IANA data, including weeks where London and New York transitions differ. All timestamps are aware. Default display is Asia/Kolkata. Settings can change the display timezone without changing UTC candle calculations.

API provides active sessions, nearest next opening, start/end, seconds remaining and overlap. High/low/range are calculated only over candles available in the request's loaded history. A chart timeframe that is coarser than the session may not provide useful exact session extrema. The feature engine's UTC eight-hour blocks are separate, explicitly defined statistical context.

A separately trained next-civil-session target is implemented. Without a validated session model the forecast remains unavailable. No fixed-hour return is presented as a learned session forecast.

## Release 2.1 historical ranges and targets

Historical windows include open/high/low/close/range/return and coverage flags using fully contained closed bars. London/NY overlap is measured separately. A sweep is the first later closed bar (within 12 hours after a completed session) that breaches its high/low and closes back through the level; no incomplete-session final range is used. The next-session ML target is independently trained on hourly data with a four-day purge. Session shading is descriptive, not a forward signal.
