# IronClad Trading System

**Project Title**: IronClad  
**Role**: Senior Quantitative Developer (The "Veteran")  
**Objective**: Capital Preservation & Modular Intraday Trading (Nifty 50)

## Overview
IronClad is a robust, modular algorithmic trading system built in Python. It combines "Old School" market wisdom (Price Action, Trend, VPA) with "New School" technology (ML, Python).

## Strategy Logic (The Veteran's Code)
1.  **Trend Alignment**: Inspects the 1-hour trend. If Bullish, we look for buys. If Bearish, we look for sells. (The 50-Year Rule).
2.  **Antigravity Reversion**: Buys when price is 2 Standard Deviations below VWAP in an uptrend (buying the dip).
3.  **VPA Confirmation**: Validates breakouts with volume spikes (1.5x average).
4.  **ML Confidence**: A Random Forest model vets every trade. signal is ignored if confidence < 75%.
5.  **Capital Preservation**:
    - **Kill Switch**: Stops trading if daily loss hits 2%.
    - **ATR Sizing**: Position size adjusts based on volatility.
    - **Time Rules**: No trades after 2:45 PM. Square off at 3:15 PM.

## Directory Structure
```
IronClad/
├── backtest.py            # Main simulation runner
├── requirements.txt       # Dependencies
└── modules/
    ├── data_handler.py    # yfinance wrapper
    ├── risk_manager.py    # Position sizing & risk rules
    └── strategy_engine.py # Core logic (ML + Technicals)
```

## Setup & Usage

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run Backtest**:
    ```bash
    python backtest.py
    ```
    This will:
    - Fetch 60 days of data for Nifty 50 stocks.
    - Train the ML model on the first 30 days.
    - Simulate trading on the last 30 days.
    - Output a trade log and a Mentor's assessment.

## Modular Design
- **DataHandler**: Easily capable of swapping `yfinance` for `KiteConnect` or `SmartAPI`.
- **StrategyEngine**: Logic is isolated. New strategies can be added as new methods.
- **RiskManager**: Centralized risk logic protecting the capital.

---
*"There are old traders and there are bold traders, but there are no old, bold traders."*
