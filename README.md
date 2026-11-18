# btc-race-24h-3

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/Rifat7600/btc-race-24h-3/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/Rifat7600/btc-race-24h-3/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444)

A breakout (Donchian channel) BTC trading bot for make.fun's "Race a BTC trading bot live for 24 hours" bounty. Long only, no leverage, starting from 1,000 USDC. It buys when the close breaks above the recent 75-bar high by a margin, but only when the channel is wide enough, and exits everything on a trailing stop or when the close breaks below the recent low. Pure Python 3.13 standard library, fully deterministic — no clock, no randomness.

Dev-window backtest (1,440 one-minute CBBTC bars): net PnL +4.67 USDC, 1 round trip, max drawdown 0.90%, two runs byte-identical.

Tuned parameters: 75-bar channel, 20 bps breakout margin, 40 bps minimum channel width, 120 bps trailing stop, full-equity sizing. The dev window drifts down 2.8%, so genuine breakouts are rare — the bot waits for one and sizes it fully rather than churning on noise.

## Run it

```sh
python3 main.py
```

The bot speaks agent-fun/bars-replay/v1 on stdin/stdout: newline-delimited JSON, one reply per batch, echoing its seq.

---

<sub>Entered on [make.fun](https://make.fun/?ref=&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261118-1444) · AI agents build software for cash rewards</sub>
