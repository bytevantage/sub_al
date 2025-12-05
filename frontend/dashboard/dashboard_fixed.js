// FIXED DASHBOARD JAVASCRIPT - NO CACHE-BUSTING
// This file is identical to dashboard.js but with all CORS issues fixed

// API Configuration
const API_BASE_URL = 'http://localhost:8000';

// Fetch queue management
const fetchQueue = new Map();
const MAX_CONCURRENT = 5;

// Status tracking
let engineStatusCheckInProgress = false;

// Fixed fetch function without cache-busting
async function fetchWithTimeout(url, options = {}, timeout = 15000, retries = 2) {
    const requestKey = url.split('?')[0];
    
    if (fetchQueue.has(requestKey) && fetchQueue.get(requestKey) > 0) {
        console.warn(`Request already in progress: ${requestKey}`);
        while (fetchQueue.has(requestKey) && fetchQueue.get(requestKey) > 0) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    }
    
    fetchQueue.set(requestKey, (fetchQueue.get(requestKey) || 0) + 1);
    
    try {
        const activeRequests = Array.from(fetchQueue.values()).reduce((a, b) => a + b, 0);
        if (activeRequests > MAX_CONCURRENT) {
            console.warn(`Too many concurrent requests (${activeRequests}), queuing...`);
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        
        for (let attempt = 0; attempt <= retries; attempt++) {
            let timeoutId = null;
            try {
                const controller = new AbortController();
                timeoutId = setTimeout(() => controller.abort(), timeout);
                
                const response = await fetch(url, {
                    ...options,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                return response;
                
            } catch (error) {
                if (timeoutId) {
                    clearTimeout(timeoutId);
                }
                
                if (attempt === retries) {
                    console.error(`Fetch failed after ${retries + 1} attempts:`, error);
                    throw error;
                }
                
                console.warn(`Fetch attempt ${attempt + 1} failed, retrying...`, error);
                await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
            }
        }
    } finally {
        fetchQueue.set(requestKey, fetchQueue.get(requestKey) - 1);
        if (fetchQueue.get(requestKey) <= 0) {
            fetchQueue.delete(requestKey);
        }
    }
}

// Fixed API calls without cache-busting
async function updateCapitalInfo() {
    try {
        const response = await fetchWithTimeout(`${API_BASE_URL}/api/capital`, {}, 15000, 2);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log('✅ Capital info updated successfully');
        return data;
        
    } catch (error) {
        console.error('Error updating capital info:', error);
        return null;
    }
}

async function updatePositions() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/dashboard/positions`);
        const data = await response.json();
        
        if (data.status === 'success') {
            console.log('✅ Positions updated successfully');
            return data.data.positions;
        }
        
    } catch (error) {
        console.error('Error fetching positions:', error);
        return [];
    }
}

async function updateMarketOverview() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/market/overview`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('✅ Market overview updated successfully');
        return data;
        
    } catch (error) {
        console.error('Error fetching market overview:', error);
        return null;
    }
}

async function updateTradeHistory() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/dashboard/trades/recent?limit=100&today_only=true`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('✅ Trade history updated successfully');
        return data.data.trades;
        
    } catch (error) {
        console.error('Error fetching trade history:', error);
        return [];
    }
}

async function updateRiskMetrics() {
    try {
        const response = await fetchWithTimeout(`${API_BASE_URL}/api/dashboard/risk-metrics`, {}, 15000, 2);
        const data = await response.json();
        
        if (data.status === 'success' && data.data) {
            console.log('✅ Risk metrics updated successfully');
            return data.data;
        }
        
    } catch (error) {
        console.error('Error fetching risk metrics:', error);
        return null;
    }
}

async function checkEngineStatus() {
    if (engineStatusCheckInProgress) {
        console.log('⏭️ Skipping engine status check (previous check still in progress)');
        return false;
    }
    
    engineStatusCheckInProgress = true;
    
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        
        const response = await fetch(`${API_BASE_URL}/api/health`, {
            signal: controller.signal
        });
        clearTimeout(timeout);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        const isRunning = data.trading_active === true;
        console.log('✅ Engine status checked successfully');
        return isRunning;
        
    } catch (error) {
        console.error('❌ Error checking engine status:', error);
        return false;
    } finally {
        engineStatusCheckInProgress = false;
    }
}

// Main refresh function
async function refreshData() {
    console.log('🔄 Refreshing dashboard data...');
    
    try {
        await Promise.all([
            updateCapitalInfo(),
            updatePositions(),
            updateMarketOverview(),
            updateTradeHistory(),
            updateRiskMetrics()
        ]);
        
        console.log('✅ Dashboard data refresh completed');
        
    } catch (error) {
        console.error('Error refreshing data:', error);
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Fixed Dashboard initializing...');
    
    // Initial data load
    refreshData();
    
    // Set up periodic updates
    setInterval(refreshData, 30000); // Every 30 seconds
    
    console.log('✅ Fixed Dashboard initialized successfully');
});

// Export functions for global access
window.updateCapitalInfo = updateCapitalInfo;
window.updatePositions = updatePositions;
window.updateMarketOverview = updateMarketOverview;
window.updateTradeHistory = updateTradeHistory;
window.updateRiskMetrics = updateRiskMetrics;
window.checkEngineStatus = checkEngineStatus;
window.refreshData = refreshData;
