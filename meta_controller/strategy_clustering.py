"""
Strategy Clustering into 9 Meta-Groups
Logical grouping of 25 strategies based on trading characteristics
"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class MetaGroup:
    """Meta-group definition"""
    id: int
    name: str
    strategies: List[str]
    max_allocation: float
    description: str


# Define the 9 meta-groups
META_GROUPS = [
    MetaGroup(
        id=0,
        name="ML_PREDICTION",
        strategies=["QuantumEdge"],
        max_allocation=0.35,
        description="ML-based directional prediction with high confidence signals"
    ),
    MetaGroup(
        id=1,
        name="GREEKS_DELTA_NEUTRAL",
        strategies=["GammaScalping", "DeltaHedging", "GammaHarvesting"],
        max_allocation=0.35,
        description="Delta-neutral Greeks-based strategies exploiting gamma and volatility"
    ),
    MetaGroup(
        id=2,
        name="VOLATILITY_TRADING",
        strategies=["VolatilityHarvesting", "IVRankTrading", "SkewArbitrage", "VegaScalping"],
        max_allocation=0.35,
        description="Volatility-focused strategies trading IV expansion/contraction"
    ),
    MetaGroup(
        id=3,
        name="MEAN_REVERSION",
        strategies=["VWAPDeviation", "BollingerBounce", "RSIReversal", "OverboughtOversold"],
        max_allocation=0.35,
        description="Mean reversion strategies exploiting price extremes"
    ),
    MetaGroup(
        id=4,
        name="MOMENTUM_TREND",
        strategies=["MomentumImpulse", "TrendFollowing", "BreakoutStrategy"],
        max_allocation=0.35,
        description="Momentum and trend-following strategies"
    ),
    MetaGroup(
        id=5,
        name="OI_INSTITUTIONAL_FLOW",
        strategies=["OIAccumulation", "InstitutionalFootprint", "MaxPainMagnet", "DealerGammaExposure"],
        max_allocation=0.35,
        description="Open Interest and institutional order flow analysis"
    ),
    MetaGroup(
        id=6,
        name="PCR_SENTIMENT",
        strategies=["PCRReversal", "SentimentAnalysis", "PutCallFlow"],
        max_allocation=0.35,
        description="Put-Call Ratio and market sentiment indicators"
    ),
    MetaGroup(
        id=7,
        name="INTRADAY_PATTERNS",
        strategies=["TimeOfDayPatterns", "OpeningRangeBreakout", "MarketProfileGapFill", "VWAP"],
        max_allocation=0.35,
        description="Intraday time-based and microstructure patterns"
    ),
    MetaGroup(
        id=8,
        name="ARBITRAGE_SPREADS",
        strategies=["IronCondor", "ButterflySpread", "CalendarSpreadArbitrage", "VolatilityCapture"],
        max_allocation=0.35,
        description="Multi-leg spread and arbitrage strategies"
    )
]


# Reverse mapping: strategy name -> meta-group
STRATEGY_TO_GROUP: Dict[str, int] = {}
for group in META_GROUPS:
    for strategy in group.strategies:
        STRATEGY_TO_GROUP[strategy] = group.id


def get_meta_group(strategy_name: str) -> int:
    """Get meta-group ID for a strategy"""
    # Normalize strategy name
    normalized = strategy_name.replace("Strategy", "").replace("_", "")
    
    for key in STRATEGY_TO_GROUP:
        if key.replace("_", "").lower() in normalized.lower():
            return STRATEGY_TO_GROUP[key]
    
    # Default to mean reversion if unknown
    return 3


def get_group_strategies(group_id: int) -> List[str]:
    """Get all strategies in a meta-group"""
    return META_GROUPS[group_id].strategies


def get_group_name(group_id: int) -> str:
    """Get meta-group name"""
    return META_GROUPS[group_id].name


def print_clustering():
    """Print the complete clustering"""
    print("="*80)
    print("STRATEGY META-GROUPS (9 Clusters)")
    print("="*80)
    
    for group in META_GROUPS:
        print(f"\n{group.id}. {group.name}")
        print(f"   Max Allocation: {group.max_allocation*100:.0f}%")
        print(f"   Description: {group.description}")
        print(f"   Strategies ({len(group.strategies)}):")
        for strategy in group.strategies:
            print(f"      - {strategy}")
    
    print(f"\n{'='*80}")
    print(f"Total Strategies: {sum(len(g.strategies) for g in META_GROUPS)}")
    print(f"Total Meta-Groups: {len(META_GROUPS)}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    print_clustering()
