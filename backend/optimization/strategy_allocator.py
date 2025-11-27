"""
Strategy Allocation Optimization
Modern Portfolio Theory applied to strategy weights
"""

import numpy as np
from scipy.optimize import minimize
import pandas as pd

from backend.core.config import config
from backend.core.logger import get_logger

logger = get_logger(__name__)


def calculate_covariance_matrix(returns_df: pd.DataFrame) -> np.ndarray:
    """Calculate covariance matrix of strategy returns"""
    # Handle NaN values
    returns_df = returns_df.fillna(0)
    
    # Convert to numpy array
    returns = returns_df.values
    
    # Calculate covariance matrix
    cov_matrix = np.cov(returns, rowvar=False)
    
    # Regularization to avoid singular matrices
    cov_matrix += np.eye(cov_matrix.shape[0]) * 1e-6
    
    return cov_matrix


def optimize_weights(performance_df: pd.DataFrame, 
                    regime: str = 'NORMAL', 
                    risk_free_rate: float = 0.05) -> Dict[str, float]:
    """
    Optimize strategy weights using Modern Portfolio Theory
    
    Args:
        performance_df: DataFrame with strategy performance metrics
        regime: Current market regime (NORMAL, HIGH_VOLATILITY, LOW_VOLATILITY)
        risk_free_rate: Annualized risk-free rate
        
    Returns:
        Optimized weights dictionary
    """
    # Validate input
    if performance_df.empty:
        logger.warning("Performance DataFrame is empty - returning equal weights")
        return {strategy: 1/len(performance_df) for strategy in performance_df.index}
        
    # Get strategy returns
    returns = performance_df['avg_pnl'].values
    
    # Get covariance matrix
    cov_matrix = calculate_covariance_matrix(performance_df[['avg_pnl']])
    
    # Number of strategies
    n = len(returns)
    
    # Constraints
    def constraint_sum(weights):
        return np.sum(weights) - 1.0
    
    # Objective function (maximize Sharpe ratio)
    def objective(weights):
        portfolio_return = np.dot(weights, returns)
        portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        sharpe_ratio = (portfolio_return - risk_free_rate/252) / portfolio_volatility \
                        if portfolio_volatility > 0 else 0
        return -sharpe_ratio  # Minimize negative Sharpe
    
    # Bounds (0-40% per strategy)
    bounds = [(0, 0.4)] * n
    
    # Initial weights (equal)
    init_weights = np.ones(n) / n
    
    # Constraints (sum to 1)
    constraints = [{'type': 'eq', 'fun': constraint_sum}]
    
    # Regime adjustments
    if regime == 'HIGH_VOLATILITY':
        # Reduce max allocation per strategy
        bounds = [(0, 0.3)] * n
    elif regime == 'LOW_VOLATILITY':
        # Allow higher concentration
        bounds = [(0, 0.5)] * n
    
    # Optimization
    result = minimize(objective, init_weights, 
                     method='SLSQP', bounds=bounds, constraints=constraints)
    
    if not result.success:
        logger.error(f"Optimization failed: {result.message}")
        return {strategy: weight for strategy, weight in zip(performance_df.index, init_weights)}
    
    # Format results
    optimized_weights = {}
    for i, strategy in enumerate(performance_df.index):
        optimized_weights[strategy] = max(0, result.x[i])  # Remove negative weights
    
    # Normalize to sum to 1
    total = sum(optimized_weights.values())
    return {strategy: weight/total for strategy, weight in optimized_weights.items()}
