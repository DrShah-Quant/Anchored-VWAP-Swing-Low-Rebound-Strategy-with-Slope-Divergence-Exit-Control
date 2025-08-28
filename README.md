# 📈 Anchored VWAP Swing-Low Rebound Strategy with Slope-Divergence Exit Control

## 📝 Strategy Description

This strategy focuses on **buying rebound opportunities from swing-lows** when the price confirms strength **above Anchored VWAP**, while exits are guided by **slope-divergence detection** on swing-highs to prevent premature or late liquidation.

### 🔹 Steps Followed:

1. **Trend & Swing Detection**

   * Identifies uptrend/downtrend sequences using rolling price windows.
   * Confirms **macro swing-lows & highs** for structural validation.
   * Uptrend sequence: `Low → High → Low → High → Low`

2. **Anchored VWAP Validation**

   * Formula:

     ```
     VWAP = (Σ(Price × Volume)) / (Σ Volume)
     ```
   * Price must close **above Anchored VWAP** to validate bullish rebound.

3. **Buy Conditions**

   * Price dips below the **swing-low band** (lowest support level).
   * Rebounds above Anchored VWAP with confirmation.
   * Slope rule:

     * Slope of latest swing-lows must be rising (`slope2 > 0.8 × slope1`).
   * Position sizing:

     * Capital allocated **20–30%** depending on buy price vs. current market price.
   * Stop-loss anchored to **most recent swing low**.

4. **Sell Conditions**

   * **Slope divergence** across swing-highs (`slope2 < 0.7 × slope1`).
   * OR sudden weakness in swing-lows (≥2 drops).
   * OR profit exceeds **8% with divergence confirmation**.
   * Ensures exit before trend exhaustion.

---

## 📊 Trading Interpretations

* **Rebound from Swing-Low + Anchored VWAP Confirmation** → Strong institutional entry point.
* **Slope Rising at Swing-Lows** → Confirms healthy uptrend continuation.
* **Slope Divergence at Swing-Highs** → Early signal of weakening momentum.
* **Risk-Managed Scaling** → 20–30% allocation prevents overexposure.

---

## 📦 Libraries Used

* **AlgoAPI** – order management, backtesting, event handling
* **AlgoAPIUtil** – trade/order utilities
* **AlgoAPI\_Backtest** – backtest handler
* **datetime** & **timedelta** – slope interval & timestamp calculations

