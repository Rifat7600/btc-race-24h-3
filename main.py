#!/usr/bin/env python3
"""Breakout trading bot for make.fun btc-race-24h-20261118-1444.

Strategy: Donchian-style channel breakout, long only.
  - Track the highest high and lowest low over a rolling window of bars.
  - Buy when the close breaks above the recent high by a margin, but only
    when the channel is wide enough to skip tiny-range noise.
  - Exit everything on a trailing stop under the highest close since entry,
    or when the close breaks below the recent low.
  - One position at a time, sized as a fixed fraction of equity.

Protocol: agent-fun/bars-replay/v1, newline-delimited JSON on stdin/stdout.
Pure standard library. Fully deterministic: no clock, no randomness, every
decision is an integer computation on the bars seen so far and the hello
message. Parameters come from the environment with fixed defaults, so a
graded run with no environment set behaves exactly like the defaults.
"""

import json
import os
import sys


def _param(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


CH_LEN = _param("B3_CH", 75)
MARGIN_BPS = _param("B3_MARGIN_BPS", 20)
WIDTH_MIN_BPS = _param("B3_WIDTH_MIN_BPS", 40)
TRAIL_BPS = _param("B3_TRAIL_BPS", 120)
SIZE_PCT = _param("B3_SIZE_PCT", 100)
MAX_SLIP_BPS = _param("B3_MAX_SLIP_BPS", 200)
TREND_LEN = _param("B3_TREND", 0)
STRONG_PCT = _param("B3_STRONG", 0)
TSTOP_BARS = _param("B3_TSTOP", 0)
TSTOP_MIN_BPS = _param("B3_TSTOP_BPS", 30)
MIN_NOTIONAL = 1000000


class BreakoutBot:
    def __init__(self):
        self.symbols = []
        self.quote_scale = 6
        self.price_scale = 5
        self.qty_scale = 8
        self.min_notional = MIN_NOTIONAL
        self.max_weight_bps = 10000
        self.cash = 0
        self.equity = 0
        self.bars = []
        self.pending = set()
        self.counter = 0
        self.trail_high = None
        self.entry_close = None
        self.entry_bar = None

    def on_hello(self, msg):
        self.symbols = [s["symbol"] for s in msg.get("symbols", [])]
        cap = msg.get("capital", {})
        self.quote_scale = int(cap.get("quote_scale", 6))
        self.cash = int(cap.get("quote_units", 0))
        self.equity = self.cash
        fees = msg.get("fees", {})
        self.min_notional = int(fees.get("min_notional_quote_units",
                                         MIN_NOTIONAL))
        caps = msg.get("caps", {})
        self.max_weight_bps = int(caps.get("max_weight_bps", 10000))
        for sym in msg.get("symbols", []):
            self.price_scale = int(sym.get("price_scale", 5))
            self.qty_scale = int(sym.get("qty_scale", 8))
            break

    def on_batch(self, msg):
        for bar in msg.get("bars", []):
            self.bars.append((int(bar["o"]), int(bar["h"]),
                              int(bar["l"]), int(bar["c"])))
        for fill in msg.get("fills", []):
            self.pending.discard(fill.get("client_id", ""))
        account = msg.get("account", {})
        self.cash = int(account.get("cash_quote_units", self.cash))
        self.equity = int(account.get("equity_quote_units", self.equity))
        positions = account.get("positions", [])
        qty = 0
        symbol = self.symbols[0] if self.symbols else "CBBTC"
        for pos in positions:
            if pos.get("symbol") == symbol:
                qty = int(pos.get("qty", 0))
        orders = self._decide(symbol, qty)
        return {"type": "reply", "seq": int(msg.get("seq", 0)),
                "orders": orders}

    def _channel(self):
        """Highest high / lowest low over the CH_LEN bars before the last."""
        window = self.bars[-CH_LEN - 1:-1]
        upper = window[0][1]
        lower = window[0][2]
        for _, high, low, _ in window[1:]:
            if high > upper:
                upper = high
            if low < lower:
                lower = low
        return upper, lower

    def _decide(self, symbol, qty):
        if not self.bars or len(self.bars) <= CH_LEN:
            return []
        close = self.bars[-1][3]
        if qty > 0:
            if self.trail_high is None or close > self.trail_high:
                self.trail_high = close
            if self.entry_close is None:
                self.entry_close = close
                self.entry_bar = len(self.bars)
            stop = self.trail_high * (10000 - TRAIL_BPS) // 10000
            upper, lower = self._channel()
            time_stop = False
            if TSTOP_BARS > 0 and self.entry_bar is not None:
                if len(self.bars) - self.entry_bar >= TSTOP_BARS:
                    if close * 10000 < self.entry_close * (
                            10000 + TSTOP_MIN_BPS):
                        time_stop = True
            if close < stop or close < lower or time_stop:
                if "sell" in [p.split("-")[0] for p in self.pending]:
                    return []
                self.counter += 1
                cid = "sell-%d" % self.counter
                self.pending.add(cid)
                self.trail_high = None
                self.entry_close = None
                self.entry_bar = None
                return [{"side": "sell", "client_id": cid,
                         "symbol": symbol, "qty": str(qty),
                         "max_slippage_bps": MAX_SLIP_BPS}]
            return []
        if self.pending:
            return []
        upper, lower = self._channel()
        mid = (upper + lower) // 2
        if mid <= 0:
            return []
        if (upper - lower) * 10000 < mid * WIDTH_MIN_BPS:
            return []
        if close * 10000 <= upper * (10000 + MARGIN_BPS):
            return []
        if TREND_LEN > 0 and len(self.bars) >= TREND_LEN:
            window = self.bars[-TREND_LEN:]
            sma = sum(b[3] for b in window) // TREND_LEN
            if close <= sma:
                return []
        if STRONG_PCT > 0:
            o, high, low, _ = self.bars[-1]
            if high > low:
                if (close - low) * 100 < (high - low) * STRONG_PCT:
                    return []
        notional = self.equity * SIZE_PCT // 100
        cap = self.equity * self.max_weight_bps // 10000
        if notional > cap:
            notional = cap
        if notional > self.cash:
            notional = self.cash
        if notional < self.min_notional:
            return []
        self.counter += 1
        cid = "buy-%d" % self.counter
        self.pending.add(cid)
        self.trail_high = close
        return [{"side": "buy", "client_id": cid, "symbol": symbol,
                 "notional_quote_units": str(notional),
                 "max_slippage_bps": MAX_SLIP_BPS}]


def main():
    bot = BreakoutBot()
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        kind = msg.get("type")
        if kind == "hello":
            bot.on_hello(msg)
        elif kind == "batch":
            reply = bot.on_batch(msg)
            out.write(json.dumps(reply, separators=(",", ":")) + "\n")
            out.flush()
        elif kind == "done":
            break


if __name__ == "__main__":
    main()
