# Trading Lab

A modular market research and decision engine built to experiment with trading ideas and progressively integrate the seven pillars of trading into a unified architecture.

## Project origin

Trading Lab started as a personal research project driven by my passion for financial markets. My initial objective was not to build a finished trading bot, but to create a modular laboratory where I could experiment with indicators, decisions and market theses, observe their impact on charts, and search for better combinations through backtesting and optimization.

Developed seriously on my own time, the project progressively evolved from a technical research base into a broader decision architecture.

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

The project currently includes two complementary layers:

### 1. Historical Trading Lab / research base
- backtesting on personal chart/data files
- experimentation with multiple technical strategies
- parameter optimization and combination search
- early grading / selection logic to compare setups
- local research workflows without depending entirely on external platforms

### 2. New modular decision engine (v1)
- standardized `MarketInfoObject`, `PillarThesisObject` and `GlobalThesisObject`
- `macro_pillar.py`
- `regime_pillar.py`
- `sentiment_pillar.py`
- `global_synthesis.py`
- `risk_pillar.py`
- `process_strategy_pillar.py`
- `execution_pillar.py`
- `pipeline_v1.py`
- JSON journaling of runs
- run registry and run viewer

## Current architecture

The current architecture is organized around a modular pipeline:

1. Market information is normalized into `MarketInfoObject`
2. Pillars generate structured theses
3. A global synthesis aggregates the main context layers
4. A risk layer gates exposure
5. A process layer transforms the thesis into an actionable plan
6. An execution layer decides whether the setup is realistically executable
7. Each run can be journaled and indexed

This architecture is designed so that future data connectors can be added without rewriting the decision logic itself.

## What I learned through this project

Beyond markets themselves, Trading Lab has been a major learning framework for me. Through this project, I developed or strengthened skills in:

- AI-assisted project building
- prompting and iterative collaboration with AI systems
- VS Code and terminal workflows
- Python project structuring
- modular reasoning and system design
- backtesting and research logic
- translating practical market intuition into a more formal architecture

## Roadmap

The next major steps include:

- improving the internal quality of each pillar
- refining scoring, conflicts and trigger logic
- connecting the system to selected external data sources
- extending journaling and run analysis
- progressively integrating more of the seven pillars into the final lab
- moving toward a more complete multi-pillar research and execution framework

## Disclaimer

This repository is a research project in active development. It does not claim proven profitability, institutional-grade execution, or live deployment readiness. Its purpose is to build a structured market research and decision framework progressively and seriously.
