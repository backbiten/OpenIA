import numpy as np
from typing import List, Dict
from .market import MarketTick

class MarketAnalyzer:
    """
    Advanced analytics for the OpenIA Internal Stock Exchange (ISE).
    Uses NumPy to process the 'heartbeat' of the AI's internal economy.
    """
    
    def __init__(self, history: List[MarketTick]):
        self.history = history
        self.currencies = list(history[0].prices.keys()) if history else []

    def _get_price_series(self, currency: str) -> np.ndarray:
        """Extracts a time-series of prices for a specific currency."""
        return np.array([tick.prices.get(currency, 0.0) for tick in self.history])

    def calculate_vibrancy(self, currency: str = "Coinbits") -> Dict[str, float]:
        """
        Calculates the 'Vibrancy' of a currency based on its volatility and growth.
        A vibrant currency is one that is actively growing and responding to noise.
        """
        prices = self._get_price_series(currency)
        if len(prices) < 2:
            return {"mean_price": float(np.mean(prices)) if len(prices) > 0 else 0.0, "volatility": 0.0, "total_growth": 0.0}

        # Calculate rate of change (Growth)
        growth_rates = np.diff(prices)
        
        # Calculate standard deviation of changes (Volatility/Vibrancy)
        volatility = np.std(growth_rates)
        
        # Calculate overall trend
        total_growth = prices[-1] - prices[0]
        
        return {
            "mean_price": float(np.mean(prices)),
            "volatility": float(volatility),
            "total_growth": float(total_growth),
            "vibrancy_score": float(volatility * (1 + total_growth))
        }

    def system_correlation(self) -> np.ndarray:
        """
        Calculates the correlation matrix between all internal currencies.
        Helps identify if different parts of the AI (Threads, Buffers, Cores) 
        are 'breathing' together.
        """
        if not self.currencies or len(self.history) < 2:
            return np.array([])
            
        data = np.array([self._get_price_series(c) for c in self.currencies])
        return np.corrcoef(data)

    def summary(self) -> Dict[str, Dict[str, float]]:
        """Returns a full vibrancy report for the entire tree of life."""
        return {c: self.calculate_vibrancy(c) for c in self.currencies}