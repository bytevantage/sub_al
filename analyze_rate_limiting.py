#!/usr/bin/env python3
"""
Rate Limiting Impact Analysis
Calculate API request frequency with new cache settings
"""

def analyze_rate_limiting():
    """Analyze rate limiting impact of new cache settings"""
    
    print("🚨 RATE LIMITING IMPACT ANALYSIS")
    print("=" * 50)
    
    print("\n📊 CURRENT CACHE SETTINGS:")
    print(f"   • Spot Price TTL: 1 second")
    print(f"   • Option Chain TTL: 2 seconds")
    print(f"   • Technical Indicators TTL: 5 seconds")
    
    print("\n📈 API REQUEST FREQUENCY CALCULATION:")
    
    # Calculate requests per minute
    symbols = ["NIFTY", "SENSEX"]  # Active symbols
    
    # Spot price requests
    spot_requests_per_symbol = 60 / 1  # 60 requests per minute per symbol
    total_spot_requests = spot_requests_per_symbol * len(symbols)
    
    # Option chain requests
    option_requests_per_symbol = 60 / 2  # 30 requests per minute per symbol
    total_option_requests = option_requests_per_symbol * len(symbols)
    
    # Technical indicator requests
    tech_requests_per_symbol = 60 / 5  # 12 requests per minute per symbol
    total_tech_requests = tech_requests_per_symbol * len(symbols)
    
    total_api_requests = total_spot_requests + total_option_requests + total_tech_requests
    
    print(f"\n🔥 REQUESTS PER MINUTE:")
    print(f"   • Spot Prices: {total_spot_requests} ({spot_requests_per_symbol} per symbol)")
    print(f"   • Option Chains: {total_option_requests} ({option_requests_per_symbol} per symbol)")
    print(f"   • Technical Indicators: {total_tech_requests} ({tech_requests_per_symbol} per symbol)")
    print(f"   • TOTAL: {total_api_requests} requests/minute")
    
    print(f"\n⚠️  RATE LIMITING COMPARISON:")
    print(f"   • System Limit: 12 orders/minute")
    print(f"   • API Requests: {total_api_requests}/minute")
    print(f"   • OVERLOAD: {total_api_requests - 12} requests over limit ({((total_api_requests/12 - 1) * 100):.0f}% excess)")
    
    print(f"\n🚨 CRITICAL ISSUES:")
    
    critical_issues = []
    
    if total_api_requests > 100:
        critical_issues.append(f"API request rate {total_api_requests}/min will trigger rate limiting")
    
    if total_option_requests > 60:
        critical_issues.append(f"Option chain requests {total_option_requests}/min will exceed API limits")
    
    if spot_requests_per_symbol > 30:
        critical_issues.append(f"Spot price requests {spot_requests_per_symbol}/min per symbol too frequent")
    
    for issue in critical_issues:
        print(f"   • {issue}")
    
    print(f"\n💡 SOLUTIONS:")
    print(f"   1. Increase cache TTL to safe levels")
    print(f"   2. Use WebSocket feed for real-time data")
    print(f"   3. Implement intelligent cache strategies")
    print(f"   4. Add request batching and throttling")
    
    return critical_issues

def recommend_safe_cache_settings():
    """Recommend safe cache settings to avoid rate limiting"""
    
    print(f"\n🎯 RECOMMENDED SAFE CACHE SETTINGS:")
    print(f"   • Spot Price TTL: 5 seconds (12 requests/minute per symbol)")
    print(f"   • Option Chain TTL: 10 seconds (6 requests/minute per symbol)")
    print(f"   • Technical Indicators TTL: 30 seconds (2 requests/minute per symbol)")
    
    print(f"\n📊 SAFE SETTINGS CALCULATION:")
    
    symbols = ["NIFTY", "SENSEX"]
    
    # Safe requests
    safe_spot_requests = 60 / 5 * len(symbols)  # 24 requests/minute
    safe_option_requests = 60 / 10 * len(symbols)  # 12 requests/minute
    safe_tech_requests = 60 / 30 * len(symbols)  # 4 requests/minute
    
    total_safe_requests = safe_spot_requests + safe_option_requests + safe_tech_requests
    
    print(f"   • Spot Prices: {safe_spot_requests}/minute")
    print(f"   • Option Chains: {safe_option_requests}/minute")
    print(f"   • Technical Indicators: {safe_tech_requests}/minute")
    print(f"   • TOTAL: {total_safe_requests}/minute (SAFE)")
    
    print(f"\n⚖️  BALANCE APPROACH:")
    print(f"   • Spot prices: 5s cache (fresh enough for trading)")
    print(f"   • Option chains: 10s cache (reasonable for opportunities)")
    print(f"   • Use WebSocket for critical real-time data")
    print(f"   • Cache only non-critical data")

def websocket_solution():
    """Explain WebSocket solution"""
    
    print(f"\n🔌 WEBSOCKET SOLUTION:")
    print(f"   ✅ Real-time data without API limits")
    print(f"   ✅ Instant price updates (no cache delay)")
    print(f"   ✅ No rate limiting concerns")
    print(f"   ✅ True LTP data for trading")
    
    print(f"\n📋 IMPLEMENTATION PRIORITY:")
    print(f"   1. Fix WebSocket connectivity issues")
    print(f"   2. Use WebSocket for spot prices")
    print(f"   3. Use WebSocket for option LTPs")
    print(f"   4. Keep API as backup only")

if __name__ == "__main__":
    issues = analyze_rate_limiting()
    recommend_safe_cache_settings()
    websocket_solution()
    
    if issues:
        print(f"\n🚨 RATE LIMITING RISK: HIGH")
        print(f"   Current settings will cause API rate limiting")
    else:
        print(f"\n✅ RATE LIMITING RISK: LOW")
