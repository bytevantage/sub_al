// Trading System Dashboard - Professional Edition v3.6
// Real-time monitoring and control interface
// v3.5: Market hours awareness for status badge, VIX API fix
// v3.6: 1-second risk monitoring, improved mixed signal clarity, SENSEX intelligence, removed duplicate OI display

const API_BASE = 'http://localhost:8000';
const API_BASE_URL = 'http://localhost:8000';  // Base URL for all API endpoints
const WS_BASE = 'ws://localhost:8000/ws';
const API_KEY = 'EMERGENCY_KEY_123';  // TODO: Move to env config
const REFRESH_INTERVAL = 2000;  // 2 seconds (fallback if WebSocket fails)

let refreshInterval = null;
let pnlChart = null;
let pnlData = [];
let ws = null;
let wsReconnectAttempts = 0;
let wsMaxReconnectAttempts = 5;
let wsReconnectDelay = 2000;
let tokenCheckInterval = null;
let engineStatusCheckInProgress = false;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Dashboard initializing...');
    
    // Start system time
    updateSystemTime();
    setInterval(updateSystemTime, 1000);
    
    // Initialize P&L chart
    initializePnLChart();
    
    // Load historical intraday P&L data
    loadIntradayPnLHistory();
    
    // Initialize WebSocket connection
    initializeWebSocket();
    
    // Start auto-refresh as fallback
    startAutoRefresh();
    
    // Start token monitoring
    startTokenMonitoring();
    
    // Initialize watchlist collapse state
    initWatchlistCollapse();
    
    // Initial data load
    refreshData();
    
    console.log('✓ Dashboard initialized');
});

// WebSocket Management
function initializeWebSocket() {
    console.log('Connecting to WebSocket...');
    
    ws = new WebSocket(WS_BASE);
    
    ws.onopen = function(event) {
        console.log('✓ WebSocket connected');
        wsReconnectAttempts = 0;
        updateConnectionStatus(true);
        
        // Stop polling when WebSocket is active
        stopAutoRefresh();
    };
    
    ws.onmessage = function(event) {
        try {
            const message = JSON.parse(event.data);
            handleWebSocketMessage(message);
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    };
    
    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
        updateConnectionStatus(false);
    };
    
    ws.onclose = function(event) {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);
        
        // Restart polling as fallback
        startAutoRefresh();
        
        // Attempt to reconnect
        attemptWebSocketReconnect();
    };
}

function attemptWebSocketReconnect() {
    if (wsReconnectAttempts < wsMaxReconnectAttempts) {
        wsReconnectAttempts++;
        const delay = wsReconnectDelay * wsReconnectAttempts;
        
        console.log(`Reconnecting to WebSocket (attempt ${wsReconnectAttempts}/${wsMaxReconnectAttempts}) in ${delay/1000}s...`);
        
        setTimeout(() => {
            initializeWebSocket();
        }, delay);
    } else {
        console.warn('Max WebSocket reconnection attempts reached. Using polling fallback.');
    }
}

function handleWebSocketMessage(message) {
    const messageType = message.type;
    const data = message.data;
    
    console.debug('WebSocket message:', messageType, data);
    
    switch (messageType) {
        case 'connection':
            console.log('WebSocket connection confirmed:', data);
            break;
            
        case 'position_update':
            handlePositionUpdate(data);
            break;
            
        case 'trade_closed':
        case 'trade_update':
            handleTradeUpdate(data);
            break;
            
        case 'pnl_update':
            handlePnLUpdate(data);
            break;
            
        case 'circuit_breaker_event':
            handleCircuitBreakerEvent(data);
            break;
            
        case 'alert':
            handleAlert(data);
            break;
            
        case 'market_condition':
            handleMarketConditionUpdate(data);
            break;
            
        case 'data_quality':
            handleDataQualityUpdate(data);
            break;
            
        case 'system_status':
            handleSystemStatusUpdate(data);
            break;
            
        case 'heartbeat':
            // Just log heartbeat
            console.debug('WebSocket heartbeat');
            break;
            
        default:
            console.warn('Unknown WebSocket message type:', messageType);
    }
}

// WebSocket Event Handlers
function handlePositionUpdate(data) {
    console.log('Position update received:', data);
    // Refresh positions display
    updatePositions();
}

function handleTradeUpdate(data) {
    console.log('Trade update received:', data);
    // Refresh trade history when a trade closes
    updateTradeHistory();
    // Also refresh positions and capital
    updatePositions();
    updateCapitalDisplay();
}

function handlePnLUpdate(data) {
    console.log('P&L update received:', data);
    
    // Update daily P&L display
    const pnl = data.daily_pnl || 0;
    const pnlPercent = data.daily_pnl_percent || 0;
    
    // Add to chart (or update existing minute)
    const now = new Date();
    const currentTime = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
    
    const existingIndex = pnlData.findIndex(d => d.time === currentTime);
    if (existingIndex >= 0) {
        pnlData[existingIndex].pnl = pnl;
    } else {
        pnlData.push({
            time: currentTime,
            pnl: pnl
        });
        
        if (pnlData.length > 200) {
            pnlData.shift();
        }
    }
    
    updatePnLChart();
    
    // Update display
    const container = document.getElementById('daily-pnl');
    const pnlClass = pnl >= 0 ? 'positive' : 'negative';
    
    container.innerHTML = `
        <div class="metric">
            <div class="metric-label">Today's P&L</div>
            <div class="metric-value ${pnlClass}">
                ${pnl >= 0 ? '+' : ''}₹${pnl.toFixed(2)}
            </div>
        </div>
        <div class="metric">
            <div class="metric-label">Return %</div>
            <div class="metric-value ${pnlClass}">
                ${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%
            </div>
        </div>
    `;
}

function handleCircuitBreakerEvent(data) {
    console.warn('Circuit breaker event:', data);
    
    // Show alert notification
    const event = data.event || 'unknown';
    const reason = data.reason || '';
    
    showNotification(
        `Circuit Breaker ${event.toUpperCase()}${reason ? ': ' + reason : ''}`,
        'warning'
    );
    
    // Refresh status
    updateSystemStatus();
}

function handleAlert(data) {
    const level = data.level || 'info';
    const message = data.message || '';
    
    console.log(`Alert [${level}]:`, message);
    
    showNotification(message, level);
}

function handleMarketConditionUpdate(data) {
    console.log('Market condition update:', data);
    updateMarketConditionDisplay(data);
}

function handleDataQualityUpdate(data) {
    console.log('Data quality update:', data);
    // Could update data quality display in real-time
}

function handleSystemStatusUpdate(data) {
    console.log('System status update:', data);
    // Full system status update - could refresh all displays
    if (data.market_condition) {
        updateMarketConditionDisplay(data.market_condition);
    }
}

// Notification System
function showNotification(message, level = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${level}`;
    notification.innerHTML = `
        <div class="notification-content">
            <strong>${level.toUpperCase()}</strong>: ${message}
        </div>
        <button onclick="this.parentElement.remove()" class="notification-close">×</button>
    `;
    
    // Add to page
    let container = document.getElementById('notifications-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notifications-container';
        container.style.cssText = 'position: fixed; top: 80px; right: 20px; z-index: 10000; width: 400px;';
        document.body.appendChild(container);
    }
    
    container.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// Auto-refresh control (fallback when WebSocket is unavailable)
function startAutoRefresh() {
    if (refreshInterval) return; // Don't start if already running
    
    refreshInterval = setInterval(() => {
        // Only poll if WebSocket is not connected
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            refreshData();
        }
    }, REFRESH_INTERVAL);
    
    console.log(`Auto-refresh started (every ${REFRESH_INTERVAL/1000}s) - Fallback mode`);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
        console.log('Auto-refresh stopped - WebSocket active');
    }
}

// Main data refresh function
async function refreshData() {
    try {
        updateConnectionStatus(true);
        
        // Call each function independently with error handling
        // This prevents one failure from blocking others
        const promises = [
            updateMarketOverview().catch(err => console.error('Market overview failed:', err)),
            updateOptionChainData().catch(err => console.error('Option chain failed:', err)),
            updateWatchlist().catch(err => console.error('Watchlist failed:', err)),
            updateTradeHistory().catch(err => console.error('Trade history failed:', err)),
            updateSystemStatus().catch(err => console.error('System status failed:', err)),
            updatePositions().catch(err => console.error('Positions failed:', err)),
            updateRiskMetrics().catch(err => console.error('Risk metrics failed:', err)),
            updateCapitalInfo().catch(err => console.error('Capital info failed:', err))
        ];
        
        await Promise.allSettled(promises);
        
    } catch (error) {
        console.error('Error refreshing data:', error);
        updateConnectionStatus(false);
    }
}

// Update system time display (IST)
function updateSystemTime() {
    const now = new Date();
    const istOptions = {
        timeZone: 'Asia/Kolkata',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    };
    const istDateOptions = {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    };
    
    const timeString = now.toLocaleTimeString('en-IN', istOptions);
    const dateString = now.toLocaleDateString('en-IN', istDateOptions);
    
    const systemTimeElement = document.getElementById('system-time');
    if (systemTimeElement) {
        systemTimeElement.textContent = `${dateString} ${timeString} IST`;
    }
}

// Update connection status
function updateConnectionStatus(connected) {
    const statusDiv = document.getElementById('connection-status');
    const dot = statusDiv.querySelector('.status-dot');
    const text = statusDiv.querySelector('.status-text');
    
    if (connected) {
        dot.classList.remove('disconnected');
        text.textContent = 'Connected';
    } else {
        dot.classList.add('disconnected');
        text.textContent = 'Disconnected';
    }
}

// Check trade engine status
async function checkEngineStatus() {
    // Skip if a check is already in progress
    if (engineStatusCheckInProgress) {
        console.log('⏭️ Skipping engine status check (previous check still in progress)');
        return false;
    }
    
    engineStatusCheckInProgress = true;
    
    try {
        // Add cache-busting and increased timeout to 10 seconds
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 10000);
        
        const response = await fetch(`${API_BASE_URL}/api/health?t=${Date.now()}`, {
            signal: controller.signal,
            cache: 'no-store'
        });
        clearTimeout(timeout);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        const isRunning = data.trading_active === true;
        const engineDot = document.getElementById('engine-status-dot');
        const engineBtn = document.getElementById('engine-control-btn');
        
        console.log(`✅ Engine status check: ${isRunning ? 'RUNNING' : 'STOPPED'}`);
        
        if (engineDot) {
            engineDot.className = isRunning ? 'quality-dot green' : 'quality-dot red';
            engineDot.title = `Trade Engine: ${isRunning ? 'Running' : 'Stopped'}`;
        }
        
        if (engineBtn) {
            if (isRunning) {
                engineBtn.style.display = 'none';
            } else {
                engineBtn.style.display = 'inline-flex';
                engineBtn.innerHTML = '▶️ Start';
            }
        }
        
        return isRunning;
    } catch (error) {
        // Silently handle AbortError (timeouts) to reduce console noise
        if (error.name === 'AbortError') {
            console.warn('⏱️ Engine status check timed out (network slow or backend busy)');
        } else {
            console.error('❌ Error checking engine status:', error);
        }
        
        const engineDot = document.getElementById('engine-status-dot');
        const engineBtn = document.getElementById('engine-control-btn');
        
        if (engineDot) {
            engineDot.className = 'quality-dot yellow';
            engineDot.title = 'Trade Engine: Status Unknown';
        }
        
        if (engineBtn) {
            engineBtn.style.display = 'inline-flex';
            engineBtn.innerHTML = '🔄 Retry';
        }
        
        return false;
    } finally {
        engineStatusCheckInProgress = false;
    }
}

// Toggle trading engine (start/restart)
async function toggleTradingEngine() {
    const btn = document.getElementById('engine-control-btn');
    if (!btn) return;
    
    const originalContent = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '⏳ Starting...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/trading/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'success' || data.status === 'info') {
            showNotification(data.message || 'Trading engine started', 'success');
            
            // Check status after a short delay
            setTimeout(async () => {
                await checkEngineStatus();
                btn.disabled = false;
            }, 2000);
        } else {
            throw new Error(data.message || 'Failed to start engine');
        }
    } catch (error) {
        console.error('Error starting trade engine:', error);
        showNotification(`Failed to start engine: ${error.message}`, 'error');
        btn.innerHTML = originalContent;
        btn.disabled = false;
    }
}

// Fetch system status
async function updateSystemStatus() {
    try {
        const response = await fetch(`${API_BASE}/paper_trading_status.json`);
        const data = await response.json();
        
        // The paper_trading_status.json endpoint returns data directly, not wrapped in status/data
        if (data) {
            // Update market status
            const marketStatusElement = document.getElementById('market-status');
            if (marketStatusElement) {
                marketStatusElement.textContent = data.market_status || 'unknown';
            }
            
            // Update system status badge based on market status
            const isMarketOpen = data.market_status === 'open';
            updateStatusBadge(isMarketOpen);
        }
        
    } catch (error) {
        console.error('Error fetching system status:', error);
    }
}

// Update market condition display (now uses live VIX data from market overview)
function updateMarketConditionDisplay(mc) {
    const container = document.getElementById('market-condition');
    if (!container) return; // Element removed, skip update
    
    // This will be updated by updateMarketOverview() with real VIX data
    // Keeping this function for system status integration
    const condition = mc.condition || 'unknown';
    const vix = mc.current_vix || 0;
    const halted = mc.is_market_halted || false;
    
    // Only update if we have real data from system status
    if (vix > 0 || halted) {
        let haltedHTML = '';
        if (halted) {
            haltedHTML = '<div class="condition-badge extreme">🚫 MARKET HALTED</div>';
        }
        
        container.innerHTML = `
            ${haltedHTML}
            <div class="condition-badge ${condition}">
                ${condition.toUpperCase().replace('_', ' ')}
            </div>
            <div class="metric">
                <div class="metric-label">VIX Level</div>
                <div class="metric-value">${vix.toFixed(2)}</div>
            </div>
        `;
    }
}

// Update daily P&L display
function updateDailyPnLDisplay(cb) {
    const container = document.getElementById('daily-pnl');
    if (!container) return; // Element removed, skip update
    
    const pnl = cb.daily_loss || 0;
    const pnlPercent = cb.daily_loss_percent || 0;
    const pnlClass = pnl >= 0 ? 'positive' : 'negative';
    
    // Add to chart data (or update existing minute)
    const now = new Date();
    const currentTime = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
    
    const existingIndex = pnlData.findIndex(d => d.time === currentTime);
    if (existingIndex >= 0) {
        pnlData[existingIndex].pnl = pnl;
    } else {
        pnlData.push({
            time: currentTime,
            pnl: pnl
        });
        
        if (pnlData.length > 200) {
            pnlData.shift();
        }
    }
    
    // Update chart
    updatePnLChart();
    
    container.innerHTML = `
        <div class="metric">
            <div class="metric-label">Today's P&L</div>
            <div class="metric-value ${pnlClass}">
                ${pnl >= 0 ? '+' : ''}₹${pnl.toFixed(2)}
            </div>
        </div>
        <div class="metric">
            <div class="metric-label">Return %</div>
            <div class="metric-value ${pnlClass}">
                ${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%
            </div>
        </div>
    `;
}

// Update status badge
function updateStatusBadge(isMarketOpen) {
    const badge = document.getElementById('status-badge');
    
    if (isMarketOpen) {
        badge.className = 'status-badge trading';
        badge.textContent = 'Trading Active';
        badge.title = 'Market is open and trading is active';
    } else {
        badge.className = 'status-badge stopped';
        badge.textContent = 'Market Closed';
        badge.title = 'Trading hours: 9:15 AM - 3:30 PM IST, Mon-Fri';
    }
}

// Fetch and update positions
async function updatePositions() {
    try {
        // Add cache-busting to ensure real-time prices
        const response = await fetch(`${API_BASE_URL}/api/dashboard/positions?t=${Date.now()}`, {
            cache: 'no-store'
        });
        const data = await response.json();
        
        if (data.status === 'success') {
            const positions = (data.data && data.data.positions) || [];
            displayPositions(positions);
        }
        
    } catch (error) {
        console.error('Error fetching positions:', error);
        showError('positions-table', 'Failed to load positions');
    }
}

// Display positions table
function displayPositions(positions) {
    const container = document.getElementById('positions-table');
    
    if (positions.length === 0) {
        container.innerHTML = '<div class="no-data">No open positions</div>';
        return;
    }
    
    const tableHTML = `
        <table class="positions-table">
            <thead>
                <tr>
                    <th>Option</th>
                    <th>Strike</th>
                    <th>Type</th>
                    <th>Qty</th>
                    <th>Entry</th>
                    <th>Current</th>
                    <th>SL</th>
                    <th>T1</th>
                    <th>T2</th>
                    <th>T3</th>
                    <th>P&L</th>
                    <th>P&L %</th>
                    <th>Strategy</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${positions.map(pos => {
                    const optionType = pos.option_type || '—';
                    const strike = pos.strike_price > 0 ? pos.strike_price : '—';
                    const sl = pos.stop_loss > 0 ? `₹${pos.stop_loss.toFixed(2)}` : '—';
                    const t1 = pos.target_1 > 0 ? `₹${pos.target_1.toFixed(2)}` : '—';
                    const t2 = pos.target_2 > 0 ? `₹${pos.target_2.toFixed(2)}` : '—';
                    const t3 = pos.target_3 > 0 ? `₹${pos.target_3.toFixed(2)}` : '—';
                    
                    // Color coding for option type
                    const typeColor = optionType === 'CE' ? 'style="color: #10b981; font-weight: 600;"' : 
                                     optionType === 'PE' ? 'style="color: #ef4444; font-weight: 600;"' : '';
                    
                    // Calculate target progress
                    let targetProgress = '';
                    const currentPrice = pos.current_price;
                    if (pos.target_1 > 0) {
                        const progress1 = ((currentPrice - pos.entry_price) / (pos.target_1 - pos.entry_price) * 100);
                        const progress2 = pos.target_2 > 0 ? ((currentPrice - pos.entry_price) / (pos.target_2 - pos.entry_price) * 100) : 0;
                        const progress3 = pos.target_3 > 0 ? ((currentPrice - pos.entry_price) / (pos.target_3 - pos.entry_price) * 100) : 0;
                        
                        if (progress1 >= 100) targetProgress = '✓ T1';
                        if (progress2 >= 100) targetProgress = '✓✓ T2';
                        if (progress3 >= 100) targetProgress = '✓✓✓ T3';
                    }
                    
                    return `
                    <tr>
                        <td><strong>${pos.symbol}</strong> ${targetProgress ? `<span style="color: #10b981; font-size: 0.85rem;">${targetProgress}</span>` : ''}</td>
                        <td style="font-weight: 600;">${strike}</td>
                        <td ${typeColor}>${optionType}</td>
                        <td>${pos.quantity}</td>
                        <td>₹${pos.entry_price.toFixed(2)}</td>
                        <td style="font-weight: 600;">₹${pos.current_price.toFixed(2)}</td>
                        <td style="font-size: 0.85rem; color: ${pos.stop_loss > 0 ? '#ef4444' : 'var(--text-secondary)'}">${sl}</td>
                        <td style="font-size: 0.85rem; color: ${pos.target_1 > 0 ? '#10b981' : 'var(--text-secondary)'}">${t1}</td>
                        <td style="font-size: 0.85rem; color: ${pos.target_2 > 0 ? '#10b981' : 'var(--text-secondary)'}">${t2}</td>
                        <td style="font-size: 0.85rem; color: ${pos.target_3 > 0 ? '#10b981' : 'var(--text-secondary)'}">${t3}</td>
                        <td class="${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}" style="font-weight: 600;">
                            ₹${pos.unrealized_pnl.toFixed(2)}
                        </td>
                        <td class="${pos.pnl_percent >= 0 ? 'positive' : 'negative'}" style="font-weight: 600;">
                            ${pos.pnl_percent >= 0 ? '+' : ''}${pos.pnl_percent.toFixed(2)}%
                        </td>
                        <td style="font-size: 0.8rem; color: var(--text-secondary);">${pos.strategy || '—'}</td>
                        <td>
                            <button class="btn btn-sm btn-danger" onclick="closePosition('${pos.id}')" title="Close Position">
                                ✕
                            </button>
                        </td>
                    </tr>
                `}).join('')}
            </tbody>
        </table>
    `;
    
    container.innerHTML = tableHTML;
}

// Fetch and update risk metrics with real-time data
async function updateRiskMetrics() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/dashboard/risk-metrics`);
        const data = await response.json();
        
        if (data.status === 'success' && data.data) {
            displayRiskMetrics(data.data);
        }
        
    } catch (error) {
        console.error('Error fetching risk metrics:', error);
        // Show default values on error
        displayRiskMetrics({
            daily_pnl: 0,
            win_rate: 0,
            total_trades: 0,
            max_drawdown: 0,
            capital_utilization: 0,
            largest_position_percent: 0,
            total_unrealized_pnl: 0
        });
    }
}

// Display risk metrics with real-time data
function displayRiskMetrics(metrics) {
    // Update individual metric elements with correct field names
    document.getElementById('daily-pnl').textContent = `₹${(metrics.daily_pnl || 0).toLocaleString('en-IN')}`;
    document.getElementById('profit-percentage').textContent = `${(metrics.daily_pnl_percent || 0).toFixed(2)}%`;
    document.getElementById('win-rate').textContent = `${(metrics.win_rate || 0).toFixed(1)}%`;
    document.getElementById('drawdown').textContent = `${(metrics.max_drawdown || 0).toFixed(2)}%`;
    
    // Update capital utilization if available
    const capitalUtilEl = document.getElementById('session-vwap');
    if (capitalUtilEl) {
        const util = metrics.capital_utilization || 0;
        capitalUtilEl.textContent = `${util.toFixed(1)}% utilized`;
    }
    
    // Update total trades
    const tradesEl = document.getElementById('iv-rank');
    if (tradesEl) {
        tradesEl.textContent = `${metrics.total_trades || 0} trades`;
    }
    
    // Color code the metrics
    const dailyPnlEl = document.getElementById('daily-pnl');
    if (dailyPnlEl && metrics.daily_pnl !== undefined) {
        dailyPnlEl.className = metrics.daily_pnl >= 0 ? 'metric-value success' : 'metric-value danger';
    }
    
    const profitPctEl = document.getElementById('profit-percentage');
    if (profitPctEl && metrics.daily_pnl_percent !== undefined) {
        profitPctEl.className = metrics.daily_pnl_percent >= 0 ? 'metric-value success' : 'metric-value danger';
    }
    
    const winRateEl = document.getElementById('win-rate');
    if (winRateEl && metrics.win_rate !== undefined) {
        winRateEl.className = metrics.win_rate >= 60 ? 'metric-value success' : 
                             metrics.win_rate >= 40 ? 'metric-value warning' : 'metric-value danger';
    }
    
    const drawdownEl = document.getElementById('drawdown');
    if (drawdownEl && metrics.max_drawdown !== undefined) {
        drawdownEl.className = metrics.max_drawdown <= 2 ? 'metric-value success' : 
                              metrics.max_drawdown <= 5 ? 'metric-value warning' : 'metric-value danger';
    }
}

// Fetch and update data quality
async function updateDataQuality() {
    try {
        const response = await fetch(`${API_BASE}/data-quality`);
        const data = await response.json();
        
        if (data.status === 'success') {
            displayDataQuality(data.report);
        }
        
    } catch (error) {
        console.error('Error fetching data quality:', error);
        showError('data-quality', 'Failed to load data quality');
    }
}

// Display data quality
function displayDataQuality(report) {
    const container = document.getElementById('data-quality');
    
    const overall = report.overall_quality || 'unknown';
    const qualityClass = overall === 'excellent' ? 'excellent' : 
                        overall === 'good' ? 'good' : 'poor';
    
    let symbolsHTML = '';
    if (report.symbols) {
        symbolsHTML = Object.entries(report.symbols).map(([symbol, data]) => `
            <div class="quality-item">
                <div>
                    <strong>${symbol}</strong><br>
                    <small>${data.age_seconds?.toFixed(1) || '0.0'}s old</small>
                </div>
                <div class="quality-score ${data.is_stale ? 'poor' : 'excellent'}">
                    ${data.is_stale ? '❌ Stale' : '✓ Fresh'}
                </div>
            </div>
        `).join('');
    }
    
    container.innerHTML = `
        <div class="metric">
            <div class="metric-label">Overall Quality</div>
            <div class="quality-score ${qualityClass}">
                ${overall.toUpperCase()}
            </div>
        </div>
        <div class="quality-display">
            ${symbolsHTML}
        </div>
    `;
}

// Initialize P&L Chart
function initializePnLChart() {
    const ctx = document.getElementById('pnl-chart').getContext('2d');
    
    pnlChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'P&L (₹)',
                data: [],
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: {
                        color: '#2d3748'
                    },
                    ticks: {
                        color: '#8b939d',
                        maxTicksLimit: 10
                    }
                },
                y: {
                    display: true,
                    grid: {
                        color: '#2d3748'
                    },
                    ticks: {
                        color: '#8b939d',
                        callback: function(value) {
                            return '₹' + value.toFixed(0);
                        }
                    }
                }
            }
        }
    });
}

// Load historical intraday P&L data from backend
async function loadIntradayPnLHistory() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/capital/intraday-pnl`);
        if (!response.ok) {
            console.warn('Could not fetch intraday P&L history');
            return;
        }
        
        const result = await response.json();
        
        if (result.status === 'success' && result.data && result.data.length > 0) {
            // Clear existing data and populate with historical data
            pnlData = [];
            
            for (const point of result.data) {
                pnlData.push({
                    time: point.time,
                    pnl: point.cumulative_pnl
                });
            }
            
            // Update chart with historical data
            updatePnLChart();
            
            console.log(`✓ Loaded ${pnlData.length} intraday P&L data points from ${result.market_open}`);
        }
    } catch (error) {
        console.error('Error loading intraday P&L history:', error);
    }
}

// Update P&L Chart
function updatePnLChart() {
    if (!pnlChart) return;
    
    pnlChart.data.labels = pnlData.map(d => d.time);
    pnlChart.data.datasets[0].data = pnlData.map(d => d.pnl);
    
    // Update line color based on current P&L
    const currentPnL = pnlData.length > 0 ? pnlData[pnlData.length - 1].pnl : 0;
    if (currentPnL >= 0) {
        pnlChart.data.datasets[0].borderColor = '#10b981';
        pnlChart.data.datasets[0].backgroundColor = 'rgba(16, 185, 129, 0.1)';
    } else {
        pnlChart.data.datasets[0].borderColor = '#ef4444';
        pnlChart.data.datasets[0].backgroundColor = 'rgba(239, 68, 68, 0.1)';
    }
    
    pnlChart.update('none');  // Update without animation
}

// Emergency stop modal
function showEmergencyStopModal() {
    document.getElementById('emergency-modal').classList.add('show');
}

// Execute emergency stop
async function executeEmergencyStop() {
    const reason = document.getElementById('emergency-reason').value;
    const password = document.getElementById('emergency-password').value;
    
    if (!reason) {
        alert('Please enter a reason');
        return;
    }
    
    if (!password) {
        alert('Please enter the emergency password');
        return;
    }
    
    if (!confirm('Are you sure you want to STOP ALL TRADING?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/stop`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({ reason, password })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            alert('✓ Emergency stop activated');
            closeModal('emergency-modal');
            refreshData();
        } else {
            alert('Error: ' + (data.message || 'Unknown error'));
        }
        
    } catch (error) {
        alert('Error executing emergency stop: ' + error.message);
    }
}

// Reset circuit breaker
async function resetCircuitBreaker() {
    const reason = prompt('Enter reason for reset:');
    if (!reason) return;
    
    const password = prompt('Enter password:');
    if (!password) return;
    
    try {
        const response = await fetch(`${API_BASE}/emergency/circuit-breaker/reset`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({ reason, password })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            alert('✓ Circuit breaker reset');
            refreshData();
        } else {
            alert('Error: ' + (data.message || 'Unknown error'));
        }
        
    } catch (error) {
        alert('Error resetting circuit breaker: ' + error.message);
    }
}

// Close position
async function closePosition(positionId) {
    if (!confirm('Close this position?')) return;
    
    const reason = prompt('Enter reason:');
    if (!reason) return;
    
    try {
        const response = await fetch(`${API_BASE}/positions/close`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({ 
                position_id: positionId,
                reason 
            })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            alert('✓ Position closed');
            refreshData();
        } else {
            alert('Error: ' + (data.message || 'Unknown error'));
        }
        
    } catch (error) {
        alert('Error closing position: ' + error.message);
    }
}

// Close all positions
async function closeAllPositions() {
    if (!confirm('Close ALL positions? This cannot be undone!')) return;
    
    const reason = prompt('Enter reason for closing all positions:');
    if (!reason) return;
    
    try {
        const response = await fetch(`${API_BASE}/positions/close`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({ 
                close_all: true,
                reason 
            })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            alert('✓ All positions closed');
            refreshData();
        } else {
            alert('Error: ' + (data.message || 'Unknown error'));
        }
        
    } catch (error) {
        alert('Error closing positions: ' + error.message);
    }
}

// Manual order modal
function showManualOrderModal() {
    document.getElementById('manual-order-modal').classList.add('show');
}

// Place manual order
async function placeManualOrder() {
    const symbol = document.getElementById('manual-symbol').value;
    const side = document.getElementById('manual-side').value;
    const quantity = parseInt(document.getElementById('manual-quantity').value);
    const price = parseFloat(document.getElementById('manual-price').value);
    const reason = document.getElementById('manual-reason').value;
    
    if (!reason) {
        alert('Please enter a reason');
        return;
    }
    
    if (!confirm(`Place ${side} order for ${quantity} ${symbol} @ ₹${price}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/manual-order`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({
                symbol,
                quantity,
                price,
                side,
                order_type: 'LIMIT',
                reason
            })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            alert('✓ Manual order placed: ' + data.order_id);
            closeModal('manual-order-modal');
            refreshData();
        } else {
            alert('Error: ' + (data.message || 'Unknown error'));
        }
        
    } catch (error) {
        alert('Error placing manual order: ' + error.message);
    }
}

// Enable override mode
async function enableOverride() {
    const reason = prompt('Enter reason for enabling override mode:');
    if (!reason) return;
    
    const password = prompt('Enter override password:');
    if (!password) return;
    
    if (!confirm('⚠️ WARNING: Override mode bypasses safety checks. Continue?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/override/enable`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({ reason, password })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            alert('⚠️ Override mode enabled');
            refreshData();
        } else {
            alert('Error: ' + (data.message || 'Unknown error'));
        }
        
    } catch (error) {
        alert('Error enabling override: ' + error.message);
    }
}

// Show logs modal
function showLogsModal() {
    document.getElementById('logs-modal').classList.add('show');
    loadRecentLogs();
}

// Load recent logs
async function loadRecentLogs() {
    try {
        const response = await fetch(`${API_BASE}/logs/recent?lines=50`, {
            headers: {
                'X-API-Key': API_KEY
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            displayLogs(data.logs);
        }
        
    } catch (error) {
        console.error('Error loading logs:', error);
        document.getElementById('logs-container').innerHTML = 
            '<div class="error">Failed to load logs</div>';
    }
}

// Display logs
function displayLogs(logs) {
    const container = document.getElementById('logs-container');
    
    if (logs.length === 0) {
        container.innerHTML = '<div class="no-data">No logs available</div>';
        return;
    }
    
    const logsHTML = logs.map(log => `
        <div class="log-entry ${log.level.toLowerCase()}">
            <div><strong>${log.timestamp}</strong> [${log.level}]</div>
            <div>${log.message}</div>
        </div>
    `).join('');
    
    container.innerHTML = logsHTML;
}

// Close modal
window.closeModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    }
}

// Show error message
function showError(containerId, message) {
    const container = document.getElementById(containerId);
    container.innerHTML = `<div class="error">${message}</div>`;
}

// Utility functions
function formatCurrency(value) {
    return '₹' + value.toFixed(2);
}

function formatPercent(value) {
    return (value >= 0 ? '+' : '') + value.toFixed(2) + '%';
}

// ============================================================================
// TRADE HISTORY
// ============================================================================

async function updateTradeHistory() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/trades/history?limit=10`);
        const data = await response.json();
        
        if (data.trades && data.trades.length > 0) {
            displayTradeHistory(data.trades);
        } else {
            const container = document.getElementById('recent-trades');
            if (container) {
                container.innerHTML = '<div class="no-data">No recent trades</div>';
            }
        }
        
    } catch (error) {
        console.error('Error fetching trade history:', error);
        const container = document.getElementById('recent-trades');
        if (container) {
            container.innerHTML = '<div class="error">Error loading trade history</div>';
        }
    }
}

function displayTradeHistory(trades) {
    const container = document.getElementById('recent-trades');
    if (!container) return;
    
    const tradesHTML = trades.map(trade => {
        const pnlClass = trade.net_pnl >= 0 ? 'positive' : 'negative';
        const pnlSign = trade.net_pnl >= 0 ? '+' : '';
        const isWinning = trade.is_winning_trade ? '✓' : '✗';
        
        return `
            <div class="trade-item">
                <div class="trade-header">
                    <strong>${trade.symbol} ${trade.instrument_type} ${trade.strike_price}</strong>
                    <span class="trade-outcome ${trade.is_winning_trade ? 'win' : 'loss'}">${isWinning}</span>
                </div>
                <div class="trade-details">
                    <span>Entry: ₹${trade.entry_price.toFixed(2)}</span>
                    <span>Exit: ₹${trade.exit_price ? trade.exit_price.toFixed(2) : '--'}</span>
                    <span class="trade-pnl ${pnlClass}">P&L: ${pnlSign}₹${trade.net_pnl.toFixed(2)}</span>
                </div>
                <div class="trade-meta">
                    <small>${new Date(trade.entry_time).toLocaleString()}</small>
                    <small>${trade.strategy_name}</small>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = tradesHTML;
}

// ============================================================================
// CAPITAL INFORMATION
// ============================================================================

async function updateCapitalInfo() {
    try {
        const response = await fetch(`${API_BASE}/paper_trading_status.json`);
        const data = await response.json();
        
        if (data) {
            displayCapitalInfo(data);
        }
        
    } catch (error) {
        console.error('Error fetching capital info:', error);
        // Don't show error for capital info, just use defaults
    }
}

function displayCapitalInfo(capital) {
    const startingCapitalEl = document.getElementById('starting-capital');
    const currentCapitalEl = document.getElementById('current-capital');
    const todayPnlEl = document.getElementById('today-pnl');
    const todayPnlPctEl = document.getElementById('today-pnl-pct');
    const totalPnlEl = document.getElementById('total-pnl');
    const totalPnlPctEl = document.getElementById('total-pnl-pct');
    
    if (startingCapitalEl) {
        startingCapitalEl.textContent = `₹${(capital.initial_capital || capital.capital || 100000).toLocaleString('en-IN')}`;
    }
    
    if (currentCapitalEl) {
        currentCapitalEl.textContent = `₹${(capital.capital || capital.current_capital || 100000).toLocaleString('en-IN')}`;
    }
    
    // Calculate today's P&L (assuming total_pnl includes today's P&L for now)
    const todaysPnl = capital.total_pnl || capital.last_pnl || 0;
    const startingCapital = capital.initial_capital || capital.capital || 100000;
    const todaysPnlPct = startingCapital > 0 ? (todaysPnl / startingCapital) * 100 : 0;
    
    if (todayPnlEl) {
        todayPnlEl.textContent = `${todaysPnl >= 0 ? '+' : ''}₹${Math.abs(todaysPnl).toLocaleString('en-IN')}`;
        todayPnlEl.className = todaysPnl >= 0 ? 'capital-value pnl-value positive' : 'capital-value pnl-value negative';
    }
    
    if (todayPnlPctEl) {
        todayPnlPctEl.textContent = `(${todaysPnl >= 0 ? '+' : ''}${todaysPnlPct.toFixed(2)}%)`;
        todayPnlPctEl.className = todaysPnl >= 0 ? 'pnl-percentage positive' : 'pnl-percentage negative';
    }
    
    // For total P&L, use same as today's for now (can be enhanced later)
    if (totalPnlEl) {
        totalPnlEl.textContent = `${todaysPnl >= 0 ? '+' : ''}₹${Math.abs(todaysPnl).toLocaleString('en-IN')}`;
        totalPnlEl.className = todaysPnl >= 0 ? 'capital-value pnl-value positive' : 'capital-value pnl-value negative';
    }
    
    if (totalPnlPctEl) {
        totalPnlPctEl.textContent = `(${todaysPnl >= 0 ? '+' : ''}${todaysPnlPct.toFixed(2)}%)`;
        totalPnlPctEl.className = todaysPnl >= 0 ? 'pnl-percentage positive' : 'pnl-percentage negative';
    }
}

function fetchUpstoxToken() {
    // Show the token modal
    document.getElementById('token-modal').classList.add('show');
    
    // Check current token status
    checkTokenStatus();
}

async function checkTokenStatus() {
    try {
        const response = await fetch('http://localhost:8000/api/upstox/token/status');
        if (response.ok) {
            const data = await response.json();
            const tokenInfo = document.getElementById('token-info');
            const tokenAge = document.getElementById('token-age');
            const tokenStatus = document.getElementById('token-status-text');
            
            tokenInfo.style.display = 'block';
            
            if (data.status === 'valid') {
                const remainingHours = Math.max(0, 24 - data.age_hours);
                tokenAge.textContent = `${data.age_hours}h old, ${remainingHours.toFixed(1)}h remaining`;
                tokenStatus.textContent = '✅ Valid';
                tokenStatus.style.color = 'green';
            } else if (data.status === 'expired') {
                tokenAge.textContent = `${data.age_hours}h old (expired)`;
                tokenStatus.textContent = '⚠️ Expired';
                tokenStatus.style.color = 'orange';
            } else if (data.status === 'missing') {
                tokenAge.textContent = 'No token found';
                tokenStatus.textContent = '❌ Not Found';
                tokenStatus.style.color = 'red';
            } else {
                // Invalid or error status
                tokenAge.textContent = data.message || 'Token invalid';
                tokenStatus.textContent = '⚠️ Invalid';
                tokenStatus.style.color = 'orange';
            }
        }
    } catch (error) {
        console.error('Error checking token status:', error);
    }
}

function startTokenFetch() {
    // Open authorization in new window
    const width = 600;
    const height = 700;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    
    const authWindow = window.open(
        '',
        'Upstox Authorization',
        `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no`
    );
    
    if (authWindow) {
        authWindow.document.write(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Starting Upstox Authorization...</title>
                <style>
                    body {
                        font-family: 'Inter', sans-serif;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    }
                    .container {
                        text-align: center;
                        padding: 40px;
                        background: rgba(255, 255, 255, 0.1);
                        border-radius: 12px;
                        backdrop-filter: blur(10px);
                    }
                    .spinner {
                        border: 4px solid rgba(255, 255, 255, 0.3);
                        border-top: 4px solid white;
                        border-radius: 50%;
                        width: 50px;
                        height: 50px;
                        animation: spin 1s linear infinite;
                        margin: 20px auto;
                    }
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                    .info {
                        margin-top: 20px;
                        font-size: 14px;
                        opacity: 0.9;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <h2>🔐 Starting Authorization Server...</h2>
                    <div class="spinner"></div>
                    <p class="info">Please wait while we prepare the authorization flow.</p>
                    <p class="info">This window will redirect to Upstox login shortly.</p>
                </div>
                <script>
                    // Trigger the backend to start auth server and get URL
                    fetch('http://localhost:8000/api/upstox/token/start-auth', {
                        method: 'POST'
                    })
                        .then(response => response.json())
                        .then(data => {
                            if (data.auth_url) {
                                // Redirect to Upstox authorization
                                window.location.href = data.auth_url;
                            } else {
                                document.body.innerHTML = '<div class="container"><h2>❌ Error</h2><p>' + (data.error || 'Failed to start authorization') + '</p></div>';
                            }
                        })
                        .catch(error => {
                            document.body.innerHTML = '<div class="container"><h2>❌ Error</h2><p>Failed to connect to backend: ' + error.message + '</p><p class="info">Make sure the backend server is running on port 8000.</p></div>';
                        });
                </script>
            </body>
            </html>
        `);
        
        // Start the auth server - it will open browser automatically
        const tokenStatus = document.getElementById('token-status');
        const modalFooter = document.querySelector('#token-modal .modal-footer');

        fetch('http://localhost:8000/api/upstox/token/start-auth', {
            method: 'POST'
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Server started and will open browser automatically
                    tokenStatus.innerHTML = `
                        <p>✅ Authorization started!</p>
                        <p class="info-text">Browser window should open automatically.</p>
                        <p class="info-text">Complete the authorization, then click "Check Status".</p>
                    `;
                } else {
                    tokenStatus.innerHTML = `
                        <p>❌ Error: ${data.message || 'Failed to start authorization'}</p>
                    `;
                }
            })
            .catch(error => {
                tokenStatus.innerHTML = `
                    <p>❌ Error connecting to backend: ${error.message}</p>
                `;
            });
        
        // Update modal status immediately
        tokenStatus.innerHTML = `
            <p>⏳ Starting authorization server...</p>
            <p class="info-text">Please wait...</p>
        `;
        
        // Add a check status button
        modalFooter.innerHTML = `
            <button class="btn btn-secondary" onclick="closeModal('token-modal')">Close</button>
            <button class="btn btn-success" onclick="checkTokenStatus()">Check Status</button>
        `;
    } else {
        alert('Please allow popups for this site to fetch the Upstox token.');
    }
}

// ============================================================================
// MARKET OVERVIEW - NIFTY, SENSEX, MARKET BREADTH, VIX
// ============================================================================

async function updateMarketOverview() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/market/overview`);
        const result = await response.json();
        
        if (result.status === 'success') {
            const data = result.data;
            
            // Update NIFTY
            displayIndexData('nifty', data.indices.NIFTY, data.is_market_open);
            
            // Update SENSEX
            displayIndexData('sensex', data.indices.SENSEX, data.is_market_open);
            
            // Update Market Breadth
            displayMarketBreadth(data.market_breadth);
            
            // Update VIX and Market Condition
            displayVIX(data.volatility);
            displayMarketConditionFromVIX(data.volatility, data.is_market_open);
            
            // Update Sector Performance
            displaySectorPerformance(data.sector_performance);
        }
    } catch (error) {
        console.error('Error fetching market overview:', error);
    }
}

function displayIndexData(indexName, data, isMarketOpen) {
    const priceEl = document.querySelector(`#${indexName}-data .index-price`);
    const changeEl = document.querySelector(`#${indexName}-data .index-change`);
    const statsEl = document.querySelector(`#${indexName}-data .index-stats`);
    const statusEl = document.getElementById(`${indexName}-market-status`);
    
    if (!priceEl || !changeEl || !statsEl || !statusEl) return;
    
    // Update price
    priceEl.textContent = `₹${data.price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    
    // Update change
    const changeSign = data.change >= 0 ? '+' : '';
    changeEl.textContent = `${changeSign}${data.change.toFixed(2)} (${changeSign}${data.change_percent.toFixed(2)}%)`;
    changeEl.className = `index-change ${data.change >= 0 ? 'positive' : 'negative'}`;
    
    // Update stats - include Max Pain if available
    let statsHtml = `
        <span>Open: <strong>₹${data.open.toLocaleString('en-IN', {maximumFractionDigits: 2})}</strong></span>
        <span>High: <strong>₹${data.high.toLocaleString('en-IN', {maximumFractionDigits: 2})}</strong></span>
        <span>Low: <strong>₹${data.low.toLocaleString('en-IN', {maximumFractionDigits: 2})}</strong></span>
    `;
    
    // Add Max Pain if available (for NIFTY and SENSEX)
    if (data.max_pain && data.max_pain > 0) {
        statsHtml += `<span class="max-pain-stat" title="Options Max Pain Strike">Max Pain: <strong>₹${data.max_pain.toLocaleString('en-IN', {maximumFractionDigits: 0})}</strong></span>`;
    }
    
    statsEl.innerHTML = statsHtml;
    
    // Update market status
    statusEl.className = `market-status ${isMarketOpen ? 'open' : 'closed'}`;
    statusEl.title = isMarketOpen ? 'Market Open' : 'Market Closed';
}

function displayMarketBreadth(breadth) {
    const advancesEl = document.getElementById('advances-count');
    const declinesEl = document.getElementById('declines-count');
    const adRatioEl = document.getElementById('ad-ratio');
    
    if (!breadth) {
        if (advancesEl) advancesEl.textContent = '—';
        if (declinesEl) declinesEl.textContent = '—';
        if (adRatioEl) {
            adRatioEl.textContent = '—';
            adRatioEl.className = 'breadth-value';
        }
        return;
    }
    
    const advances = breadth.advances ?? 0;
    const declines = breadth.declines ?? 0;
    const ratio = typeof breadth.advance_decline_ratio === 'number' ? breadth.advance_decline_ratio : null;
    
    if (advancesEl) advancesEl.textContent = advances.toLocaleString();
    if (declinesEl) declinesEl.textContent = declines.toLocaleString();
    if (adRatioEl) {
        adRatioEl.textContent = ratio !== null ? ratio.toFixed(2) : '—';
        adRatioEl.className = ratio !== null
            ? `breadth-value ${ratio >= 1.0 ? 'positive' : 'negative'}`
            : 'breadth-value';
    }
}

function displayVIX(vix) {
    const vixValueEl = document.querySelector('#vix-data .vix-value');
    const vixChangeEl = document.querySelector('#vix-data .vix-change');
    const vixInterpEl = document.querySelector('#vix-data .vix-interpretation');
    
    if (!vixValueEl || !vixChangeEl) return;
    
    // Check if VIX data is available
    if (!vix || vix.india_vix === null || vix.india_vix === undefined) {
        vixValueEl.textContent = '--';
        vixChangeEl.textContent = '--';
        if (vixInterpEl) vixInterpEl.textContent = '--';
        return;
    }
    
    vixValueEl.textContent = vix.india_vix.toFixed(2);
    
    const changeSign = vix.vix_change >= 0 ? '+' : '';
    vixChangeEl.textContent = `${changeSign}${vix.vix_change.toFixed(2)} (${changeSign}${vix.vix_change_percent.toFixed(2)}%)`;
    vixChangeEl.className = `vix-change ${vix.vix_change >= 0 ? 'positive' : 'negative'}`;
    
    if (vixInterpEl) {
        vixInterpEl.textContent = `${vix.interpretation} Volatility`;
    }
}

function displayMarketConditionFromVIX(vix, isMarketOpen) {
    const container = document.getElementById('market-condition');
    if (!container) return;
    
    // Determine market condition based on VIX
    let condition = 'normal';
    let conditionText = 'NORMAL';
    
    if (vix.india_vix < 12) {
        condition = 'normal';
        conditionText = 'LOW VOLATILITY';
    } else if (vix.india_vix < 16) {
        condition = 'elevated';
        conditionText = 'MODERATE';
    } else if (vix.india_vix < 22) {
        condition = 'high_stress';
        conditionText = 'ELEVATED';
    } else {
        condition = 'extreme';
        conditionText = 'HIGH STRESS';
    }
    
    const marketStatusHTML = isMarketOpen ? 
        '<div style="font-size: 0.75rem; color: var(--success); margin-bottom: 0.5rem;">● Market Open</div>' :
        '<div style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.5rem;">● Market Closed</div>';
    
    container.innerHTML = `
        ${marketStatusHTML}
        <div class="condition-badge ${condition}">
            ${conditionText}
        </div>
        <div class="metric">
            <div class="metric-label">VIX Level</div>
            <div class="metric-value">${vix.india_vix.toFixed(2)}</div>
        </div>
        <div class="metric">
            <div class="metric-label">VIX Change</div>
            <div class="metric-value ${vix.vix_change >= 0 ? 'positive' : 'negative'}">
                ${vix.vix_change >= 0 ? '+' : ''}${vix.vix_change.toFixed(2)}
            </div>
        </div>
    `;
}

function displaySectorPerformance(sectors) {
    const container = document.getElementById('sector-performance');
    if (!container) return;
    
    // Convert to array and sort by performance
    const sectorArray = Object.entries(sectors).map(([key, data]) => ({
        name: key,
        symbol: data.symbol,
        change: data.change_percent
    }));
    
    sectorArray.sort((a, b) => b.change - a.change);
    
    let sectorsHTML = '';
    sectorArray.forEach(sector => {
        const changeClass = sector.change >= 0 ? 'positive' : 'negative';
        const changeSign = sector.change >= 0 ? '+' : '';
        
        sectorsHTML += `
            <div class="sector-item">
                <div class="sector-info">
                    <span class="sector-name">${sector.name}</span>
                    <span class="sector-symbol">${sector.symbol}</span>
                </div>
                <div class="sector-change ${changeClass}">
                    ${changeSign}${sector.change.toFixed(2)}%
                </div>
            </div>
        `;
    });
    
    container.innerHTML = sectorsHTML;
}

// Fetch and display option chain data
async function updateOptionChainData() {
    try {
        // Fetch NIFTY data (option chain + institutional intelligence)
        const [niftyOCResponse, niftyWLResponse] = await Promise.all([
            fetch(`${API_BASE_URL}/api/market/option-chain/NIFTY`),
            fetch(`${API_BASE_URL}/api/watchlist/recommended-strikes?symbol=NIFTY&min_ml_score=0.0&min_strategy_strength=50&min_strategies_agree=1`)
        ]);
        
        const niftyOCData = await niftyOCResponse.json();
        const niftyWLData = await niftyWLResponse.json();
        
        if (niftyOCData.status === 'success') {
            displayOptionChain('nifty', niftyOCData.data);
        }
        
        if (niftyWLData.status === 'success' && niftyWLData.market_context) {
            displayInstitutionalIntelligence('NIFTY', niftyWLData.market_context);
        }
        
        // Fetch SENSEX data (option chain + institutional intelligence)
        const [sensexOCResponse, sensexWLResponse] = await Promise.all([
            fetch(`${API_BASE_URL}/api/market/option-chain/SENSEX`),
            fetch(`${API_BASE_URL}/api/watchlist/recommended-strikes?symbol=SENSEX&min_ml_score=0.0&min_strategy_strength=50&min_strategies_agree=1`)
        ]);
        
        const sensexOCData = await sensexOCResponse.json();
        const sensexWLData = await sensexWLResponse.json();
        
        if (sensexOCData.status === 'success') {
            displayOptionChain('sensex', sensexOCData.data);
        }
        
        if (sensexWLData.status === 'success' && sensexWLData.market_context) {
            displayInstitutionalIntelligence('SENSEX', sensexWLData.market_context);
        }
        
    } catch (error) {
        console.error('Error fetching option chain data:', error);
    }
}

function displayOptionChain(symbol, data) {
    const containerId = `${symbol}-options`;
    const expiryId = `${symbol}-expiry`;
    const container = document.getElementById(containerId);
    const expiryBadge = document.getElementById(expiryId);
    
    if (!container || !expiryBadge) return;
    
    // Format expiry date
    const expiryDate = new Date(data.expiry);
    const dayName = expiryDate.toLocaleDateString('en-US', { weekday: 'short' });
    const formattedDate = expiryDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    expiryBadge.textContent = `${dayName}, ${formattedDate}`;
    
    // Format OI values - data fields are at root level, not in analysis
    const callOI = formatLargeNumber(data.total_call_oi);
    const putOI = formatLargeNumber(data.total_put_oi);
    
    // Count strikes
    const totalStrikes = (Object.keys(data.calls || {}).length + Object.keys(data.puts || {}).length);
    
    // PCR interpretation
    const pcr = data.pcr;
    let pcrInterpretation = 'Neutral';
    let pcrClass = 'neutral';
    if (pcr > 1.2) {
        pcrInterpretation = 'Bullish';
        pcrClass = 'bullish';
    } else if (pcr < 0.8) {
        pcrInterpretation = 'Bearish';
        pcrClass = 'bearish';
    }
    
    // Display option chain summary
    const html = `
        <div class="option-stats-grid">
            <div class="option-stat">
                <div class="option-stat-label">Spot Price</div>
                <div class="option-stat-value">₹${data.spot_price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
            </div>
            <div class="option-stat">
                <div class="option-stat-label">PCR</div>
                <div class="option-stat-value ${pcrClass}">${pcr.toFixed(2)}</div>
                <div class="option-stat-hint">${pcrInterpretation}</div>
            </div>
            <div class="option-stat">
                <div class="option-stat-label">Call OI</div>
                <div class="option-stat-value">${callOI}</div>
            </div>
            <div class="option-stat">
                <div class="option-stat-label">Put OI</div>
                <div class="option-stat-value">${putOI}</div>
            </div>
            ${data.max_pain ? `
            <div class="option-stat">
                <div class="option-stat-label">Max Pain</div>
                <div class="option-stat-value">₹${data.max_pain.toLocaleString('en-IN')}</div>
            </div>
            ` : ''}
        </div>
    `;
    
    container.innerHTML = html;
}

function displayPCRAnalysis(niftyData, sensexData) {
    const container = document.getElementById('pcr-analysis');
    if (!container) return;
    
    // Average PCR - data.pcr is at root level, not in analysis
    const avgPCR = ((niftyData.pcr + sensexData.pcr) / 2).toFixed(2);
    
    // Determine interpretation
    let interpretation = 'Neutral';
    let interpretationClass = 'neutral';
    
    if (avgPCR > 1.2) {
        interpretation = 'Bullish';
        interpretationClass = 'bullish';
    } else if (avgPCR < 0.8) {
        interpretation = 'Bearish';
        interpretationClass = 'bearish';
    }
    
    // Determine individual interpretations
    const niftyInterpretation = niftyData.pcr > 1.2 ? 'Bullish' : (niftyData.pcr < 0.8 ? 'Bearish' : 'Neutral');
    const sensexInterpretation = sensexData.pcr > 1.2 ? 'Bullish' : (sensexData.pcr < 0.8 ? 'Bearish' : 'Neutral');
    
    const html = `
        <div class="pcr-meter">
            <div class="pcr-value">${avgPCR}</div>
            <div class="pcr-interpretation ${interpretationClass}">
                ${interpretation} Sentiment
            </div>
        </div>
        <div class="oi-comparison">
            <div class="oi-item">
                <div class="oi-item-label">NIFTY PCR</div>
                <div class="oi-item-value">${niftyData.pcr.toFixed(2)}</div>
                <div class="oi-item-label">${niftyInterpretation}</div>
            </div>
            <div class="oi-item">
                <div class="oi-item-label">SENSEX PCR</div>
                <div class="oi-item-value">${sensexData.pcr.toFixed(2)}</div>
                <div class="oi-item-label">${sensexInterpretation}</div>
            </div>
        </div>
    `;
    
    container.innerHTML = html;
}

// ================================
// Trade History Functions
// ================================

async function updateTradeHistory() {
    try {
        // Add cache-busting to force fresh data
        const response = await fetch(`${API_BASE_URL}/api/dashboard/trades/recent?limit=100&today_only=true&t=${Date.now()}`, {
            cache: 'no-store'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const trades = (data.data && data.data.trades) || [];
        console.log(`📊 Trade history updated: ${trades.length} trades found`);
        displayTradeHistory(trades);
        
    } catch (error) {
        console.error('Error fetching trade history:', error);
        const container = document.getElementById('recent-trades');
        if (container) {
            container.innerHTML = '<div class="error">Error loading trade history</div>';
        }
    }
}

function displayTradeHistory(trades) {
    const container = document.getElementById('recent-trades');
    if (!container) return;
    
    if (!trades || trades.length === 0) {
        container.innerHTML = `
            <div class="no-trades-message">
                <i>📭</i>
                <p>No completed trades today</p>
                <small style="color: #888; margin-top: 8px; display: block;">
                    📝 Open positions shown in "Open Positions" tab • Paper trading mode
                </small>
            </div>
        `;
        return;
    }
    
    // Build table HTML
    let html = `
        <table class="trade-history-table">
            <thead>
                <tr>
                    <th>Time</th>
                    <th>Symbol</th>
                    <th>Type</th>
                    <th>Strike</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>Qty</th>
                    <th>P&L</th>
                    <th>P&L %</th>
                    <th>Duration</th>
                    <th>Strategy</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    // Sort trades by entry time descending (newest first)
    trades.sort((a, b) => new Date(b.entry_time) - new Date(a.entry_time));
    
    trades.forEach(trade => {
        const entryTime = formatTime(trade.entry_time);
        const exitTime = trade.exit_time ? formatTime(trade.exit_time) : '-';
        
        const directionClass = trade.direction === 'CALL' ? 'call' : 'put';
        const pnl = trade.net_pnl || 0;
        const pnlClass = pnl > 0 ? 'profit' : pnl < 0 ? 'loss' : 'neutral';
        const pnlSign = pnl > 0 ? '+' : '';
        const pnlPercent = trade.pnl_percentage || 0;
        
        const statusClass = (trade.status || 'CLOSED').toLowerCase();
        const duration = formatDuration(trade.hold_duration_minutes);
        
        html += `
            <tr>
                <td>${entryTime}</td>
                <td class="trade-symbol">${trade.symbol}</td>
                <td><span class="trade-direction ${directionClass}">${trade.direction}</span></td>
                <td>${trade.strike_price}</td>
                <td class="trade-price">₹${trade.entry_price.toFixed(2)}</td>
                <td class="trade-price">${trade.exit_price ? '₹' + trade.exit_price.toFixed(2) : '-'}</td>
                <td>${trade.quantity}</td>
                <td class="trade-pnl ${pnlClass}">${pnlSign}₹${Math.abs(pnl).toFixed(2)}</td>
                <td class="trade-pnl ${pnlClass}">${pnlSign}${pnlPercent.toFixed(2)}%</td>
                <td class="trade-duration">${duration}</td>
                <td class="trade-strategy">${trade.strategy_name}</td>
                <td><span class="trade-status ${statusClass}">${trade.status}</span></td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
        </table>
    `;
    
    container.innerHTML = html;
}

// Format timestamp to IST time
function formatTime(timestamp) {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-IN', { 
        timeZone: 'Asia/Kolkata',
        hour: '2-digit', 
        minute: '2-digit',
        hour12: false
    });
}

// Format timestamp to IST date and time
function formatDateTime(timestamp) {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    const dateStr = date.toLocaleDateString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
    const timeStr = date.toLocaleTimeString('en-IN', {
        timeZone: 'Asia/Kolkata',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    });
    return `${dateStr} ${timeStr}`;
}

function formatDuration(minutes) {
    if (!minutes || minutes === 0) return '-';
    
    if (minutes < 60) {
        return `${Math.round(minutes)}m`;
    } else {
        const hours = Math.floor(minutes / 60);
        const mins = Math.round(minutes % 60);
        return `${hours}h ${mins}m`;
    }
}

async function exportTrades() {
    try {
        const today = new Date().toISOString().split('T')[0];
        const url = `${API_BASE_URL}/api/trades/export/csv?start_date=${today}`;
        
        // Open in new tab to trigger download
        window.open(url, '_blank');
    } catch (error) {
        console.error('Error exporting trades:', error);
        alert('Failed to export trades. Please try again.');
    }
}

// ================================
// Smart Watchlist Functions
// ================================

// Toggle watchlist collapse/expand (GLOBAL)
window.toggleWatchlistCollapse = function() {
    const body = document.getElementById('watchlist-body');
    const icon = document.getElementById('watchlist-collapse-icon');
    
    if (!body || !icon) return;
    
    const isCollapsed = body.style.maxHeight === '0px' || body.style.display === 'none';
    
    if (isCollapsed) {
        // Expand
        body.style.display = 'block';
        body.style.maxHeight = '2000px';  // Large enough to show content
        body.style.opacity = '1';
        icon.style.transform = 'rotate(0deg)';
        icon.textContent = '▼';
        localStorage.setItem('watchlist-collapsed', 'false');
    } else {
        // Collapse
        body.style.maxHeight = '0px';
        body.style.opacity = '0';
        icon.style.transform = 'rotate(-90deg)';
        icon.textContent = '▶';
        localStorage.setItem('watchlist-collapsed', 'true');
        
        // Hide after animation
        setTimeout(() => {
            if (body.style.maxHeight === '0px') {
                body.style.display = 'none';
            }
        }, 300);
    }
}

// Initialize watchlist collapse state from localStorage
function initWatchlistCollapse() {
    const isCollapsed = localStorage.getItem('watchlist-collapsed') === 'true';
    if (isCollapsed) {
        const body = document.getElementById('watchlist-body');
        const icon = document.getElementById('watchlist-collapse-icon');
        if (body && icon) {
            body.style.display = 'none';
            body.style.maxHeight = '0px';
            body.style.opacity = '0';
            icon.style.transform = 'rotate(-90deg)';
            icon.textContent = '▶';
        }
    }
}

async function updateWatchlist() {
    try {
        // Fetch all indices in parallel
        const symbols = ['NIFTY', 'SENSEX'];
        
        const responses = await Promise.all(
            symbols.map(symbol =>
                fetch(`${API_BASE_URL}/api/watchlist/recommended-strikes?symbol=${symbol}&min_ml_score=0.0&min_strategy_strength=50&min_strategies_agree=1`)
                    .then(res => res.json())
                    .catch(err => ({ status: 'error', symbol, error: err.message }))
            )
        );
        
        // Combine all recommendations
        const allRecommendations = [];
        
        responses.forEach(data => {
            if (data.status === 'success') {
                // Add symbol to each recommendation
                if (data.recommended_strikes) {
                    data.recommended_strikes.forEach(strike => {
                        allRecommendations.push({
                            ...strike,
                            index: data.symbol
                        });
                    });
                }
            }
        });
        
        // Display only predictive signals (table only)
        displayWatchlistTable(allRecommendations);
        
    } catch (error) {
        console.error('Error fetching watchlist:', error);
        const tableContainer = document.getElementById('watchlist-table');
        
        if (tableContainer) {
            tableContainer.innerHTML = '<div class="error">Unable to fetch recommendations</div>';
        }
    }
}

function displayWatchlistSummaryAll(marketContexts, recommendations) {
    const container = document.getElementById('watchlist-summary');
    if (!container) return;
    
    const nifty = marketContexts['NIFTY'] || {};
    const sensex = marketContexts['SENSEX'] || {};
    
    const html = `
        <div class="watchlist-stat">
            <div class="watchlist-stat-label">NIFTY</div>
            <div class="watchlist-stat-value">₹${(nifty.spot_price || 0).toLocaleString()}</div>
            <div style="font-size: 0.7rem; color: #64748b;">PCR: ${(nifty.pcr || 0).toFixed(2)}</div>
        </div>
        <div class="watchlist-stat">
            <div class="watchlist-stat-label">SENSEX</div>
            <div class="watchlist-stat-value">₹${(sensex.spot_price || 0).toLocaleString()}</div>
            <div style="font-size: 0.7rem; color: #64748b;">PCR: ${(sensex.pcr || 0).toFixed(2)}</div>
        </div>
        <div class="watchlist-stat">
            <div class="watchlist-stat-label">Total Signals</div>
            <div class="watchlist-stat-value">${recommendations.length}</div>
            <div style="font-size: 0.7rem; color: #64748b;">from 20 strategies</div>
        </div>
    `;
    
    container.innerHTML = html;
}

function displayWatchlistIntelligence(marketContexts) {
    const container = document.getElementById('watchlist-intelligence');
    if (!container) {
        // If container doesn't exist, create it before the table
        const tableContainer = document.getElementById('watchlist-table');
        if (tableContainer && tableContainer.parentElement) {
            const newContainer = document.createElement('div');
            newContainer.id = 'watchlist-intelligence';
            newContainer.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1rem; margin: 1rem 0;';
            tableContainer.parentElement.insertBefore(newContainer, tableContainer);
            return displayWatchlistIntelligence(marketContexts); // Retry with new container
        }
        return;
    }
    
    const symbols = ['NIFTY', 'SENSEX'];
    let html = '';
    
    symbols.forEach(symbol => {
        const ctx = marketContexts[symbol];
        if (!ctx) return;
        
        const sentimentColor = ctx.sentiment === 'Bullish' ? '#10b981' : 
                              ctx.sentiment === 'Bearish' ? '#ef4444' : '#f59e0b';
        
        const callOiFormatted = (ctx.total_call_oi_change / 100000).toFixed(1);
        const putOiFormatted = (ctx.total_put_oi_change / 100000).toFixed(1);
        const callOiColor = ctx.total_call_oi_change > 0 ? '#ef4444' : '#10b981';
        const putOiColor = ctx.total_put_oi_change > 0 ? '#10b981' : '#ef4444';
        
        html += `
            <div class="intelligence-card" style="background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 1rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                    <div style="font-size: 1.1rem; font-weight: 600;">${symbol === 'NIFTY' ? '📊' : '📈'} ${symbol}</div>
                    <div style="font-size: 0.9rem; padding: 4px 8px; background: ${sentimentColor}20; color: ${sentimentColor}; border-radius: 4px; font-weight: 500;">
                        ${ctx.sentiment}
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 0.75rem; font-size: 0.85rem;">
                    <div>
                        <div style="color: var(--text-secondary); font-size: 0.75rem;">Spot Price</div>
                        <div style="font-weight: 600;">₹${(ctx.spot_price || 0).toLocaleString()}</div>
                    </div>
                    <div>
                        <div style="color: var(--text-secondary); font-size: 0.75rem;">PCR</div>
                        <div style="font-weight: 600;">${(ctx.pcr || 0).toFixed(2)}</div>
                    </div>
                    <div>
                        <div style="color: var(--text-secondary); font-size: 0.75rem;">Call OI Change</div>
                        <div style="font-weight: 600; color: ${callOiColor};">${callOiFormatted}L</div>
                    </div>
                    <div>
                        <div style="color: var(--text-secondary); font-size: 0.75rem;">Put OI Change</div>
                        <div style="font-weight: 600; color: ${putOiColor};">${putOiFormatted}L</div>
                    </div>
                </div>
                
                <div style="padding: 0.75rem; background: var(--bg-secondary); border-radius: 6px; margin-bottom: 0.75rem;">
                    <div style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.25rem;">💡 Trading Suggestion</div>
                    <div style="font-size: 0.9rem; font-weight: 500;">${ctx.trading_suggestion || 'Wait for signals'}</div>
                </div>
                
                ${ctx.vix_status ? `
                    <div style="padding: 0.75rem; background: rgba(139, 92, 246, 0.1); border-left: 3px solid #8b5cf6; border-radius: 4px; margin-bottom: 0.75rem;">
                        <div style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.25rem;">⚡ VIX Analysis</div>
                        <div style="font-size: 0.85rem;">${ctx.vix_status}</div>
                    </div>
                ` : ''}
                
                ${ctx.recommended_strikes && ctx.recommended_strikes.length > 0 ? `
                    <div style="padding: 0.75rem; background: rgba(16, 185, 129, 0.1); border-radius: 6px;">
                        <div style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.5rem;">🎯 Suggested Strikes</div>
                        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                            ${ctx.recommended_strikes.map((strike, idx) => {
                                const label = idx === 0 ? 'ATM' : idx === 1 ? 'OTM1' : 'OTM2';
                                return `<span style="padding: 4px 10px; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 4px; font-size: 0.85rem; font-weight: 500;">${strike} <span style="font-size: 0.7rem; color: var(--text-secondary);">${label}</span></span>`;
                            }).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${ctx.detailed_reasoning ? `
                    <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border-color);">
                        <div style="font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.25rem;">🔍 Analysis</div>
                        <div style="font-size: 0.85rem; color: var(--text-secondary);">${ctx.detailed_reasoning}</div>
                    </div>
                ` : ''}
            </div>
        `;
    });
    
    container.innerHTML = html || '<div style="padding: 2rem; text-align: center; color: var(--text-secondary);">No market data available</div>';
}

function displayInstitutionalIntelligence(symbol, marketContext) {
    if (!marketContext) return;
    
    // Try to find dedicated intelligence container first, fall back to options container
    const intelligenceId = `${symbol.toLowerCase()}-intelligence`;
    let container = document.getElementById(intelligenceId);
    
    if (!container) {
        // If no dedicated container, use options container (backward compatibility for NIFTY)
        const optionsId = `${symbol.toLowerCase()}-options`;
        container = document.getElementById(optionsId);
    }
    
    if (!container) return;
    
    const {
        institutional_activity = "No data",
        trading_suggestion = "Wait for signals",
        detailed_reasoning = "",
        recommended_strikes = [],
        total_call_oi_change = 0,
        total_put_oi_change = 0,
        pcr = 1.0,
        sentiment = "Neutral",
        vix_status = "",
        spot_price = 0
    } = marketContext;
    
    // Format OI changes
    const callOiFormatted = (total_call_oi_change / 100000).toFixed(1);
    const putOiFormatted = (total_put_oi_change / 100000).toFixed(1);
    
    // Determine OI change colors
    const callOiColor = total_call_oi_change > 0 ? '#ef4444' : '#10b981';
    const putOiColor = total_put_oi_change > 0 ? '#10b981' : '#ef4444';
    
    // Sentiment color
    const sentimentColor = sentiment === 'Bullish' ? '#10b981' : sentiment === 'Bearish' ? '#ef4444' : '#f59e0b';
    
    // Build strike recommendations HTML
    let strikesHtml = '';
    if (recommended_strikes && recommended_strikes.length > 0) {
        // Check if it's a straddle/neutral strategy
        const isStraddle = trading_suggestion.includes('Straddle') || trading_suggestion.includes('Iron Condor');
        
        if (isStraddle) {
            // For straddle selling, show ATM strike prominently
            strikesHtml = `
                <div class="intel-section" style="margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border-color);">
                    <div class="intel-header">🎯 ATM Strike for Straddle</div>
                    <div class="strike-chips">
                        <span class="strike-chip straddle-strike">${recommended_strikes[0]} ATM</span>
                    </div>
                </div>
            `;
        } else {
            // Determine strike type from trading suggestion
            // Look for "Buy Call" or "Buy CE" (bullish) vs "Buy Put" or "Buy PE" (bearish)
            let strikeType = 'PE'; // Default to PE
            if (trading_suggestion.includes('Buy Call') || 
                trading_suggestion.includes('Buy CE') ||
                trading_suggestion.includes('Strong Buy Calls')) {
                strikeType = 'CE';
            } else if (trading_suggestion.includes('Buy Put') || 
                       trading_suggestion.includes('Buy PE') ||
                       trading_suggestion.includes('Strong Buy Puts')) {
                strikeType = 'PE';
            }
            
            strikesHtml = `
                <div class="intel-section" style="margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border-color);">
                    <div class="intel-header">🎯 Suggested ${strikeType} Strikes</div>
                    <div class="strike-chips">
                        ${recommended_strikes.map((strike, idx) => {
                            const label = idx === 0 ? 'ATM' : idx === 1 ? 'OTM1' : 'OTM2';
                            return `<span class="strike-chip">${strike} ${label}</span>`;
                        }).join('')}
                    </div>
                    <div style="font-size: 0.7rem; color: var(--text-secondary); margin-top: 4px;">
                        Spot: ₹${spot_price.toLocaleString()}
                    </div>
                </div>
            `;
        }
    }
    
    // Build reasoning HTML
    let reasoningHtml = '';
    if (detailed_reasoning) {
        // Determine header based on whether there are recommended strikes
        const reasoningHeader = (recommended_strikes && recommended_strikes.length > 0) 
            ? '🔍 Why This Trade?' 
            : '⚠️ Analysis';
        
        reasoningHtml = `
            <div class="intel-section">
                <div class="intel-header">${reasoningHeader}</div>
                <div class="intel-reasoning">${detailed_reasoning}</div>
            </div>
        `;
    }
    
    const html = `
        <div class="institutional-intelligence">
            <div class="intel-section">
                <div class="intel-header">📊 Market Sentiment</div>
                <div class="intel-value" style="color: ${sentimentColor}; font-weight: 600;">
                    ${sentiment} (PCR: ${pcr.toFixed(2)})
                </div>
            </div>
            
            <div class="intel-section">
                <div class="intel-header">🏛️ Institutional Activity</div>
                <div class="intel-activity">${institutional_activity}</div>
                <div class="oi-changes">
                    <span style="color: ${callOiColor};">Call OI: ${callOiFormatted > 0 ? '+' : ''}${callOiFormatted}L</span>
                    <span style="color: ${putOiColor}; margin-left: 12px;">Put OI: ${putOiFormatted > 0 ? '+' : ''}${putOiFormatted}L</span>
                </div>
            </div>
            
            <div class="intel-section">
                <div class="intel-header">💡 Trading Action</div>
                <div class="intel-suggestion">${trading_suggestion}</div>
            </div>
            
            ${reasoningHtml}
            
            ${strikesHtml}
            
            <div class="intel-section" style="margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border-color);">
                <div class="intel-volatility" style="font-size: 0.75rem; color: var(--text-secondary);">
                    ⚡ ${vix_status}
                </div>
            </div>
        </div>
    `;
    
    // Show the container and set innerHTML
    container.style.display = 'block';
    container.innerHTML = html;
}

function displayWatchlistTable(strikes) {
    const container = document.getElementById('watchlist-table');
    if (!container) return;
    
    if (!strikes || strikes.length === 0) {
        container.innerHTML = `
            <div class="no-trades-message" style="padding: 2rem; text-align: center; background: var(--bg-secondary); border-radius: 8px; border: 1px dashed var(--border-color);">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">📊</div>
                <div style="font-size: 1rem; font-weight: 600; margin-bottom: 0.5rem; color: var(--text-primary);">
                    No Trading Signals Active
                </div>
                <div style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1rem;">
                    Strategies are analyzing market conditions. Signals appear here when 21+ strategies agree on high-probability trades.
                </div>
                <div style="font-size: 0.85rem; color: var(--text-secondary); padding: 0.75rem; background: var(--card-bg); border-radius: 6px; display: inline-block;">
                    💡 Check <strong>Market Intelligence</strong> above for current analysis
                </div>
            </div>
        `;
        return;
    }
    
    let html = `
        <table class="watchlist-table">
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Index</th>
                    <th>Strike</th>
                    <th>Type</th>
                    <th>Entry Price</th>
                    <th>T1</th>
                    <th>T2</th>
                    <th>T3</th>
                    <th>Stop Loss</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    strikes.forEach((strike, index) => {
        const rank = index + 1;
        const directionClass = strike.direction === 'CALL' ? 'call' : 'put';
        
        // Calculate targets if available
        const entryPrice = strike.entry_price || 0;
        const t1 = strike.target_price || (entryPrice * 1.15); // +15%
        const t2 = strike.target_2 || (entryPrice * 1.25); // +25%
        const t3 = strike.target_3 || (entryPrice * 1.35); // +35%
        const sl = strike.stop_loss || (entryPrice * 0.85); // -15%
        
        html += `
            <tr onclick="showStrikeDetails('${strike.index}', '${strike.strike}', '${strike.direction}')">
                <td><strong>#${rank}</strong></td>
                <td><strong>${strike.index}</strong></td>
                <td class="price-cell">${strike.strike}</td>
                <td><span class="strike-badge ${directionClass}">${strike.direction}</span></td>
                <td class="price-cell">₹${entryPrice.toFixed(2)}</td>
                <td class="price-cell">₹${t1.toFixed(2)}</td>
                <td class="price-cell">₹${t2.toFixed(2)}</td>
                <td class="price-cell">₹${t3.toFixed(2)}</td>
                <td class="price-cell">₹${sl.toFixed(2)}</td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
        </table>
    `;
    
    container.innerHTML = html;
}

async function refreshRecentSignals() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/signals/recent`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.status !== 'success') {
            document.getElementById('recent-signals-container').innerHTML = 
                '<div class="error-message">Unable to load recent signals</div>';
            return;
        }
        
        displayRecentSignals(result.data);
        
    } catch (error) {
        console.error('Error fetching recent signals:', error);
        document.getElementById('recent-signals-container').innerHTML = 
            '<div class="error-message">Error loading signals</div>';
    }
}

function displayRecentSignals(signals) {
    const container = document.getElementById('recent-signals-container');
    if (!container) return;
    
    if (!signals || signals.length === 0) {
        container.innerHTML = `
            <div class="no-trades-message" style="padding: 1.5rem; text-align: center; background: var(--bg-secondary); border-radius: 8px;">
                <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">📊</div>
                <div style="font-size: 0.9rem; color: var(--text-secondary);">
                    No signals generated yet today
                </div>
            </div>
        `;
        return;
    }
    
    let html = '<div style="display: grid; gap: 0.75rem;">';
    
    // Add paper mode indicator at top
    html += `
        <div style="padding: 0.5rem; background: rgba(59, 130, 246, 0.1); border-left: 3px solid #3b82f6; border-radius: 4px; font-size: 0.85rem;">
            <strong>📝 Paper Trading Mode</strong> - These signals were tested in simulation. No real money at risk.
        </div>
    `;
    
    signals.slice(0, 10).forEach(signal => {
        const timestamp = new Date(signal.timestamp).toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        const directionClass = signal.direction === 'CALL' ? 'call' : 'put';
        
        // Determine actual status - paper trades show differently
        let statusClass, statusIcon, statusText;
        
        if (signal.status === 'executed') {
            // Check if this is a paper trade or real trade
            // Paper mode always shows as paper trade
            statusClass = 'info';  // Blue for paper trades
            statusIcon = '📝';
            statusText = 'Paper Trade';
        } else if (signal.status === 'blocked_by_risk') {
            statusClass = 'warning';
            statusIcon = '⚠';
            statusText = 'Blocked';
        } else if (signal.status === 'execution_failed') {
            statusClass = 'error';
            statusIcon = '✗';
            statusText = 'Failed';
        } else {
            statusClass = 'secondary';
            statusIcon = '○';
            statusText = signal.status;
        }
        
        html += `
            <div class="signal-item" style="padding: 0.75rem; background: var(--card-bg); border-radius: 6px; border-left: 3px solid ${directionClass === 'call' ? '#10b981' : '#ef4444'};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 0.75rem; color: var(--text-secondary);">${timestamp}</span>
                        <span class="strike-badge ${directionClass}">${signal.direction}</span>
                        <strong>${signal.symbol} ${signal.strike || ''}</strong>
                    </div>
                    <span class="status-badge ${statusClass}" style="font-size: 0.75rem; padding: 0.25rem 0.5rem;">
                        ${statusIcon} ${statusText}
                    </span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 0.5rem; font-size: 0.8rem;">
                    <div>
                        <span style="color: var(--text-secondary);">Entry:</span> 
                        <strong>₹${(signal.entry_price || 0).toFixed(2)}</strong>
                    </div>
                    <div>
                        <span style="color: var(--text-secondary);">Target:</span> 
                        <strong>₹${(signal.target_price || 0).toFixed(2)}</strong>
                    </div>
                    <div>
                        <span style="color: var(--text-secondary);">SL:</span> 
                        <strong>₹${(signal.stop_loss || 0).toFixed(2)}</strong>
                    </div>
                    <div>
                        <span style="color: var(--text-secondary);">Strength:</span> 
                        <strong>${signal.strength || 0}</strong>
                    </div>
                </div>
                ${signal.strategy ? `<div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.25rem;">Strategy: ${signal.strategy}</div>` : ''}
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

function showStrikeDetails(strike, direction) {
    // TODO: Show modal with full strategy consensus and detailed analysis
    console.log(`Show details for ${strike} ${direction}`);
    alert(`Detailed analysis for ${strike} ${direction}\n\nFeature coming soon:\n- Full strategy breakdown\n- ML confidence score\n- Historical performance\n- Entry/exit recommendations`);
}

async function showWatchlistPerformance() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/watchlist/performance?days=30`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.status !== 'success') {
            showModal('Performance Data', '<p>Unable to load performance data</p>');
            return;
        }
        
        const data = result.data;
        
        // Check if there's data
        if (data.closed_signals === 0) {
            showModal('Smart Watchlist Performance', 
                `<div style="text-align: center; padding: 20px;">
                    <p style="margin-bottom: 10px;">No closed signals yet</p>
                    <p style="font-size: 0.9rem; color: #64748b;">
                        Total signals: ${data.total_signals}<br/>
                        Pending signals: ${data.pending_signals}
                    </p>
                </div>`
            );
            return;
        }
        
        // Build performance HTML
        let html = `
            <div style="padding: 20px;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px;">
                    <div class="performance-card">
                        <div style="font-size: 0.8rem; color: #64748b;">Win Rate</div>
                        <div style="font-size: 1.8rem; font-weight: bold; color: ${data.overall.win_rate >= 60 ? '#10b981' : data.overall.win_rate >= 50 ? '#f59e0b' : '#ef4444'}">
                            ${data.overall.win_rate.toFixed(1)}%
                        </div>
                        <div style="font-size: 0.75rem; color: #64748b;">
                            ${data.overall.wins} wins / ${data.overall.losses} losses
                        </div>
                    </div>
                    <div class="performance-card">
                        <div style="font-size: 0.8rem; color: #64748b;">Total P&L</div>
                        <div style="font-size: 1.8rem; font-weight: bold; color: ${data.pnl.total_pnl >= 0 ? '#10b981' : '#ef4444'}">
                            ₹${data.pnl.total_pnl.toLocaleString()}
                        </div>
                        <div style="font-size: 0.75rem; color: #64748b;">
                            From ${data.closed_signals} signals
                        </div>
                    </div>
                    <div class="performance-card">
                        <div style="font-size: 0.8rem; color: #64748b;">Avg P&L / Signal</div>
                        <div style="font-size: 1.5rem; font-weight: bold; color: ${data.pnl.avg_pnl_per_signal >= 0 ? '#10b981' : '#ef4444'}">
                            ₹${data.pnl.avg_pnl_per_signal.toFixed(2)}
                        </div>
                    </div>
                    <div class="performance-card">
                        <div style="font-size: 0.8rem; color: #64748b;">Profit Factor</div>
                        <div style="font-size: 1.5rem; font-weight: bold; color: ${data.pnl.profit_factor >= 2 ? '#10b981' : data.pnl.profit_factor >= 1 ? '#f59e0b' : '#ef4444'}">
                            ${data.pnl.profit_factor.toFixed(2)}x
                        </div>
                    </div>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <h4 style="margin-bottom: 10px;">By Symbol</h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: #f8fafc; text-align: left;">
                                <th style="padding: 8px;">Symbol</th>
                                <th style="padding: 8px;">Win Rate</th>
                                <th style="padding: 8px;">Signals</th>
                                <th style="padding: 8px;">Total P&L</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.by_symbol.map(s => `
                                <tr style="border-bottom: 1px solid #e2e8f0;">
                                    <td style="padding: 8px; font-weight: 500;">${s.symbol}</td>
                                    <td style="padding: 8px; color: ${s.win_rate >= 60 ? '#10b981' : s.win_rate >= 50 ? '#f59e0b' : '#ef4444'}">
                                        ${s.win_rate.toFixed(1)}%
                                    </td>
                                    <td style="padding: 8px;">${s.total_signals}</td>
                                    <td style="padding: 8px; color: ${s.total_pnl >= 0 ? '#10b981' : '#ef4444'}">
                                        ₹${s.total_pnl.toFixed(2)}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <h4 style="margin-bottom: 10px;">By Direction</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                        ${data.by_direction.map(d => `
                            <div style="padding: 12px; background: #f8fafc; border-radius: 8px;">
                                <div style="font-size: 0.9rem; font-weight: 500; margin-bottom: 5px;">${d.direction}</div>
                                <div style="color: ${d.win_rate >= 60 ? '#10b981' : d.win_rate >= 50 ? '#f59e0b' : '#ef4444'}">
                                    ${d.win_rate.toFixed(1)}% win rate
                                </div>
                                <div style="font-size: 0.85rem; color: #64748b;">
                                    ${d.total_signals} signals · ₹${d.total_pnl.toFixed(2)} P&L
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                
                ${data.best_signals && data.best_signals.length > 0 ? `
                    <div style="margin-bottom: 15px;">
                        <h4 style="margin-bottom: 10px;">🏆 Top 3 Best Signals</h4>
                        <div style="font-size: 0.9rem;">
                            ${data.best_signals.slice(0, 3).map((s, i) => `
                                <div style="padding: 8px; background: #f0fdf4; border-left: 3px solid #10b981; margin-bottom: 5px;">
                                    <strong>#${i+1}</strong> ${s.symbol} ${s.strike} ${s.direction} 
                                    <span style="color: #10b981; font-weight: bold;">+₹${s.pnl.toFixed(2)}</span>
                                    <span style="color: #64748b;">(${s.pnl_pct.toFixed(1)}%)</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${data.worst_signals && data.worst_signals.length > 0 ? `
                    <div>
                        <h4 style="margin-bottom: 10px;">📉 Top 3 Worst Signals</h4>
                        <div style="font-size: 0.9rem;">
                            ${data.worst_signals.slice(0, 3).map((s, i) => `
                                <div style="padding: 8px; background: #fef2f2; border-left: 3px solid #ef4444; margin-bottom: 5px;">
                                    <strong>#${i+1}</strong> ${s.symbol} ${s.strike} ${s.direction} 
                                    <span style="color: #ef4444; font-weight: bold;">₹${s.pnl.toFixed(2)}</span>
                                    <span style="color: #64748b;">(${s.pnl_pct.toFixed(1)}%)</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
        
        showModal('Smart Watchlist Performance (Last 30 Days)', html);
        
    } catch (error) {
        console.error('Error fetching watchlist performance:', error);
        showModal('Error', '<p>Failed to load performance data. Please try again.</p>');
    }
}

function formatLargeNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// ============================================================================
// CAPITAL MANAGEMENT
// ============================================================================

// Update capital info and P&L chart
async function updateCapitalInfo() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/capital`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update capital display
        updateCapitalDisplay();
        
        // Update P&L chart with current data
        const todayPnl = data.today_pnl || 0;
        const now = new Date();
        const currentTime = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
        
        // Check if we already have a data point for this minute
        const existingIndex = pnlData.findIndex(d => d.time === currentTime);
        
        if (existingIndex >= 0) {
            // Update existing data point for this minute
            pnlData[existingIndex].pnl = todayPnl;
        } else {
            // Add new data point
            pnlData.push({
                time: currentTime,
                pnl: todayPnl
            });
            
            // Keep only last 200 data points (enough for full trading session)
            if (pnlData.length > 200) {
                pnlData.shift();
            }
        }
        
        updatePnLChart();
        
    } catch (error) {
        console.error('Error updating capital info:', error);
    }
}

async function updateCapitalDisplay() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/capital`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update starting capital
        const startingEl = document.getElementById('starting-capital');
        if (startingEl) {
            startingEl.textContent = `₹${formatNumber(data.starting_capital)}`;
        }
        
        // Update current capital
        const currentEl = document.getElementById('current-capital');
        if (currentEl) {
            currentEl.textContent = `₹${formatNumber(data.current_capital)}`;
        }
        
        // Update today's P&L
        const todayPnlEl = document.getElementById('today-pnl');
        const todayPctEl = document.getElementById('today-pnl-pct');
        if (todayPnlEl && todayPctEl) {
            const todayPnl = data.today_pnl || 0;
            const todayPct = data.today_pnl_pct || 0;
            todayPnlEl.textContent = `₹${formatNumber(todayPnl)}`;
            todayPctEl.textContent = `(${todayPct >= 0 ? '+' : ''}${todayPct.toFixed(2)}%)`;
            
            // Set color based on positive/negative
            todayPnlEl.className = 'pnl-value ' + (todayPnl >= 0 ? 'positive' : 'negative');
            todayPctEl.className = 'pnl-pct ' + (todayPnl >= 0 ? 'positive' : 'negative');
        }
        
        // Update total P&L
        const totalPnlEl = document.getElementById('total-pnl');
        const totalPctEl = document.getElementById('total-pnl-pct');
        if (totalPnlEl && totalPctEl) {
            const totalPnl = data.total_pnl || 0;
            const totalPct = data.total_pnl_pct || 0;
            totalPnlEl.textContent = `₹${formatNumber(totalPnl)}`;
            totalPctEl.textContent = `(${totalPct >= 0 ? '+' : ''}${totalPct.toFixed(2)}%)`;
            
            // Set color based on positive/negative
            totalPnlEl.className = 'pnl-value ' + (totalPnl >= 0 ? 'positive' : 'negative');
            totalPctEl.className = 'pnl-pct ' + (totalPnl >= 0 ? 'positive' : 'negative');
        }
    } catch (error) {
        console.error('Error updating capital display:', error);
        // Show placeholder values on error
        ['starting-capital', 'current-capital'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '₹--';
        });
        ['today-pnl', 'total-pnl'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '₹0.00';
        });
        ['today-pnl-pct', 'total-pnl-pct'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '(0.00%)';
        });
    }
}

function editCapital() {
    const currentCapital = document.getElementById('starting-capital')?.textContent?.replace('₹', '').replace(/,/g, '') || '100000';
    const newCapital = prompt('Enter Starting Capital (₹):', currentCapital);
    
    if (newCapital !== null && newCapital.trim() !== '') {
        const capitalValue = parseFloat(newCapital.replace(/,/g, ''));
        
        if (isNaN(capitalValue) || capitalValue < 10000) {
            alert('❌ Invalid capital. Minimum is ₹10,000');
            return;
        }
        
        saveCapital(capitalValue);
    }
}

async function saveCapital(capitalValue) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/capital/starting`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ starting_capital: capitalValue })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log('✓ Capital updated:', data);
        
        // Refresh capital display
        await updateCapitalDisplay();
        
        alert(`✅ Starting capital updated to ₹${formatNumber(capitalValue)}`);
    } catch (error) {
        console.error('Error saving capital:', error);
        alert('❌ Failed to update capital. Please try again.');
    }
}

function formatNumber(num) {
    return num.toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

// ============================================================================
// STATUS DOTS
// ============================================================================

async function updateStatusDots() {
    // Check API status
    try {
        const apiResponse = await fetch(`${API_BASE_URL}/health`, { timeout: 3000 });
        const apiDot = document.getElementById('status-api');
        if (apiDot) {
            apiDot.className = 'quality-dot ' + (apiResponse.ok ? 'connected' : 'error');
            apiDot.title = apiResponse.ok ? 'API: Connected' : 'API: Error';
        }
    } catch (error) {
        const apiDot = document.getElementById('status-api');
        if (apiDot) {
            apiDot.className = 'quality-dot error';
            apiDot.title = 'API: Disconnected';
        }
    }
    
    // Check Database status
    try {
        const dbResponse = await fetch(`${API_BASE_URL}/api/health/db`);
        const dbData = await dbResponse.json();
        const dbDot = document.getElementById('status-db');
        if (dbDot) {
            dbDot.className = 'quality-dot ' + (dbData.status === 'ok' ? 'connected' : 'error');
            dbDot.title = dbData.status === 'ok' ? 'Database: Connected' : 'Database: Error';
        }
    } catch (error) {
        const dbDot = document.getElementById('status-db');
        if (dbDot) {
            dbDot.className = 'quality-dot error';
            dbDot.title = 'Database: Disconnected';
        }
    }
    
    // Check WebSocket status (placeholder - implement based on your WS setup)
    const wsDot = document.getElementById('status-ws');
    if (wsDot) {
        // For now, show as disconnected since WS not implemented yet
        wsDot.className = 'quality-dot degraded';
        wsDot.title = 'WebSocket: Not Configured';
    }
}

// ============================================================================
// SETTINGS MODAL
// ============================================================================

let currentSettings = null;

window.openSettingsModal = function() {
    const modal = document.getElementById('settings-modal');
    if (modal) {
        modal.style.display = 'block';
        loadSettings();
    }
}

function closeSettingsModal() {
    const modal = document.getElementById('settingsModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

window.showSettingsTab = function(tabName) {
    // Hide all tab contents
    const contents = document.querySelectorAll('.settings-tab-content');
    contents.forEach(content => {
        content.classList.remove('active');
    });
    
    // Remove active class from all tabs
    const tabs = document.querySelectorAll('.settings-tab');
    tabs.forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected tab content
    const selectedContent = document.getElementById(`${tabName}-tab`);
    if (selectedContent) {
        selectedContent.classList.add('active');
    }
    
    // Add active class to selected tab
    const selectedTab = document.querySelector(`.settings-tab[onclick*="${tabName}"]`);
    if (selectedTab) {
        selectedTab.classList.add('active');
    }
}

async function loadSettings() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const settings = await response.json();
        currentSettings = settings;
        
        // Populate Trading Configuration
        document.getElementById('setting-capital').value = settings.trading.capital || 100000;
        document.getElementById('setting-max-trades').value = settings.trading.max_trades_per_day || 999;
        document.getElementById('setting-max-positions').value = settings.trading.max_positions || 5;
        document.getElementById('setting-trade-amount').value = settings.trading.trade_amount || 20000;
        document.getElementById('setting-commission').value = settings.trading.commission || 40;
        
        // Populate Risk Management
        document.getElementById('setting-max-drawdown').value = settings.risk.max_drawdown_pct || 10;
        document.getElementById('setting-daily-loss').value = settings.risk.daily_loss_limit_pct || 5;
        document.getElementById('setting-per-trade-risk').value = settings.risk.per_trade_risk_pct || 2;
        document.getElementById('setting-stop-loss-type').value = settings.risk.stop_loss_type || 'fixed';
        document.getElementById('setting-position-sizing').value = settings.risk.position_sizing_method || 'fixed';
        
        // Populate Strategy Weights
        initializeStrategyWeights(settings.strategies || {});
        
        // Populate ML Configuration
        document.getElementById('setting-min-ml-score').value = settings.ml.min_ml_score || 0.65;
        document.getElementById('setting-min-strategy-strength').value = settings.ml.min_strategy_strength || 70;
        document.getElementById('setting-min-strategies').value = settings.ml.min_strategies_agree || 3;
        document.getElementById('setting-retrain-frequency').value = settings.ml.retrain_frequency_days || 7;
        
        // Populate System Configuration
        document.getElementById('setting-refresh-rate').value = settings.system.refresh_rate_seconds || 2;
        document.getElementById('setting-log-level').value = settings.system.log_level || 'INFO';
        document.getElementById('setting-trading-mode').value = settings.system.trading_mode || 'paper';
        
        console.log('✓ Settings loaded successfully');
    } catch (error) {
        console.error('Error loading settings:', error);
        alert('⚠️ Could not load settings. Using defaults.');
        loadDefaultSettings();
    }
}

function loadDefaultSettings() {
    // Load default values from DASHBOARD_ENHANCEMENTS.md
    document.getElementById('setting-capital').value = 100000;
    document.getElementById('setting-max-trades').value = 999;
    document.getElementById('setting-max-positions').value = 5;
    document.getElementById('setting-trade-amount').value = 20000;
    document.getElementById('setting-commission').value = 40;
    
    document.getElementById('setting-max-drawdown').value = 10;
    document.getElementById('setting-daily-loss').value = 5;
    document.getElementById('setting-per-trade-risk').value = 2;
    document.getElementById('setting-stop-loss-type').value = 'fixed';
    document.getElementById('setting-position-sizing').value = 'fixed';
    
    document.getElementById('setting-min-ml-score').value = 0.65;
    document.getElementById('setting-min-strategy-strength').value = 70;
    document.getElementById('setting-min-strategies').value = 3;
    document.getElementById('setting-retrain-frequency').value = 7;
    
    document.getElementById('setting-refresh-rate').value = 2;
    document.getElementById('setting-log-level').value = 'INFO';
    document.getElementById('setting-trading-mode').value = 'paper';
    
    // Initialize strategy weights to defaults
    const defaultWeights = {
        oi_buildup: 85, oi_unwinding: 80, max_pain: 75, pcr_analysis: 70,
        sentiment_flow: 85, volume_surge: 80, institutional_activity: 75,
        delta_hedging: 90, gamma_scalping: 85, vega_vanna: 80,
        fii_dii: 85, block_deals: 80, bulk_deals: 75,
        bull_spread: 70, bear_spread: 70, iron_condor: 65,
        vwap: 75, pivot: 70, momentum: 75,
        vix_correlation: 80
    };
    initializeStrategyWeights(defaultWeights);
}

function initializeStrategyWeights(weights) {
    const strategies = [
        'oi_buildup', 'oi_unwinding', 'max_pain', 'pcr_analysis',
        'sentiment_flow', 'volume_surge', 'institutional_activity',
        'delta_hedging', 'gamma_scalping', 'vega_vanna',
        'fii_dii', 'block_deals', 'bulk_deals',
        'bull_spread', 'bear_spread', 'iron_condor',
        'vwap', 'pivot', 'momentum', 'vix_correlation'
    ];
    
    strategies.forEach(strategy => {
        const slider = document.getElementById(`strategy-${strategy}`);
        const valueDisplay = document.getElementById(`value-${strategy}`);
        const toggle = document.getElementById(`toggle-${strategy}`);
        
        if (slider && valueDisplay) {
            const weight = weights[strategy] || 50;
            slider.value = weight;
            valueDisplay.textContent = weight;
            
            // Update slider on input
            slider.oninput = function() {
                valueDisplay.textContent = this.value;
            };
        }
        
        if (toggle) {
            toggle.checked = weights[strategy] > 0;
            
            // Disable slider if toggle is off
            if (slider) {
                slider.disabled = !toggle.checked;
            }
            
            // Handle toggle change
            toggle.onchange = function() {
                if (slider) {
                    slider.disabled = !this.checked;
                    if (!this.checked) {
                        slider.value = 0;
                        valueDisplay.textContent = 0;
                    }
                }
            };
        }
    });
}

async function saveSettings() {
    try {
        // Collect all settings
        const settings = {
            trading: {
                capital: parseFloat(document.getElementById('setting-capital').value),
                max_trades_per_day: parseInt(document.getElementById('setting-max-trades').value),
                max_positions: parseInt(document.getElementById('setting-max-positions').value),
                trade_amount: parseFloat(document.getElementById('setting-trade-amount').value),
                commission: parseFloat(document.getElementById('setting-commission').value)
            },
            risk: {
                max_drawdown_pct: parseFloat(document.getElementById('setting-max-drawdown').value),
                daily_loss_limit_pct: parseFloat(document.getElementById('setting-daily-loss').value),
                per_trade_risk_pct: parseFloat(document.getElementById('setting-per-trade-risk').value),
                stop_loss_type: document.getElementById('setting-stop-loss-type').value,
                position_sizing_method: document.getElementById('setting-position-sizing').value
            },
            strategies: collectStrategyWeights(),
            ml: {
                min_ml_score: parseFloat(document.getElementById('setting-min-ml-score').value),
                min_strategy_strength: parseFloat(document.getElementById('setting-min-strategy-strength').value),
                min_strategies_agree: parseInt(document.getElementById('setting-min-strategies').value),
                retrain_frequency_days: parseInt(document.getElementById('setting-retrain-frequency').value)
            },
            system: {
                refresh_rate_seconds: parseInt(document.getElementById('setting-refresh-rate').value),
                log_level: document.getElementById('setting-log-level').value,
                trading_mode: document.getElementById('setting-trading-mode').value
            }
        };
        
        // Validate settings
        const validation = validateSettings(settings);
        if (!validation.valid) {
            alert('❌ Validation Error:\n\n' + validation.errors.join('\n'));
            return;
        }
        
        // Save to backend
        const response = await fetch(`${API_BASE_URL}/api/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(settings)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log('✓ Settings saved:', data);
        
        alert('✅ Settings saved successfully!');
        closeSettingsModal();
        
        // Refresh data with new settings
        refreshData();
    } catch (error) {
        console.error('Error saving settings:', error);
        alert('❌ Failed to save settings. Please try again.');
    }
}

function collectStrategyWeights() {
    const strategies = [
        'oi_buildup', 'oi_unwinding', 'max_pain', 'pcr_analysis',
        'sentiment_flow', 'volume_surge', 'institutional_activity',
        'delta_hedging', 'gamma_scalping', 'vega_vanna',
        'fii_dii', 'block_deals', 'bulk_deals',
        'bull_spread', 'bear_spread', 'iron_condor',
        'vwap', 'pivot', 'momentum', 'vix_correlation'
    ];
    
    const weights = {};
    strategies.forEach(strategy => {
        const toggle = document.getElementById(`toggle-${strategy}`);
        const slider = document.getElementById(`strategy-${strategy}`);
        
        if (toggle && slider) {
            weights[strategy] = toggle.checked ? parseInt(slider.value) : 0;
        }
    });
    
    return weights;
}

function validateSettings(settings) {
    const errors = [];
    
    // Validate capital
    if (settings.trading.capital < 10000) {
        errors.push('Capital must be at least ₹10,000');
    }
    
    // Validate drawdown
    if (settings.risk.max_drawdown_pct < 1 || settings.risk.max_drawdown_pct > 50) {
        errors.push('Max Drawdown must be between 1% and 50%');
    }
    
    // Validate daily loss
    if (settings.risk.daily_loss_limit_pct < 0.5 || settings.risk.daily_loss_limit_pct > 20) {
        errors.push('Daily Loss Limit must be between 0.5% and 20%');
    }
    
    // Validate per trade risk
    if (settings.risk.per_trade_risk_pct < 0.5 || settings.risk.per_trade_risk_pct > 10) {
        errors.push('Per Trade Risk must be between 0.5% and 10%');
    }
    
    // Validate ML scores
    if (settings.ml.min_ml_score < 0 || settings.ml.min_ml_score > 1) {
        errors.push('Min ML Score must be between 0 and 1');
    }
    
    // Validate strategy weights
    const weights = Object.values(settings.strategies);
    const invalidWeights = weights.filter(w => w < 0 || w > 100);
    if (invalidWeights.length > 0) {
        errors.push('Strategy weights must be between 0 and 100');
    }
    
    return {
        valid: errors.length === 0,
        errors: errors
    };
}

async function resetSettingsToDefaults() {
    const confirmed = confirm(
        '⚠️ Reset to Optimum Defaults?\n\n' +
        'This will restore all settings to factory defaults:\n' +
        '• Capital: ₹1,00,000\n' +
        '• Max Trades: 999 (unlimited paper trading)\n' +
        '• Max Drawdown: 10%\n' +
        '• All strategy weights to optimum values\n\n' +
        'Continue?'
    );
    
    if (!confirmed) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/settings/reset`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        console.log('✓ Settings reset to defaults:', data);
        
        // Reload settings in modal
        await loadSettings();
        
        alert('✅ Settings reset to optimum defaults!');
    } catch (error) {
        console.error('Error resetting settings:', error);
        alert('⚠️ Could not connect to backend. Loading local defaults.');
        loadDefaultSettings();
    }
}

// ============================================================================
// INITIALIZATION & AUTO-REFRESH
// ============================================================================

// Add capital and status dots to refresh cycle
const originalRefreshData = refreshData;
refreshData = async function() {
    await originalRefreshData();
    await updateCapitalDisplay();
};

// Update status dots every 5 seconds
setInterval(updateStatusDots, 5000);
updateStatusDots(); // Initial update

// Check engine status every 10 seconds
setInterval(checkEngineStatus, 10000);
checkEngineStatus(); // Initial check

// Refresh trade history every 10 seconds to catch closed trades
setInterval(updateTradeHistory, 10000);

// Refresh positions every 2 seconds to ensure live price updates
setInterval(updatePositions, 2000);

// Update market overview every 5 seconds (independent of WebSocket)
setInterval(updateMarketOverview, 5000);
updateMarketOverview(); // Initial update

// Update option chain and institutional data every 30 seconds (matches backend fetch interval)
setInterval(updateOptionChainData, 30000);
updateOptionChainData(); // Initial update

// Update watchlist every 30 seconds for aggressive trade scanning
setInterval(updateWatchlist, 30000);

// Update risk metrics and capital every 3 seconds
setInterval(() => {
    updateRiskMetrics();
    updateCapitalInfo();
}, 3000);

// Initial capital load
updateCapitalDisplay();

// Production Lock Functions
async function toggleProductionLock() {
    try {
        // Check current status
        const statusResponse = await fetch(`${API_BASE_URL}/api/production/status`);
        const status = await statusResponse.json();
        
        if (status.production_mode) {
            // Already locked - ask for unlock
            if (confirm('⚠️ System is in PRODUCTION mode.\n\nUnlocking will remove all safety locks.\nAre you sure you want to continue?')) {
                const unlockResponse = await fetch(`${API_BASE_URL}/api/production/unlock`, {
                    method: 'POST'
                });
                const result = await unlockResponse.json();
                
                if (result.status === 'unlocked') {
                    alert('✅ Production lock removed\nSystem is now in DEVELOPMENT mode');
                    updateProductionLockButton(false);
                } else {
                    alert('❌ Failed to unlock: ' + (result.detail || 'Unknown error'));
                }
            }
        } else {
            // Not locked - ask for lock
            const confirmMsg = `🔒 PRODUCTION LOCK ACTIVATION\n\nThis will:
• Create git tag: v1.0.0-production
• Freeze all configuration parameters
• Apply hard safety locks
• Set max daily loss to -3.5%
• Force EOD exit at 15:25 IST
• Limit position size to 4 lots per strike

This action cannot be undone without written justification.

Proceed with Production Lock?`;
            
            if (confirm(confirmMsg)) {
                const lockResponse = await fetch(`${API_BASE_URL}/api/production/lock`, {
                    method: 'POST'
                });
                const result = await lockResponse.json();
                
                if (result.status === 'locked') {
                    alert(`✅ PRODUCTION LOCK ACTIVATED\n\nGit tag: ${result.git_tag}\nLocked at: ${result.locked_at}\n\nSystem is now in production mode`);
                    updateProductionLockButton(true);
                } else {
                    alert('❌ Failed to lock: ' + (result.detail || 'Unknown error'));
                }
            }
        }
    } catch (error) {
        console.error('Error toggling production lock:', error);
        alert('❌ Error: ' + error.message);
    }
}

function updateProductionLockButton(isLocked) {
    const btn = document.getElementById('production-lock-btn');
    if (isLocked) {
        btn.textContent = '🔓 Production Locked';
        btn.className = 'btn btn-success';
        btn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
    } else {
        btn.textContent = '🔒 Production Lock';
        btn.className = 'btn btn-primary';
        btn.style.background = '';
    }
}

// Check production lock status on load
async function checkProductionLockStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/production/status`);
        const status = await response.json();
        updateProductionLockButton(status.production_mode);
    } catch (error) {
        console.error('Error checking production status:', error);
    }
}

// Check production status on dashboard load
checkProductionLockStatus();

console.log('✓ Dashboard script loaded');


// ============================================
// TOKEN MONITORING SYSTEM
// ============================================

function startTokenMonitoring() {
    // Check token status immediately
    updateTokenStatus();
    
    // Check every 5 minutes
    tokenCheckInterval = setInterval(updateTokenStatus, 5 * 60 * 1000);
    
    console.log('✓ Token monitoring started');
}

async function updateTokenStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/token/status`);
        const data = await response.json();
        
        const tokenStatusEl = document.getElementById('token-status');
        const tokenCountdownEl = document.getElementById('token-countdown');
        
        if (data.valid) {
            const hoursLeft = data.time_remaining_hours || 0;
            const minutesLeft = Math.floor((data.time_remaining_seconds || 0) / 60) % 60;
            
            // Clear expired flag when token is valid again
            sessionStorage.removeItem('token_expired_shown');
            
            // Remove any stuck expired notification banners
            const existingBanner = document.querySelector('div[style*="linear-gradient(135deg, #f44336"]');
            if (existingBanner) {
                existingBanner.remove();
            }
            
            // Show token status
            tokenStatusEl.style.display = 'flex';
            
            // Color code based on time remaining
            if (hoursLeft < 1) {
                tokenStatusEl.style.color = '#ff4444'; // Red - urgent
                tokenCountdownEl.textContent = `${minutesLeft}m (Expiring Soon!)`;
            } else if (hoursLeft < 3) {
                tokenStatusEl.style.color = '#ff9800'; // Orange - warning
                tokenCountdownEl.textContent = `${hoursLeft.toFixed(1)}h`;
            } else {
                tokenStatusEl.style.color = '#4caf50'; // Green - healthy
                tokenCountdownEl.textContent = `${hoursLeft.toFixed(1)}h`;
            }
            
            // Show notification if token needs refresh soon
            if (hoursLeft < 1 && !sessionStorage.getItem('token_warning_shown')) {
                showTokenExpiryWarning(minutesLeft);
                sessionStorage.setItem('token_warning_shown', 'true');
            }
            
        } else {
            // Token expired or invalid
            tokenStatusEl.style.display = 'flex';
            tokenStatusEl.style.color = '#ff4444';
            tokenCountdownEl.textContent = 'EXPIRED';
            
            if (!sessionStorage.getItem('token_expired_shown')) {
                showTokenExpiredNotification();
                sessionStorage.setItem('token_expired_shown', 'true');
            }
        }
        
    } catch (error) {
        console.error('Error checking token status:', error);
        // Hide token status on error
        const tokenStatusEl = document.getElementById('token-status');
        if (tokenStatusEl) {
            tokenStatusEl.style.display = 'none';
        }
    }
}

function showTokenExpiryWarning(minutesLeft) {
    // Create notification banner
    const banner = document.createElement('div');
    banner.style.cssText = `
        position: fixed;
        top: 70px;
        left: 50%;
        transform: translateX(-50%);
        background: linear-gradient(135deg, #ff9800, #ff5722);
        color: white;
        padding: 15px 30px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: slideDown 0.3s ease;
        font-weight: 500;
    `;
    
    banner.innerHTML = `
        <div style="display: flex; align-items: center; gap: 15px;">
            <span style="font-size: 24px;">⚠️</span>
            <div>
                <div style="font-weight: 600; margin-bottom: 5px;">Token Expiring Soon!</div>
                <div style="font-size: 14px; opacity: 0.9;">
                    Your Upstox token expires in ${minutesLeft} minutes. 
                    System will attempt auto-refresh, or <a href="#" onclick="openSettingsModal(); return false;" style="color: white; text-decoration: underline;">refresh manually</a>.
                </div>
            </div>
            <button onclick="this.parentElement.parentElement.remove()" 
                    style="background: rgba(255,255,255,0.2); border: none; color: white; padding: 5px 10px; border-radius: 4px; cursor: pointer;">
                ✕
            </button>
        </div>
    `;
    
    document.body.appendChild(banner);
    
    // Auto-remove after 10 seconds
    setTimeout(() => {
        if (banner.parentElement) {
            banner.remove();
        }
    }, 10000);
}

function showTokenExpiredNotification() {
    // Create error notification
    const banner = document.createElement('div');
    banner.style.cssText = `
        position: fixed;
        top: 70px;
        left: 50%;
        transform: translateX(-50%);
        background: linear-gradient(135deg, #f44336, #d32f2f);
        color: white;
        padding: 15px 30px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: slideDown 0.3s ease;
        font-weight: 500;
    `;
    
    banner.innerHTML = `
        <div style="display: flex; align-items: center; gap: 15px;">
            <span style="font-size: 24px;">❌</span>
            <div>
                <div style="font-weight: 600; margin-bottom: 5px;">Token Expired!</div>
                <div style="font-size: 14px; opacity: 0.9;">
                    Your Upstox token has expired. 
                    <a href="#" onclick="openSettingsModal(); return false;" style="color: white; text-decoration: underline; font-weight: 600;">
                        Click here to refresh
                    </a> to restore functionality.
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(banner);
}

// Add CSS animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideDown {
        from {
            opacity: 0;
            transform: translate(-50%, -20px);
        }
        to {
            opacity: 1;
            transform: translate(-50%, 0);
        }
    }
    
    .token-status {
        display: none;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        background: rgba(0, 0, 0, 0.1);
        border-radius: 6px;
        font-size: 13px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .token-status:hover {
        background: rgba(0, 0, 0, 0.15);
    }
    
    .token-icon {
        font-size: 16px;
    }
`;
document.head.appendChild(style);


// ============================================
// TRIGGER ML TRAINING (GLOBAL FUNCTION)
// ============================================
window.triggerMLTraining = async function() {
    if (!confirm('Start ML model training with current data?\n\nThis may take several minutes and will train models using all available trade data.')) {
        return;
    }
    
    const button = event.target;
    button.disabled = true;
    button.textContent = '⏳ Training...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/ml-strategy/train-model`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Parse timestamp and convert to IST
            const trainedDate = new Date(data.trained_at);
            const istTime = trainedDate.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: true });
            alert(`✅ ML Training Complete!\n\nStatus: ${data.status}\nMessage: ${data.message}\nTrained at: ${istTime}`);
            console.log('✓ ML training completed:', data);
        } else {
            alert(`❌ Training Failed\n\n${data.detail || 'Unknown error'}`);
            console.error('ML training failed:', data);
        }
        
    } catch (error) {
        console.error('Error triggering ML training:', error);
        alert(`❌ Error: ${error.message}`);
    } finally {
        button.disabled = false;
        button.textContent = '🤖 Train ML Models';
    }
}

// ============================================
// RECENT SIGNALS MODAL (GLOBAL FUNCTIONS)
// ============================================
window.openRecentSignalsModal = function() {
    const modal = document.getElementById('recent-signals-modal');
    if (modal) {
        modal.style.display = 'block';
        refreshRecentSignalsModal();
    }
}

window.refreshRecentSignalsModal = async function() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/signals/recent`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.status !== 'success') {
            document.getElementById('recent-signals-modal-container').innerHTML = 
                '<div class="error-message">Unable to load recent signals</div>';
            return;
        }
        
        displayRecentSignalsModal(result.data);
        
    } catch (error) {
        console.error('Error fetching recent signals:', error);
        document.getElementById('recent-signals-modal-container').innerHTML = 
            '<div class="error-message">Error loading signals</div>';
    }
}

function displayRecentSignalsModal(signals) {
    const container = document.getElementById('recent-signals-modal-container');
    if (!container) return;
    
    if (!signals || signals.length === 0) {
        container.innerHTML = `
            <div class="no-trades-message" style="padding: 1.5rem; text-align: center; background: var(--bg-secondary); border-radius: 8px;">
                <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">📊</div>
                <div style="font-size: 0.9rem; color: var(--text-secondary);">
                    No signals generated yet today
                </div>
            </div>
        `;
        return;
    }
    
    let html = '<div style="display: grid; gap: 0.75rem;">';
    
    // Add paper mode indicator at top
    html += `
        <div style="padding: 0.5rem; background: rgba(59, 130, 246, 0.1); border-left: 3px solid #3b82f6; border-radius: 4px; font-size: 0.85rem;">
            <strong>📝 Paper Trading Mode</strong> - These signals were tested in simulation. No real money at risk.
        </div>
    `;
    
    signals.slice(0, 50).forEach(signal => {
        const timestamp = new Date(signal.timestamp).toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit'
        });
        
        const directionClass = signal.direction === 'CALL' ? 'call' : 'put';
        
        let statusClass, statusIcon, statusText;
        
        if (signal.status === 'executed') {
            statusClass = 'info';
            statusIcon = '📝';
            statusText = 'Paper Trade';
        } else if (signal.status === 'blocked_by_risk') {
            statusClass = 'warning';
            statusIcon = '⚠';
            statusText = 'Blocked';
        } else if (signal.status === 'execution_failed') {
            statusClass = 'error';
            statusIcon = '✗';
            statusText = 'Failed';
        } else {
            statusClass = 'secondary';
            statusIcon = '○';
            statusText = signal.status;
        }
        
        html += `
            <div class="signal-item" style="padding: 0.75rem; background: var(--bg-card); border-radius: 6px; border-left: 3px solid ${directionClass === 'call' ? '#10b981' : '#ef4444'};">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <span style="font-size: 0.75rem; color: var(--text-secondary);">${timestamp}</span>
                        <span class="strike-badge ${directionClass}">${signal.direction}</span>
                        <strong>${signal.symbol} ${signal.strike || ''}</strong>
                    </div>
                    <span class="status-badge ${statusClass}" style="font-size: 0.75rem; padding: 0.25rem 0.5rem;">
                        ${statusIcon} ${statusText}
                    </span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 0.5rem; font-size: 0.8rem;">
                    <div>
                        <span style="color: var(--text-secondary);">Strategy:</span> 
                        <strong>${signal.strategy_id || signal.strategy || 'N/A'}</strong>
                    </div>
                    <div>
                        <span style="color: var(--text-secondary);">Entry:</span> 
                        <strong>₹${(signal.entry_price || 0).toFixed(2)}</strong>
                    </div>
                    <div>
                        <span style="color: var(--text-secondary);">Target:</span> 
                        <strong>₹${(signal.target_price || 0).toFixed(2)}</strong>
                    </div>
                    <div>
                        <span style="color: var(--text-secondary);">Strength:</span> 
                        <strong>${(signal.strength || 0).toFixed(0)}</strong>
                    </div>
                    <div>
                        <span style="color: var(--text-secondary);">ML Score:</span> 
                        <strong>${((signal.ml_probability || 0) * 100).toFixed(0)}%</strong>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

