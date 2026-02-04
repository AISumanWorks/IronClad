import pandas as pd

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
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
        self.imputer = SimpleImputer(strategy='mean')
        self.min_training_samples = 100
        self.db = DatabaseManager()
        
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
        
        # Helper: VWAP
        # Cumulative VWAP: sum(Price * Vol) / sum(Vol)
        df['VWAP'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
            
        # Reversion Bands (VWAP +/- 2 SD)
        df['Dist_VWAP'] = df['close'] - df['VWAP']
        df['Dist_VWAP_Std'] = df['Dist_VWAP'].rolling(20).std()
        df['Z_Score_VWAP'] = df['Dist_VWAP'] / df['Dist_VWAP_Std']

        # Supertrend (10, 3)
        df = self.add_supertrend(df, period=10, multiplier=3)
        
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
        Trains a RandomForestClassifier for the specific ticker.
        """
        data, features = self.prepare_ml_data(df.copy())
        
        if len(data) < self.min_training_samples:
            # print(f"Not enough data to train ML for {ticker}")
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

        # Optimization: Grid Search for better precision
        # We want to maximize Precision (Accuracy of Buy signals)
        param_grid = {
            'n_estimators': [50, 100, 200],
            'max_depth': [3, 5, 10],
            'min_samples_split': [2, 5, 10],
            'class_weight': ['balanced', None] # Handle imbalance
        }
        
        # specific scoring for trading: precision of the positive class (1)
        # We use TimeSeriesSplit to respect time order (though GridSearch usually uses KFold, standard splits risk leakage)
        # But for simple tuning here, KFold is okay if data is shuffled? No, financial data.
        # Use TimeSeriesSplit
        
        tscv = TimeSeriesSplit(n_splits=3)
        
        base_clf = RandomForestClassifier(random_state=42)
        
        grid_search = GridSearchCV(
            estimator=base_clf,
            param_grid=param_grid,
            scoring='precision', # Prioritize being RIGHT when Buying
            cv=tscv,
            n_jobs=1, # Avoid threading issues in loops
            verbose=0
        )
        
        try:
             grid_search.fit(X, y)
             best_model = grid_search.best_estimator_
             self.models[ticker] = best_model
             # print(f"Optimized Model for {ticker}. Best Params: {grid_search.best_params_}")
        except Exception as e:
             # Fallback
             # print(f"GridSearch failed for {ticker}: {e}. Using default.")
             clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
             clf.fit(X, y)
             self.models[ticker] = clf

    def get_ml_confidence(self, ticker: str, current_features: pd.DataFrame):
        """Returns the probability of the positive class (Buy)."""
        model = self.models.get(ticker)
        if model is None:
            return 0.5 # Neutral
            
        try:
            # Ensure shape matches
            prob = model.predict_proba(current_features)[:, 1] # Probability of class 1
            return prob[0]
        except:
            return 0.5

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

    def generate_signal(self, ticker: str, df_5m: pd.DataFrame, df_1h: pd.DataFrame, strategy_type='composite'):
        """
        Core Decision Logic.
        Supported Strategies: 'composite' (Antigravity), 'orb', 'supertrend', 'ma_crossover'
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

        # --- ML Confirmation & Logging (Applied to ALL strategies) ---
        features_now = df_5m[['RSI', 'Dist_VWAP', 'Z_Score_VWAP', 'volume']].iloc[[-1]]
        confidence = self.get_ml_confidence(ticker, features_now)
        
        # Log to DB for "Learning from Mistakes"
        try:
             # We assume 'predicted_price' here is just the confidence score for now, 
             # or we could make a dummy price projection: Price * (1 + (Conf-0.5)/100)
             # Let's log confidence directly.
             self.db.log_prediction(ticker, float(confidence), float(latest['close']), float(confidence), strategy_type)
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
