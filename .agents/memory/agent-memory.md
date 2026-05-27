# Agent Memory

- Write or update `.agents/memory` after meaningful work or substantive design
  discussion, not only during handoffs.
- Record durable decisions, user preferences, architectural direction, gotchas,
  verification results, and future-agent context.
- Keep notes concise and organized by subject. Update existing subject files
  instead of creating dated task diaries.
- Collector gotcha: an empty Binance `aggTrades` response for a 10-second
  window means a quiet interval, not a removed market. Fill zero-volume candles
  from the previous close, and only mark markets removed from exchange info.
- Realtime zero-volume candles are only valid when that symbol's trade
  WebSocket was connected for the whole candle window. If Binance WebSocket
  connects time out, reconnect and wait; do not carry stale closes forward.
