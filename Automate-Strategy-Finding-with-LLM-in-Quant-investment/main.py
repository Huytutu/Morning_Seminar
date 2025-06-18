import pandas as pd
import numpy as np
from vnstock import *
from tqdm import tqdm
import os
import warnings
warnings.filterwarnings('ignore')  # Suppress warnings for cleaner output

# Import alpha formula reader if available, otherwise create a placeholder
try:
    import modules.alpha_formula_reader as afr
except ImportError:
    # Create a placeholder module if the import fails
    class AlphaFormulaReader:
        @staticmethod
        def read_alpha_formula_from_excel(path):
            print(f"Warning: Could not import alpha_formula_reader module. Using default formulas.")
            return [
                "PriceMomentum", 
                "VolumeMomentum", 
                "RSIMomentum",
                "MeanReversion",
                "BollingerBandWidth"
            ]
    afr = AlphaFormulaReader()

# No authentication required for vnstock
print("Using vnstock library - no authentication required")

def result_to_excel(result, path="result.xlsx"):
    """Save analysis results to Excel file"""
    try:
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        writer = pd.ExcelWriter(path, engine='openpyxl')
        result["rank_ic_analysis"].summary().to_excel(writer, "ic-summary")
        result["quantile"].quantile_returns.to_excel(writer, "các phân nhóm lợi nhuận tích lũy")
        result["quantile"].quantile_turnover.to_excel(writer, "tỷ lệ luân chuyển nhóm")
        result["return"].factor_returns.to_excel(writer, "lợi nhuận tích lũy từ yếu tố")
        result["return"].max_drawdown().to_excel(writer, "mức rút lui tối đa")
        result["return"].std().to_excel(writer, "độ biến động lợi nhuận yếu tố")
        writer.close()
        print(f"Results saved to {path}")
    except Exception as e:
        print(f"Error saving results to {path}: {e}")

# Create Factor class to replace rqfactor's Factor
class Factor:
    def __init__(self, name):
        self.name = name
        self.data = None
    
    def calculate(self, stock_data):
        """Calculate factor value based on stock data"""
        if self.name in stock_data.columns:
            return stock_data[self.name]
        else:
            return None

# Define factor calculation functions
def REF(series, n):
    """Equivalent to DELAY - returns the value n periods ago"""
    return series.shift(n)

def DELAY(series, n):
    """Returns the value n periods ago"""
    return series.shift(n)

def MA(series, n):
    """Simple moving average"""
    return series.rolling(n).mean()

def SMA(series, n):
    """Simple moving average (alias)"""
    return series.rolling(n).mean()

def EMA(series, n):
    """Exponential moving average"""
    return series.ewm(span=n, adjust=False).mean()

def STD(series, n):
    """Standard deviation"""
    return series.rolling(n).std()

# Define factor variables
def create_factors(stock_data):
    """Create and calculate factor variables"""
    factors = {}
    
    # Ensure all required columns exist in stock_data
    required_columns = ["close", "low", "high", "volume"]
    for col in required_columns:
        if col not in stock_data.columns:
            raise ValueError(f"Required column '{col}' not found in stock data")
    
    # Basic price and volume factors
    factors["close"] = stock_data["close"]
    factors["low"] = stock_data["low"]
    factors["volume"] = stock_data["volume"]
    factors["high"] = stock_data["high"]
    
    # Calculate returns
    factors["returns"] = stock_data["close"].pct_change()
    
    # Market cap proxy (price * volume as simplified placeholder)
    factors["market_cap"] = stock_data["close"] * stock_data["volume"]
    factors["cap"] = factors["market_cap"]
    
    # Calculate VWAP
    if "value" in stock_data.columns:
        # Avoid division by zero
        factors["vwap"] = np.where(
            stock_data["volume"] > 0,
            stock_data["value"] / stock_data["volume"],
            stock_data["close"]
        )
    else:
        # Approximate VWAP calculation if value not available
        factors["vwap"] = ((factors["high"] + factors["low"] + factors["close"]) / 3)
    
    # Calculate technical indicators
    # RSI calculation
    delta = factors["close"].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    # Use EMA instead of simple MA for more stable RSI calculation
    avg_gain = gain.ewm(com=9, adjust=False).mean()  # 10-period EMA
    avg_loss = loss.ewm(com=9, adjust=False).mean()  # 10-period EMA
    
    # Handle division by zero in RSI calculation
    rs = np.where(avg_loss == 0, 100, avg_gain / avg_loss.replace(0, np.nan).fillna(0.001))
    factors["RSI10"] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands
    factors["BOLL"] = MA(factors["close"], 20)
    bollinger_std = STD(factors["close"], 20)
    factors["BOLL_UP"] = factors["BOLL"] + 2 * bollinger_std
    factors["BOLL_DOWN"] = factors["BOLL"] - 2 * bollinger_std
    
    # Financial metrics (placeholders - in a real implementation, get from vnstock)
    # These are simplified proxies and would need actual data in production
    factors["basic_eps"] = pd.Series(1000 / factors["close"], index=stock_data.index)
    factors["ebitda_ttm"] = pd.Series(factors["close"] * 1000, index=stock_data.index)
    factors["pb_ratio_ttm"] = pd.Series(factors["close"] / 10, index=stock_data.index)
    factors["gross_profit_margin_ttm"] = pd.Series(0.3 + 0.1 * np.random.random(len(factors["close"])), index=stock_data.index)
    factors["profit_from_operation_to_revenue_ttm"] = pd.Series(0.2 + 0.05 * np.random.random(len(factors["close"])), index=stock_data.index)
    factors["peg_ratio_ttm"] = pd.Series(1.5 + 0.5 * np.random.random(len(factors["close"])), index=stock_data.index)
    
    # ATR calculation
    high_low = factors["high"] - factors["low"]
    high_close = abs(factors["high"] - REF(factors["close"], 1))
    low_close = abs(factors["low"] - REF(factors["close"], 1))
    
    # Use pandas DataFrame for cleaner max operation
    tr_df = pd.DataFrame({
        'hl': high_low,
        'hc': high_close,
        'lc': low_close
    })
    tr = tr_df.max(axis=1)
    factors["ATR"] = tr.rolling(14).mean()
    
    return factors

# Define derived factors
def calculate_derived_factors(factors):
    """Calculate derived factors based on basic factors"""
    derived = {}
    
    # Error handling for each derived factor
    try:
        derived["PriceMomentum"] = factors["close"] - DELAY(factors["close"], 14)
    except Exception as e:
        print(f"Error calculating PriceMomentum: {e}")
        derived["PriceMomentum"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        derived["VolumeMomentum"] = factors["volume"] - DELAY(factors["volume"], 14)
    except Exception as e:
        print(f"Error calculating VolumeMomentum: {e}")
        derived["VolumeMomentum"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        derived["RSIMomentum"] = factors["RSI10"] - DELAY(factors["RSI10"], 14)
    except Exception as e:
        print(f"Error calculating RSIMomentum: {e}")
        derived["RSIMomentum"] = pd.Series(np.nan, index=factors["close"].index)
    
    try:
        derived["MeanReversion"] = MA(factors["close"], 20) - factors["close"]
    except Exception as e:
        print(f"Error calculating MeanReversion: {e}")
        derived["MeanReversion"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        std_20 = STD(factors["close"], 20)
        # Handle division by zero
        std_20_safe = std_20.replace(0, np.nan).fillna(0.001)
        derived["ZScoreMeanReversion"] = (factors["close"] - MA(factors["close"], 20)) / std_20_safe
    except Exception as e:
        print(f"Error calculating ZScoreMeanReversion: {e}")
        derived["ZScoreMeanReversion"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        derived["BollingerBands"] = factors["BOLL"]
    except Exception as e:
        print(f"Error calculating BollingerBands: {e}")
        derived["BollingerBands"] = pd.Series(np.nan, index=factors["close"].index)
    
    try:
        derived["StandardDeviation"] = STD(factors["close"], 20)
    except Exception as e:
        print(f"Error calculating StandardDeviation: {e}")
        derived["StandardDeviation"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        derived["ATR"] = factors["ATR"]
    except Exception as e:
        print(f"Error calculating ATR: {e}")
        derived["ATR"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        # Handle division by zero
        sma_20 = SMA(factors["close"], 20)
        sma_20_safe = sma_20.replace(0, np.nan).fillna(0.001)
        derived["BollingerBandWidth"] = (factors["BOLL_UP"] - factors["BOLL_DOWN"]) / sma_20_safe
    except Exception as e:
        print(f"Error calculating BollingerBandWidth: {e}")
        derived["BollingerBandWidth"] = pd.Series(np.nan, index=factors["close"].index)
    
    try:
        # Handle division by zero
        basic_eps_safe = factors["basic_eps"].replace(0, np.nan).fillna(0.001)
        derived["PE"] = factors["close"] / basic_eps_safe
    except Exception as e:
        print(f"Error calculating PE: {e}")
        derived["PE"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        derived["PB"] = factors["pb_ratio_ttm"]
    except Exception as e:
        print(f"Error calculating PB: {e}")
        derived["PB"] = pd.Series(np.nan, index=factors["close"].index)
    
    try:
        derived["TradingVolume"] = factors["volume"]
    except Exception as e:
        print(f"Error calculating TradingVolume: {e}")
        derived["TradingVolume"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        derived["AverageTradingVolume"] = MA(factors["volume"], 20)
    except Exception as e:
        print(f"Error calculating AverageTradingVolume: {e}")
        derived["AverageTradingVolume"] = pd.Series(np.nan, index=factors["close"].index)
    
    try:
        derived["GrossProfitMargin"] = factors["gross_profit_margin_ttm"]
    except Exception as e:
        print(f"Error calculating GrossProfitMargin: {e}")
        derived["GrossProfitMargin"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        derived["OperatingProfitMargin"] = factors["profit_from_operation_to_revenue_ttm"]
    except Exception as e:
        print(f"Error calculating OperatingProfitMargin: {e}")
        derived["OperatingProfitMargin"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        derived["EarningsGrowthRate"] = factors["peg_ratio_ttm"]
    except Exception as e:
        print(f"Error calculating EarningsGrowthRate: {e}")
        derived["EarningsGrowthRate"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        # Handle division by zero
        ebitda_delay = DELAY(factors["ebitda_ttm"], 1)
        ebitda_delay_safe = ebitda_delay.replace(0, np.nan).fillna(0.001)
        derived["EBITDAGrowthRate"] = factors["ebitda_ttm"] / ebitda_delay_safe - 1
    except Exception as e:
        print(f"Error calculating EBITDAGrowthRate: {e}")
        derived["EBITDAGrowthRate"] = pd.Series(np.nan, index=factors["close"].index)
    
    try:
        derived["MovingAverage"] = SMA(factors["close"], 20)
    except Exception as e:
        print(f"Error calculating MovingAverage: {e}")
        derived["MovingAverage"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        derived["ExponentialMovingAverage"] = EMA(factors["close"], 20)
    except Exception as e:
        print(f"Error calculating ExponentialMovingAverage: {e}")
        derived["ExponentialMovingAverage"] = pd.Series(np.nan, index=factors["close"].index)
    
    try:
        # Handle division by zero
        close_delay_21 = DELAY(factors["close"], 21)
        close_delay_21_safe = close_delay_21.replace(0, np.nan).fillna(0.001)
        derived["MonthlyReturn"] = (factors["close"] - close_delay_21) / close_delay_21_safe
    except Exception as e:
        print(f"Error calculating MonthlyReturn: {e}")
        derived["MonthlyReturn"] = pd.Series(np.nan, index=factors["close"].index)
        
    try:
        # Handle division by zero
        close_delay_63 = DELAY(factors["close"], 63)
        close_delay_63_safe = close_delay_63.replace(0, np.nan).fillna(0.001)
        derived["QuarterlyReturn"] = (factors["close"] - close_delay_63) / close_delay_63_safe
    except Exception as e:
        print(f"Error calculating QuarterlyReturn: {e}")
        derived["QuarterlyReturn"] = pd.Series(np.nan, index=factors["close"].index)
    
    return derived

class FactorAnalysisEngine:
    """Simplified version of the Factor Analysis Engine"""
    
    def __init__(self):
        self.pipeline = []
    
    def append(self, component):
        """Add component to the pipeline"""
        self.pipeline.append(component)
    
    def analysis(self, df, freq, ascending=True, periods=None, keep_preprocess_result=False):
        """Run analysis on the factor data"""
        # This is a simplified implementation
        # In a real implementation, you would apply each component in the pipeline
        
        # Create mock result data for demonstration
        result = {
            "rank_ic_analysis": MockICAnalysis(),
            "quantile": MockQuantileAnalysis(),
            "return": MockReturnAnalysis()
        }
        
        return result

class MockICAnalysis:
    """Mock implementation of ICAnalysis"""
    
    def summary(self):
        """Return mock IC summary"""
        # Create a simple mock summary DataFrame
        return pd.DataFrame({
            'IC Mean': [0.05, 0.04, 0.03],
            'IC Std': [0.02, 0.02, 0.03],
            'T-stat': [2.5, 2.0, 1.0],
            'P-value': [0.01, 0.05, 0.30],
            'IC IR': [2.5, 2.0, 1.0]
        }, index=['Period 1', 'Period 3', 'Period 5'])

class MockQuantileAnalysis:
    """Mock implementation of Quantile Analysis"""
    
    @property
    def quantile_returns(self):
        """Return mock quantile returns"""
        # Create mock quantile returns
        dates = pd.date_range(start='2022-09-30', end='2022-12-31', freq='B')
        df = pd.DataFrame(np.random.randn(len(dates), 5) * 0.01, index=dates, 
                          columns=['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])
        return df.cumsum()
    
    @property
    def quantile_turnover(self):
        """Return mock quantile turnover"""
        # Create mock turnover data
        dates = pd.date_range(start='2022-09-30', end='2022-12-31', freq='B')
        df = pd.DataFrame(np.random.rand(len(dates), 5) * 0.2, index=dates, 
                          columns=['Q1', 'Q2', 'Q3', 'Q4', 'Q5'])
        return df

class MockReturnAnalysis:
    """Mock implementation of Return Analysis"""
    
    @property
    def factor_returns(self):
        """Return mock factor returns"""
        # Create mock factor returns
        dates = pd.date_range(start='2022-09-30', end='2022-12-31', freq='B')
        df = pd.DataFrame(np.random.randn(len(dates), 3) * 0.01, index=dates, 
                          columns=['Period 1', 'Period 3', 'Period 5'])
        return df.cumsum()
    
    def max_drawdown(self):
        """Calculate mock maximum drawdown"""
        return pd.DataFrame({
            'Max Drawdown': [-0.15, -0.12, -0.08]
        }, index=['Period 1', 'Period 3', 'Period 5'])
    
    def std(self):
        """Calculate mock standard deviation"""
        return pd.DataFrame({
            'Standard Deviation': [0.02, 0.018, 0.015]
        }, index=['Period 1', 'Period 3', 'Period 5'])

# Parse formula string to function (placeholders for now)
def parse_formula(formula_str):
    """Parse a formula string into a callable function"""
    # This is a placeholder - in a real implementation you would parse the formula
    # and create a function that evaluates it
    
    def formula_func(factors, derived):
        """Example formula function that returns a factor value"""
        if formula_str == "PriceMomentum":
            return derived["PriceMomentum"]
        elif formula_str == "VolumeMomentum":
            return derived["VolumeMomentum"]
        elif formula_str == "RSIMomentum":
            return derived["RSIMomentum"]
        elif formula_str == "MeanReversion":
            return derived["MeanReversion"]
        elif formula_str == "BollingerBandWidth":
            return derived["BollingerBandWidth"]
        else:
            # Default to a random factor if formula not recognized
            return pd.Series(np.random.randn(len(factors["close"])) * 0.1, index=factors["close"].index)
    
    return formula_func

# Define execution function for factors
def execute_factor(formula_str, symbols, start_date, end_date):
    """Execute factor calculation for given symbols over date range"""
    result_dfs = []
    
    # Parse the formula string to get a callable function
    formula_func = parse_formula(formula_str)

    for symbol in symbols:
        try:
            # Get stock data from vnstock
            try:
                # Create a Quote object for the symbol
                quote = Quote(symbol=symbol, source='VCI')

                # Retrieve historical data
                stock_data = quote.history(start=start_date, end=end_date, interval='1d')
                
                if stock_data.empty:
                    print(f"No data available for {symbol}. Skipping.")
                    continue
                    
            except Exception as e:
                print(f"Error retrieving data for {symbol}: {e}")
                # Try an alternative source
                try:
                    print(f"Trying alternative source for {symbol}...")
                    quote = Quote(symbol=symbol, source='TCBS')
                    stock_data = quote.history(start=start_date, end=end_date, interval='1d')
                    
                    if stock_data.empty:
                        print(f"No data available for {symbol} from alternative source. Skipping.")
                        continue
                except Exception as e2:
                    print(f"Error retrieving data from alternative source for {symbol}: {e2}")
                    continue

            # Calculate basic factors
            factors = create_factors(stock_data)

            # Calculate derived factors
            derived = calculate_derived_factors(factors)

            # Evaluate the formula function with these factors
            factor_value = formula_func(factors, derived)
            
            # Create result DataFrame
            factor_result = pd.DataFrame({
                'factor': factor_value,
                'symbol': symbol
            }, index=stock_data.index)

            result_dfs.append(factor_result)

        except Exception as e:
            print(f"Error processing symbol {symbol}: {e}")

    if result_dfs:
        return pd.concat(result_dfs)
    else:
        print("Warning: No data collected for any symbols.")
        # Return empty DataFrame with correct columns
        return pd.DataFrame(columns=['factor', 'symbol'])

# Main execution
if __name__ == "__main__":
    # Create directory for results if it doesn't exist
    os.makedirs("./result/alpha_analysis", exist_ok=True)
    
    # Get VN30 index components as a replacement for 000016.XSHG
    try:
        listing = Listing()
        # vn30_symbols = listing.index_components(IndexCode='VN30')['ticker'].tolist()
        vn30_symbols = listing.
        print(f"Successfully retrieved {len(vn30_symbols)} VN30 components")
    except Exception as e:
        print(f"Error retrieving VN30 components: {e}")
        # Fallback if API fails
        vn30_symbols = ['VNM', 'VIC', 'VCB', 'FPT', 'MWG', 'HPG', 'MSN', 'TCB']  
        print(f"Using fallback VN30 components: {vn30_symbols}")
    
    # Dates for analysis
    d1 = "2022-09-30"
    d2 = "2022-12-31"
    
    # Read alpha formulas from Excel
    try:
        formulas = afr.read_alpha_formula_from_excel("./data/Seed Alpha.xlsx")
        print(f"Successfully loaded {len(formulas)} formulas from file")
    except Exception as e:
        print(f"Error reading formulas: {e}")
        # Provide some sample formulas for testing if file not found
        formulas = [
            "PriceMomentum", 
            "VolumeMomentum", 
            "RSIMomentum",
            "MeanReversion",
            "BollingerBandWidth"
        ]
        print(f"Using {len(formulas)} default formulas")
    
    # Process each formula
    for i, formula in enumerate(tqdm(formulas)):
        path = f"./result/alpha_analysis/{i + 1}.xlsx"
        print(f"Processing formula {i+1}: {formula}")
        
        try:
            # Execute factor on stock data
            df = execute_factor(formula, vn30_symbols, d1, d2)
            
            if df.empty:
                print(f"No factor data generated for formula {formula}. Skipping analysis.")
                continue
            
            # Instantiate analysis engine
            engine = FactorAnalysisEngine()
            
            # Add neutralization component (simplified - placeholder)
            engine.append(
                (
                    "neutralization",
                    "Neutralization placeholder"  # Would be an actual neutralization object
                )
            )
            
            # Add analysis components
            engine.append(
                (
                    "rank_ic_analysis",
                    "IC Analysis placeholder"  # Would be an actual IC analysis object
                )
            )
            engine.append(
                (
                    "quantile", 
                    "Quantile Analysis placeholder"  # Would be an actual quantile analysis object
                )
            )
            engine.append(
                (
                    "return",
                    "Return Analysis placeholder"  # Would be an actual return analysis object
                )
            )
            
            # Run analysis
            result = engine.analysis(
                df, "daily", ascending=True, periods=[1, 3, 5], keep_preprocess_result=True
            )
            
            # Save results to Excel
            result_to_excel(result, path)
            
        except Exception as e:
            print(f"Error processing formula {formula}: {e}")