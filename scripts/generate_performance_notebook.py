#!/usr/bin/env python3
"""
Generate Performance Autopsy Jupyter Notebook
"""
import nbformat as nbf
from pathlib import Path

# Create notebook
nb = nbf.v4.new_notebook()

# Add cells
nb['cells'] = [
    nbf.v4.new_markdown_cell("# 📊 Performance Autopsy - November 20, 2025\n\n**System**: NIFTY/SENSEX Algo Trading  \n**Mode**: Paper Trading  \n**SAC**: Active"),
    
    nbf.v4.new_code_cell("""import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import json

# Load paper trading data
with open('../frontend/dashboard/paper_trading_status.json', 'r') as f:
    data = json.load(f)

capital = data['capital']
initial = data['initial_capital']
total_pnl = data['total_pnl']

print(f"Capital: ₹{capital:,.2f}")
print(f"Total P&L: ₹{total_pnl:,.2f} ({(total_pnl/initial*100):.4f}%)")"""),
    
    nbf.v4.new_markdown_cell("## SAC Allocations"),
    
    nbf.v4.new_code_cell("""sac_alloc = data['sac_allocation']
strategies = list(data['strategies'].keys())

fig = go.Figure(data=[go.Bar(x=[f"Group {i}" for i in range(len(sac_alloc))], y=[a*100 for a in sac_alloc])])
fig.update_layout(title="SAC Meta-Controller Allocations", yaxis_title="Allocation %")
fig.show()"""),
    
    nbf.v4.new_markdown_cell("## Strategy Configuration"),
    
    nbf.v4.new_code_cell("""strat_df = pd.DataFrame([
    {'Strategy': k, 'Enabled': v['enabled'], 'Allocation': v['allocation']*100}
    for k, v in data['strategies'].items()
])
strat_df"""),
]

# Save notebook
output_path = Path(__file__).parent.parent / "reports/current_performance_autopsy_nov20.ipynb"
output_path.parent.mkdir(exist_ok=True)

with open(output_path, 'w') as f:
    nbf.write(nb, f)

print(f"✅ Notebook generated: {output_path}")
