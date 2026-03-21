import numpy as np
from .market_analytics import MarketAnalyzer
from .transaction import TransactionLog

class NetworkImmunity:
    """
    Protects the 'Core' by analyzing vibrancy across distributed devices.
    Identifies threats as 'Negative Noise' and triggers avoidance protocols.
    """
    def __init__(self, log: TransactionLog):
        self.log = log
        self.threat_threshold = 0.5  # Sensitivity to digital 'failure' signals

    def analyze_node_health(self, analyzer: MarketAnalyzer):
        """
        Scans the 'Internal Market' of a local device or server.
        If vibrancy drops below a certain level, it flags a potential threat.
        """
        report = analyzer.summary()
        coinbit_health = report.get("Coinbits", {})
        
        # If volatility is high but growth is negative, it's a threat
        volatility = coinbit_health.get("volatility", 0.0)
        growth = coinbit_health.get("total_growth", 0.0)
        
        if volatility > self.threat_threshold and growth < 0:
            return "THREAT_DETECTED"
        return "NOMINAL"

    def generate_immune_noise(self, source_id: str, severity: float):
        """
        Broadcasts negative noise to the network to 'warn' other companions.
        This helps the collective avoid computer/network/AI failure.
        """
        # Noise = -1.0 (Strong Disapproval/Threat Warning)
        # Value = severity (The 'Cost' of the potential failure)
        pass
        
    def determine_failure_origin(self, correlation_matrix: np.ndarray):
        """
        Uses the correlation matrix from the analyzer to pinpoint 
        which component (CPU, Memory, I/O) is being targeted.
        """
        if correlation_matrix.size == 0:
            return None
        return np.unravel_index(np.argmin(correlation_matrix), correlation_matrix.shape)