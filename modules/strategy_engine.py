import pandas as pd

import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.impute import SimpleImputer
import warnings
from modules.db_manager import DatabaseManager

# Suppress pandas setting with copy warnings
pd.options.mode.chained_assignment = None
warnings.filterwarnings("ignore")

class StrategyEngine:
    """
    The Brains of IronClad.
    Combines Technical Analysis (Old School) with Machine Learning (New School).
    """
    
    def __init__(self):
        self.models = {} # Dictionary to hold models per ticker
        self.scalers = {} # Dictionary to hold scalers per ticker (Critical for NN)
        self.min_training_samples = 100
        self.db = DatabaseManager()
        from modules.system_logger import logger # Lazy import to avoid circular dependency if any
        self.logger = logger
        
    def add_indicators(self, df: pd.DataFrame):
        """Adds technical indicators to the dataframe using pure pandas."""
        if df.empty:
            return df
            
        # Helper: Simple Moving Average
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        df['SMA_200'] = df['close'].rolling(window=200).mean()
        
        # Helper: RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Helper: ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['ATR'] = true_range.rolling(window=14).mean()
        
        # FILL ATR NaNs to prevent Supertrend from failing
        df['ATR'] = df['ATR'].bfill().ffill()
        
        # Helper: VWAP
        v = df['volume'].values
        tp = (df['high'] + df['low'] + df['close']) / 3
        df['VWAP'] = (tp * v).cumsum() / v.cumsum()
            
        # Reversion Bands (VWAP +/- 2 SD)
        df['Dist_VWAP'] = df['close'] - df['VWAP']
        df['Dist_VWAP_Std'] = df['Dist_VWAP'].rolling(20).std()
        df['Z_Score_VWAP'] = df['Dist_VWAP'] / df['Dist_VWAP_Std']

        # Supertrend (10, 3)
        df = self.add_supertrend(df, period=10, multiplier=3)
        
        # ADX (Trend Strength)
        df = self.add_adx(df, period=14)
        
        return df

    def add_adx(self, df, period=14):
        """
        Calculates ADX (Average Directional Index).
        """
        if len(df) < period + 1:
            df['ADX'] = 0
            return df
            
        high = df['high']
        low = df['low']
        close = df['close']
        
        # 1. Calculate TR (already done in ATR but let's be self-contained or reuse)
        # Reuse logic for speed if possible, but safe to recalc
        tr0 = abs(high - low)
        tr1 = abs(high - close.shift())
        tr2 = abs(low - close.shift())
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
        
        # 2. Directional Movement
        up_move = high - high.shift()
        down_move = low.shift() - low
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        # 3. Smooth (Wilder's Smoothing)
        # alpha = 1/period
        tr_smooth = pd.Series(tr).ewm(alpha=1/period, min_periods=period).mean()
        plus_dm_smooth = pd.Series(plus_dm).ewm(alpha=1/period, min_periods=period).mean()
        minus_dm_smooth = pd.Series(minus_dm).ewm(alpha=1/period, min_periods=period).mean()
        
        # 4. DI
        plus_di = 100 * (plus_dm_smooth / tr_smooth)
        minus_di = 100 * (minus_dm_smooth / tr_smooth)
        
        # 5. DX and ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(alpha=1/period, min_periods=period).mean()
        
        df['ADX'] = adx
        df['Plus_DI'] = plus_di
        df['Minus_DI'] = minus_di
        
        return df

    def add_supertrend(self, df, period=10, multiplier=3):
        """
        Calculates Supertrend Indicator.
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Helper: Basic Bands
        # ATR is already in df['ATR']
        
        # Calculate N-period ATR if not present or different (using existing ATR for now)
        # Force re-calc ATR for specific period if needed? 
        # For simplicity, we assume df['ATR'] is correct length or Close enough
        # But 'ATR' in add_indicators is rolling 14. Supertrend usually uses 10.
        # Let's simple re-calc 'tr' for safety
        
        # True Range
        tr0 = abs(high - low)
        tr1 = abs(high - close.shift())
        tr2 = abs(low - close.shift())
        tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        atr = atr.bfill().ffill()
        
        hl2 = (high + low) / 2
        basic_upper = hl2 + (multiplier * atr)
        basic_lower = hl2 - (multiplier * atr)
        
        # Numpy arrays for fast looping
        basic_upper = basic_upper.values
        basic_lower = basic_lower.values
        close = close.values
        final_upper = np.zeros(len(df))
        final_lower = np.zeros(len(df))
        supertrend = np.zeros(len(df))
        trend = np.zeros(len(df)) # 1 Bullish, -1 Bearish
        
        # Initialize
        final_upper[0] = basic_upper[0]
        final_lower[0] = basic_lower[0]
        
        for i in range(1, len(df)):
            # Final Upper
            if basic_upper[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
                final_upper[i] = basic_upper[i]
            else:
                final_upper[i] = final_upper[i-1]
                
            # Final Lower
            if basic_lower[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
                final_lower[i] = basic_lower[i]
            else:
                final_lower[i] = final_lower[i-1]
                
            # Trend
            prev_trend = trend[i-1] if trend[i-1] != 0 else 1
            
            if prev_trend == 1:
                if close[i] < final_lower[i]:
                    trend[i] = -1
                else:
                    trend[i] = 1
            else:
                if close[i] > final_upper[i]:
                    trend[i] = 1
                else:
                    trend[i] = -1
                    
            if trend[i] == 1:
                supertrend[i] = final_lower[i]
            else:
                supertrend[i] = final_upper[i]
                
        df['Supertrend'] = supertrend
        df['Supertrend_Signal'] = trend # 1 or -1
        return df

    def prepare_ml_data(self, df: pd.DataFrame):
        """Creates features and targets for ML."""
        df = self.add_indicators(df)
        df.dropna(inplace=True)
        
        # Features
        feature_cols = ['RSI', 'Dist_VWAP', 'Z_Score_VWAP', 'volume']
        
        # Target: 1 if next 5 candles return > 0.1%, else 0 (Simplistic binary classification)
        df['Return_5'] = df['close'].shift(-5) / df['close'] - 1
        df['Target'] = (df['Return_5'] > 0.001).astype(int)
        
        return df, feature_cols

    def train_model(self, ticker: str, df: pd.DataFrame):
        """
        Trains a Multi-Layer Perceptron (Neural Network) for the specific ticker.
        """
        data, features = self.prepare_ml_data(df.copy())
        
        if len(data) < self.min_training_samples:
            self.models[ticker] = None
            return

        X = data[features]
        y = data['Target']
        
        # Handle Inf/Nan
        X = X.replace([np.inf, -np.inf], np.nan).dropna()
        y = y.loc[X.index] # Align y
        
        if len(X) < self.min_training_samples:
            self.models[ticker] = None
            return

        # --- NEURAL NETWORK PIPELINE ---
        
        # 1. Scale Data (Essential for NNs to converge)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        self.scalers[ticker] = scaler # Save scaler for inference
        
        # 2. Define Architecture
        # Hidden Layer 1: 100 Neurons (Feature Extraction)
        # Hidden Layer 2: 50 Neurons (Pattern Synthesis)
        # Activation: ReLU (Biological Standard)
        # Solver: Adam (Adaptive Learning Rate)
        mlp = MLPClassifier(
            hidden_layer_sizes=(100, 50), 
            activation='relu', 
            solver='adam', 
            alpha=0.0001, # L2 Regularization
            batch_size='auto', 
            learning_rate='adaptive', 
            learning_rate_init=0.001, 
            max_iter=500, 
            random_state=42,
            early_stopping=True, # Prevent Overfitting
            validation_fraction=0.1,
            n_iter_no_change=10
        )
        
        try:
             mlp.fit(X_scaled, y)
             self.models[ticker] = mlp
             # self.logger.log(f"[{ticker}] Neural Network Trained. Loss: {mlp.loss_:.4f}", "INFO")
        except Exception as e:
             self.logger.log(f"NN Training failed for {ticker}: {e}", "ERROR")
             self.models[ticker] = None

    def get_ml_confidence(self, ticker: str, current_features: pd.DataFrame):
        """Returns the probability of the positive class (Buy)."""
        model = self.models.get(ticker)
        if model is None:
            return 0.5 # Neutral
            
        try:
            # Scale features using the saved scaler for this ticker
            scaler = self.scalers.get(ticker)
            if scaler is None:
                return 0.5
                
            features_scaled = scaler.transform(current_features)
            
            # Predict
            prob = model.predict_proba(features_scaled)[:, 1] # Probability of class 1
            return prob[0]
        except:
            return 0.5

    def check_macro_trend(self, df_1d: pd.DataFrame):
        """
        Calculates the 200-day EMA on Daily data.
        Returns: 'BULLISH' if Close > EMA200, 'BEARISH' if Close < EMA200
        """
        if df_1d.empty or len(df_1d) < 200:
            return 'NEUTRAL' # Not enough data
            
        ema_200 = df_1d['close'].ewm(span=200, adjust=False).mean().iloc[-1]
        current_close = df_1d['close'].iloc[-1]
        
        if current_close > ema_200:
            return 'BULLISH'
        else:
            return 'BEARISH'

    def analyze_1h_trend(self, df_1h: pd.DataFrame):
        """
        The 50-Year Rule: Check higher timeframe structure.
        Returns: 'BULLISH', 'BEARISH', or 'SIDEWAYS'
        """
        if df_1h.empty:
            return 'SIDEWAYS'
            
        last = df_1h.iloc[-1]
        
        # Simple logical Trend definition
        if last['close'] > last['SMA_50']:
            return 'BULLISH'
        elif last['close'] < last['SMA_50']:
            return 'BEARISH'
        return 'SIDEWAYS'

    # --- PARAMETER MUTATIONS (The Arena) ---
    def strategy_rsi(self, df_5m, period=14, low_threshold=30, high_threshold=70):
        """
        Pure RSI Strategy with variable parameters.
        """
        # Calculate specific RSI if needed (default in add_indicators is 14)
        rsi_col = 'RSI'
        if period != 14:
            # Custom calc on the fly
            delta = df_5m['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi_values = 100 - (100 / (1 + rs))
            current = rsi_values.iloc[-1]
        else:
            current = df_5m['RSI'].iloc[-1]
            
        if current < low_threshold:
            return "BUY"
        elif current > high_threshold:
            return "SELL"
        return None

    def strategy_reversion_antigravity(self, ticker, df_5m, trend_1h, latest):
        """Original IronClad Strategy: VWAP Reversion + VPA."""
        signal = None
        
        # --- Logic 1: The Antigravity Reversion (Pullback in Trend) ---
        # Buy Dip: 1H Bullish + 5m Oversold (Z-Score < -2)
        if trend_1h == 'BULLISH':
            if latest['Z_Score_VWAP'] < -2:
                 signal = "BUY"
                 
        # Sell Rally: 1H Bearish + 5m Overbought (Z-Score > 2)
        elif trend_1h == 'BEARISH':
            if latest['Z_Score_VWAP'] > 2:
                signal = "SELL"
        
        # --- Logic 2: VPA Breakout (Confirmation) ---
        if signal is None:
            vol_avg = df_5m['volume'].rolling(20).mean().iloc[-1]
            if latest['volume'] > 1.5 * vol_avg: # 1.5x Volume Spike
                if trend_1h == 'BULLISH' and latest['close'] > latest['open']:
                     signal = "BUY"
                elif trend_1h == 'BEARISH' and latest['close'] < latest['open']:
                     signal = "SELL"
        return signal

    def strategy_orb(self, df_5m):
        """
        Opening Range Breakout (15 minutes).
        Trades the breakout of the first 15 mins (3 candles).
        """
        current_time = df_5m.index[-1]
        
        # Get start of the day
        day_start = current_time.replace(hour=9, minute=15, second=0, microsecond=0)
        
        # Get today's data
        df_today = df_5m[df_5m.index >= day_start]
        
        # We need at least 3 completed candles (15 mins) to define range
        # And we trade AFTER the range is formed (from 9:30 onwards)
        if len(df_today) < 4: 
            return None
            
        # Define Range (First 3 candles: 9:15, 9:20, 9:25)
        # Candles are indexed by start time? usually
        # 0: 9:15-9:20
        # 1: 9:20-9:25
        # 2: 9:25-9:30
        range_candles = df_today.iloc[:3]
        orb_high = range_candles['high'].max()
        orb_low = range_candles['low'].min()
        
        latest = df_5m.iloc[-1]
        
        # Breakout Logic
        if latest['close'] > orb_high:
            return "BUY"
        elif latest['close'] < orb_low:
            return "SELL"
            
        return None

    def strategy_supertrend(self, latest):
        """
        Pure Supertrend Following.
        """
        trend = latest['Supertrend_Signal']
        if trend == 1:
            return "BUY"
        elif trend == -1:
            return "SELL"
        return None

    def strategy_ma_crossover(self, df_5m):
        """
        SMA 20 vs SMA 50 Crossover.
        """
        if len(df_5m) < 2: return None
        
        curr = df_5m.iloc[-1]
        prev = df_5m.iloc[-2]
        
        # Crossover Up
        if prev['SMA_20'] <= prev['SMA_50'] and curr['SMA_20'] > curr['SMA_50']:
            return "BUY"
        # Crossover Down
        elif prev['SMA_20'] >= prev['SMA_50'] and curr['SMA_20'] < curr['SMA_50']:
            return "SELL"
            
        return None

    # --- NEW STRATEGIES (MACD & Bollinger) ---
    def strategy_macd(self, df_5m):
        """
        MACD Momentum Strategy.
        Buy when MACD Line crosses above Signal Line.
        """
        # Calculate MACD (12, 26, 9)
        exp1 = df_5m['close'].ewm(span=12, adjust=False).mean()
        exp2 = df_5m['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=9, adjust=False).mean()
        
        # Check Crossover
        if len(macd) < 2: return None
        
        curr_macd = macd.iloc[-1]
        curr_sig = signal_line.iloc[-1]
        prev_macd = macd.iloc[-2]
        prev_sig = signal_line.iloc[-2]
        
        # Bullish Crossover
        if prev_macd <= prev_sig and curr_macd > curr_sig:
             return "BUY"
        # Bearish Crossover
        elif prev_macd >= prev_sig and curr_macd < curr_sig:
             return "SELL"
             
        return None

    def strategy_bollinger(self, df_5m):
        """
        Bollinger Band Squeeze/Breakout.
        Buy if price closes above Upper Band.
        """
        # Calculate Bands (20, 2)
        sma = df_5m['close'].rolling(window=20).mean()
        std = df_5m['close'].rolling(window=20).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        
        if len(upper) < 1: return None
        
        close = df_5m['close'].iloc[-1]
        
        if close > upper.iloc[-1]:
            return "BUY"
        elif close < lower.iloc[-1]:
            return "SELL"
            
        return None
        
    def strategy_candlestick(self, df_5m):
        """
        Candlestick Pattern Recognition (Hammer & Shooting Star).
        """
        if len(df_5m) < 3: return None
        
        last = df_5m.iloc[-1]
        
        # Candle Parts
        body = abs(last['close'] - last['open'])
        upper_wick = last['high'] - max(last['close'], last['open'])
        lower_wick = min(last['close'], last['open']) - last['low']
        
        # 1. HAMMER (Bullish Reversal)
        # - Small body
        # - Long lower wick (at least 2x body)
        # - Small upper wick
        if lower_wick > (2 * body) and upper_wick < body:
             # Confirmation: Previous trend should be down?
             # For now, raw pattern signal
             return "BUY"
             
        # 2. SHOOTING STAR (Bearish Reversal)
        # - Small body
        # - Long upper wick (at least 2x body)
        # - Small lower wick
        elif upper_wick > (2 * body) and lower_wick < body:
             return "SELL"
             
        return None
        
    def check_sector_correlation(self, ticker: str, signal: str, sector_data: dict, df_5m: pd.DataFrame):
        """
        Phase 4: Sector Correlation.
        Returns False if trade should be VETOED.
        """
        # 1. Define Map
        # In a real app, this should be in a config or DB
        SECTOR_MAP = {
            'HDFCBANK.NS': '^NSEBANK',
            'ICICIBANK.NS': '^NSEBANK',
            'SBIN.NS': '^NSEBANK',
            'AXISBANK.NS': '^NSEBANK',
            'KOTAKBANK.NS': '^NSEBANK',
            'INDUSINDBK.NS': '^NSEBANK',
            # Add IT sector if we had ^CNXIT
        }
        
        sector_ticker = SECTOR_MAP.get(ticker)
        
        # Also Check General Market (Nifty 50) for all stocks
        # If Nifty is crashing (-1% intraday), Buying anything is risky
        nifty_data = sector_data.get('^NSEI')
        if nifty_data is not None and not nifty_data.empty:
             nifty_change = (nifty_data['close'].iloc[-1] - nifty_data['open'].iloc[0]) / nifty_data['open'].iloc[0]
             # Hard Crash Veto (> 1% drop)
             if nifty_change < -0.01 and signal == 'BUY':
                 print(f"[{ticker}] BUY Vetoed: Market Crash (^NSEI down {nifty_change*100:.2f}%)")
                 return False
        
        if not sector_ticker:
            return True # No specific sector to check
            
        sector_df = sector_data.get(sector_ticker)
        if sector_df is None or sector_df.empty:
            return True # No data, proceed
            
        # Check Sector Trend (Simple 5m slope or stored ADX?)
        # Let's compute simple correlation of direction
        sec_open = sector_df['open'].iloc[-1]
        sec_close = sector_df['close'].iloc[-1]
        
        # If Signal is BUY, Sector should not be RED candle? 
        # Or better: Sector should be above its VWAP?
        # Let's stick to the Plan: "If ^NSEBANK is -1%, VETO"
        
        # Calculate Sector Intraday Change
        # Assuming df covers today, let's look at last few candles
        # Last 30 mins change?
        if len(sector_df) < 6: return True
        
        recent_change = (sector_df['close'].iloc[-1] - sector_df['close'].iloc[-6]) / sector_df['close'].iloc[-6]
        
        if signal == 'BUY':
            if recent_change < -0.002: # Sector down 0.2% in last 30 mins (Momentum is down)
                print(f"[{ticker}] BUY Vetoed: Sector {sector_ticker} Falling ({recent_change*100:.2f}%)")
                return False
        elif signal == 'SELL':
            if recent_change > 0.002: # Sector up 0.2% in last 30 mins
                print(f"[{ticker}] SELL Vetoed: Sector {sector_ticker} Rising ({recent_change*100:.2f}%)")
                return False
                
        return True

    def generate_signal(self, ticker: str, df_5m: pd.DataFrame, df_1h: pd.DataFrame, df_1d: pd.DataFrame = None, strategy_type='composite', sector_data=None, sentiment_score=0.0):
        """
        Core Decision Logic.
        Supported Strategies: 'composite', 'orb', 'supertrend', 'ma_crossover', 'macd', 'bollinger', 'candlestick_pattern'
        """
        if df_5m.empty or len(df_5m) < 20:
            return None, 0

        # Ensure indicators
        df_5m = self.add_indicators(df_5m)
        df_1h = self.add_indicators(df_1h) 
        
        latest = df_5m.iloc[-1]
        trend_1h = self.analyze_1h_trend(df_1h)
        atr = latest['ATR']
        
        signal = None
        
        if strategy_type == 'composite':
            signal = self.strategy_reversion_antigravity(ticker, df_5m, trend_1h, latest)
            
        elif strategy_type == 'orb':
            signal = self.strategy_orb(df_5m)
            
        elif strategy_type == 'supertrend':
            signal = self.strategy_supertrend(latest)
            
        elif strategy_type == 'ma_crossover':
            signal = self.strategy_ma_crossover(df_5m)
            
        elif strategy_type == 'macd':
            signal = self.strategy_macd(df_5m)
            
        elif strategy_type == 'bollinger':
            signal = self.strategy_bollinger(df_5m)
            
        elif strategy_type == 'candlestick_pattern':
            signal = self.strategy_candlestick(df_5m)
            
        # --- SHADOW STRATEGIES ---
        elif strategy_type == 'rsi_14':
            signal = self.strategy_rsi(df_5m, period=14, low_threshold=30, high_threshold=70)
        elif strategy_type == 'rsi_9_aggressive':
            signal = self.strategy_rsi(df_5m, period=9, low_threshold=25, high_threshold=75)
        elif strategy_type == 'rsi_21_conservative':
            signal = self.strategy_rsi(df_5m, period=21, low_threshold=30, high_threshold=70)

        # --- PHASE 5: SENTIMENT FILTER (The "Ears") ---
        # If Sentiment is Very Negative, VETO BUY.
        # If Sentiment is Very Positive, VETO SELL (optional, but let's be safe).
        if sentiment_score < -0.2 and signal == 'BUY':
             self.logger.log(f"[{ticker}] BUY Vetoed: Negative Sentiment ({sentiment_score:.2f})", "VETO")
             signal = None
        elif sentiment_score > 0.2 and signal == 'SELL':
             # print(f"[{ticker}] SELL Vetoed: Positive Sentiment ({sentiment_score:.2f})")
             # Actually, for Sell signals we might not want to be as strict unless Shorting.
             # But if we hold a stock and it says SELL but sentiment is super high, maybe hold?
             # For now, let's keep it symmetric.
             signal = None
             
        if not signal:
             return None, 0

        # --- PHASE 3: MACRO TREND FILTER (The "Brain") ---
        # If the Daily Trend is BEARISH, we forbid BUY signals (Long-only bot)
        if df_1d is not None and not df_1d.empty:
            macro_trend = self.check_macro_trend(df_1d)
            if macro_trend == 'BEARISH' and signal == 'BUY':
                self.logger.log(f"[{ticker}] Trade filtered by MACRO TREND (Daily Bearish)", "VETO")
                signal = None
            elif macro_trend == 'BULLISH' and signal == 'SELL':
                pass

        # --- PHASE 4: MARKET REGIME FILTER (Context Awareness) ---
        if signal:
            current_adx = df_5m['ADX'].iloc[-1]
            regime = 'NEUTRAL'
            if current_adx > 25: regime = 'TRENDING'
            elif current_adx < 20: regime = 'RANGING'
            
            if regime == 'TRENDING':
                if strategy_type in ['bollinger', 'rsi_14', 'rsi_9_aggressive']:
                    p_di = df_5m['Plus_DI'].iloc[-1]
                    m_di = df_5m['Minus_DI'].iloc[-1]
                    trend_dir = "UP" if p_di > m_di else "DOWN"
                    if trend_dir == "UP" and signal == "SELL":
                        self.logger.log(f"[{ticker}] SELL Signal vetoed by Strong Bull Trend (ADX {current_adx:.1f})", "VETO")
                        signal = None
                    elif trend_dir == "DOWN" and signal == "BUY":
                        self.logger.log(f"[{ticker}] BUY Signal vetoed by Strong Bear Trend (ADX {current_adx:.1f})", "VETO")
                        signal = None
                        
            elif regime == 'RANGING':
                if strategy_type in ['supertrend', 'macd', 'ma_crossover']:
                    # Trend following dies in chop.
                    self.logger.log(f"[{ticker}] Trend Strategy ({strategy_type}) filtered by CHOPPY Market (ADX {current_adx:.1f})", "VETO")
                    signal = None

        # --- PHASE 4.2: SECTOR CORRELATION FILTER ---
        if signal and sector_data:
            allowed = self.check_sector_correlation(ticker, signal, sector_data, df_5m)
            if not allowed:
                signal = None

        # --- ML Confirmation & Logging (Applied to ALL strategies) ---
        features_now = df_5m[['RSI', 'Dist_VWAP', 'Z_Score_VWAP', 'volume']].iloc[[-1]]
        confidence = self.get_ml_confidence(ticker, features_now)
        
        # Log to DB for "Learning from Mistakes"
        if signal:
             try:
                 # We assume 'predicted_price' here is just the confidence score for now, 
                 # or we could make a dummy price projection: Price * (1 + (Conf-0.5)/100)
                 # Let's log confidence directly.
                 # Updated to include SIDE (signal)
                 self.db.log_prediction(ticker, float(confidence), float(latest['close']), float(confidence), strategy_type, side=signal)
             except Exception as e:
                 # print(e)
                 pass

        if signal:
            # Using a slightly looser threshold for trend strategies, tighter for reversion?
            # Let's keep 0.60 as base filter
            if confidence < 0.60:
                # print(f"Trade filtered by ML: {signal} Confidence {confidence:.2f}")
                signal = None 
            
        return signal, atr
