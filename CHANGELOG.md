# Changelog

All notable changes to Trading Lab are documented here.
This project follows a progressive research-driven development approach.

---

## [0.2.0] — 2026-04-16

### Added — AI Agents & Real-Time Pipeline

This session marked the first time the system connected to live market data
and produced real trading theses autonomously.

- **Groq API integration** — connected LLaMA 3.3 70B as the reasoning engine, running on free tier with zero cost
- **`core/macro_agent.py`** — AI agent that reads raw news text and produces a structured `MarketInfoObject` with directional bias, tags, conviction scores and asset scope, via LLM inference
- **`core/sentiment_agent.py`** — AI agent specialized in risk regime detection, identifying risk-on / risk-off conditions, crowding, positioning extremes and geopolitical sentiment from live articles
- **`core/connectors/investinglive.py`** — real-time forex news scraper that fetches and parses articles from investinglive.com, filtering author pages, tag pages and non-editorial content automatically
- **Full live pipeline** — investinglive → Groq LLM → MarketInfoObject → PillarThesisObject working end-to-end in a single call
- **Multi-currency macro scoring** — rebuilt `macro_pillar.py` to score directional bias per currency pair (EURUSD, USDJPY, GBPUSD) rather than USD-only
- **`.env` + Groq key management** — secure API key storage with `.gitignore` protection, never committed to version control

### Validated live on April 16, 2026

> Articles analyzed: 3 real forex articles from investinglive.com  
> Market context: USD under pressure from US-Iran optimism  
> Macro thesis: BEARISH EURUSD — conviction 85, tradable  
> Sentiment thesis: MIXED — risk-on/risk-off contradiction detected correctly

---

## [0.1.0] — 2026-04-09

### Added — 7-Pillar Decision Engine (v1)

First complete version of the modular decision architecture.

- **Core data structures** — `MarketInfoObject`, `PillarThesisObject`, `GlobalThesisObject` with full enum taxonomy
- **`macro_pillar.py`** — macro thesis builder from tagged market info objects
- **`regime_pillar.py`** — price action regime detection (trend, range, compression, breakout)
- **`sentiment_pillar.py`** — sentiment thesis with crowding detection, retail contrarian logic and excess scoring
- **`risk_pillar.py`** — risk posture calculator gated by global thesis
- **`process_strategy_pillar.py`** — strategy selection engine
- **`execution_pillar.py`** — execution permission state machine
- **`global_synthesis.py`** — multi-pillar synthesis with hard veto logic
- **`pipeline_v1.py`** — full pipeline orchestrator
- **`journal_logger.py`** — JSON run journaling
- **`run_registry.py`** — run indexing and registry
- **Streamlit dashboard** — initial multi-asset batch interface
- **Backtesting engine** — custom M15/H1 OHLC backtesting with optimization
- **Full test suite** — one test file per module, all passing

### Architecture principle established

> A trade is only valid when all seven pillars align.  
> The system does not generate signals — it generates structured theses  
> that must survive scrutiny from every analytical dimension.

---

## [0.0.1] — 2026-04-07

### Project initialized

- Personal research project started on a free Sunday afternoon
- Initial objective: explore how far AI could go when applied to trading
- First Python environment, VS Code setup, GitHub repository created
- Core conviction established: profitability requires structure, not just signals

---

*This changelog is maintained manually and updated after each significant development session.*