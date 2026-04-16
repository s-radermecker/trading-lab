# Trading Lab

A modular market research and decision engine built to experiment with trading ideas and progressively integrate the seven pillars of trading into a unified architecture — now powered by real-time AI agents analyzing live market news.

## Project origin

Trading Lab started as a personal research project driven by my passion for financial markets. My initial objective was not to build a finished trading bot, but to create a modular laboratory where I could experiment with indicators, decisions and market theses, observe their impact on charts, and search for better combinations through backtesting and optimization.

Developed seriously on my own time, the project progressively evolved from a technical research base into a broader decision architecture — and eventually into a live AI-powered analysis pipeline.

## Core idea

Through my past experience in financial markets, I progressively came to the conclusion that durable profitability and outperformance are not the product of isolated technical signals alone. In my view, they result from the coherent combination of seven essential factors that should not be neglected in any serious and sustainable market approach.

Trading Lab is the continuation of that conviction: an attempt to translate these seven pillars into a structured computational framework for research, decision-making, and eventually more disciplined and automatable execution.

## The seven pillars behind the project

1. **Macroeconomics and fundamentals**  
   Understanding the economic, monetary and geopolitical context driving market behavior.

2. **Price action and market structure**  
   Reading trends, ranges, breakouts, structure quality and market states directly from price behavior.

3. **Market sentiment**  
   Evaluating positioning, consensus, excess, fear, euphoria and broader market mood.

4. **Risk management**  
   Controlling exposure, sizing, concentration, correlation and overall system survival.

5. **Psychology**  
   Recognizing that execution quality depends on discipline, consistency and the reduction of emotional interference.

6. **Process and strategy**  
   Turning market ideas into structured plans with explicit entry, invalidation and no-trade conditions.

7. **Tools and execution**  
   Using the right infrastructure, data, workflows and execution logic to act in real market conditions.

## Current capabilities

The project currently includes three complementary layers:

### 1. Historical research base
- Backtesting on personal chart and data files
- Experimentation with multiple technical strategies
- Parameter optimization and combination search
- Early grading and selection logic to compare setups
- Local research workflows without depending on external platforms

### 2. Modular decision engine (v1)
- Standardized `MarketInfoObject`, `PillarThesisObject` and `GlobalThesisObject`
- `macro_pillar.py` — macro scoring with multi-currency pair logic
- `regime_pillar.py` — price action regime detection
- `sentiment_pillar.py` — sentiment scoring with crowding and excess detection
- `global_synthesis.py` — combines all pillars into one global thesis
- `risk_pillar.py` — risk posture calculator
- `process_strategy_pillar.py` — strategy selection engine
- `execution_pillar.py` — execution permission logic
- `pipeline_v1.py` — full pipeline orchestrator
- JSON journaling of runs and run registry

### 3. Real-time AI agents (new)
- `macro_agent.py` — reads raw news text, produces structured macro `MarketInfoObject` via LLM
- `sentiment_agent.py` — reads raw news text, detects risk regime and sentiment via LLM
- `connectors/investinglive.py` — real-time forex news scraper
- Full pipeline: **live news → Groq LLM → structured thesis → trade signal**

### Live example output
