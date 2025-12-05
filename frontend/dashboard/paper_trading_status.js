/**
 * Paper Trading Status Loader
 * Reads live status from paper_trading_status.json and updates dashboard
 */

// Poll for paper trading status every 5 seconds
async function loadPaperTradingStatus() {
    try {
        const response = await fetch('/paper_trading_status.json');
        const status = await response.json();
        
        // Update capital display
        updateCapitalDisplay(status);
        
        // Update strategies display
        updateStrategiesDisplay(status);
        
        // Update SAC allocation visualization
        updateSACVisualization(status);
        
    } catch (error) {
        console.error('Failed to load paper trading status:', error);
    }
}

function updateCapitalDisplay(status) {
    // Find capital element and update it
    const capitalElement = document.querySelector('#portfolio-capital, .portfolio-value, [data-field="capital"]');
    if (capitalElement) {
        const capital = status.capital || 0;
        const pnl = status.total_pnl || 0;
        const pnlClass = pnl >= 0 ? 'positive' : 'negative';
        
        capitalElement.innerHTML = `
            <div style="font-size: 2rem; font-weight: bold;">₹${(capital/100000).toFixed(2)}L</div>
            <div style="font-size: 1rem; color: ${pnl >= 0 ? '#10b981' : '#ef4444'};">
                P&L: ₹${pnl.toFixed(2)} (${(pnl/status.initial_capital*100).toFixed(3)}%)
            </div>
        `;
    }
    
    // Update any other capital displays
    document.querySelectorAll('[data-capital]').forEach(el => {
        el.textContent = '₹' + (status.capital/100000).toFixed(2) + 'L';
    });
}

function updateStrategiesDisplay(status) {
    // Find strategies section
    const strategiesSection = document.querySelector('#active-strategies, .strategies-list, [data-section="strategies"]');
    if (!strategiesSection) {
        // Create a new section if it doesn't exist
        createStrategiesSection(status);
        return;
    }
    
    const strategiesHTML = `
        <h3>🎯 Active Strategies (${status.active_strategies})</h3>
        <div class="strategies-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1rem;">
            ${Object.entries(status.strategies).map(([name, config]) => `
                <div class="strategy-card" style="padding: 1rem; background: var(--card-bg, #1a1a2e); border-radius: 8px; border-left: 3px solid #10b981;">
                    <div style="font-weight: 600; margin-bottom: 0.5rem;">${name.replace(/_/g, ' ').toUpperCase()}</div>
                    <div style="font-size: 0.9rem; color: var(--text-secondary, #9ca3af);">
                        Allocation: <strong>${(config.allocation * 100).toFixed(0)}%</strong>
                    </div>
                    <div style="font-size: 0.8rem; color: #10b981; margin-top: 0.25rem;">
                        ✅ ${config.enabled ? 'Active' : 'Disabled'}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
    
    strategiesSection.innerHTML = strategiesHTML;
}

function updateSACVisualization(status) {
    if (!status.sac_enabled || !status.sac_allocation) {
        return;
    }
    
    // Find SAC section
    let sacSection = document.querySelector('#sac-allocation, .sac-visualization, [data-section="sac"]');
    if (!sacSection) {
        sacSection = createSACSection();
    }
    
    const allocation = status.sac_allocation;
    const topGroups = status.top_groups || [];
    
    const strategyNames = ['Quantum Edge V2', 'Quantum Edge', 'Default', 'Gamma Scalping', 'VWAP Deviation', 'IV Rank Trading'];
    
    const sacHTML = `
        <h3>🧠 SAC Strategy Allocations</h3>
        <div class="sac-bars" style="margin-top: 1rem;">
            ${allocation.map((value, index) => {
                const percentage = (value * 100).toFixed(1);
                const isTop = topGroups.includes(index);
                const barColor = isTop ? '#10b981' : '#6366f1';
                const strategyName = strategyNames[index] || `Strategy ${index}`;
                
                return `
                    <div class="allocation-bar" style="margin-bottom: 0.75rem;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem; font-size: 0.85rem;">
                            <span>${strategyName} ${isTop ? '⭐' : ''}</span>
                            <span style="font-weight: 600;">${percentage}%</span>
                        </div>
                        <div style="background: rgba(99, 102, 241, 0.1); border-radius: 4px; height: 8px; overflow: hidden;">
                            <div style="background: ${barColor}; height: 100%; width: ${percentage}%; transition: width 0.5s;"></div>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
        <div style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-secondary, #9ca3af);">
            <strong>Top 3 Strategies:</strong> ${topGroups.map(g => strategyNames[g] || `Strategy ${g}`).join(', ')}
        </div>
        <div style="margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-secondary, #9ca3af);">
            Last updated: ${new Date(status.timestamp).toLocaleTimeString()}
        </div>
    `;
    
    sacSection.innerHTML = sacHTML;
}

function createStrategiesSection(status) {
    const dashboard = document.querySelector('.dashboard-content');
    if (!dashboard) return;
    
    const section = document.createElement('div');
    section.id = 'active-strategies';
    section.className = 'card';
    section.style.cssText = 'margin: 1rem; padding: 1.5rem; background: var(--card-bg, #1a1a2e); border-radius: 12px;';
    dashboard.appendChild(section);
    
    updateStrategiesDisplay(status);
}

function createSACSection() {
    const dashboard = document.querySelector('.dashboard-content');
    if (!dashboard) return null;
    
    const section = document.createElement('div');
    section.id = 'sac-allocation';
    section.className = 'card';
    section.style.cssText = 'margin: 1rem; padding: 1.5rem; background: var(--card-bg, #1a1a2e); border-radius: 12px;';
    dashboard.appendChild(section);
    
    return section;
}

// Start polling when page loads
document.addEventListener('DOMContentLoaded', () => {
    // Load immediately
    loadPaperTradingStatus();
    
    // Then poll every 5 seconds
    setInterval(loadPaperTradingStatus, 5000);
    
    console.log('📊 Paper Trading Status Loader initialized');
});

// Export for manual refresh
window.refreshPaperTradingStatus = loadPaperTradingStatus;
