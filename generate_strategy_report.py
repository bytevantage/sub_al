"""
Generate Comprehensive Strategy Performance Report
Executes Jupyter notebook and exports to HTML/PDF
"""

import subprocess
import os
import sys

print("="*80)
print("STRATEGY PERFORMANCE AUTOPSY - REPORT GENERATOR")
print("="*80)

# Check if jupyter is installed
try:
    result = subprocess.run(['jupyter', '--version'], capture_output=True, text=True)
    print(f"✓ Jupyter version: {result.stdout.strip()}")
except:
    print("❌ Jupyter not found. Installing...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'jupyter', 'nbconvert'])

# Check for required libraries
print("\nChecking dependencies...")
required = ['pandas', 'numpy', 'matplotlib', 'seaborn', 'plotly', 'kaleido']
for lib in required:
    try:
        __import__(lib)
        print(f"  ✓ {lib}")
    except:
        print(f"  Installing {lib}...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', lib], capture_output=True)

# Execute notebook
print("\n" + "="*80)
print("EXECUTING ANALYSIS NOTEBOOK...")
print("="*80)

notebook_path = 'reports/strategy_autopsy_2025.ipynb'

try:
    # Execute the notebook
    result = subprocess.run([
        'jupyter', 'nbconvert',
        '--to', 'notebook',
        '--execute',
        '--inplace',
        notebook_path
    ], capture_output=True, text=True, timeout=300)
    
    if result.returncode == 0:
        print("✓ Notebook executed successfully")
    else:
        print(f"⚠️  Notebook execution had warnings:\n{result.stderr}")
    
    # Export to HTML
    print("\nExporting to HTML...")
    result = subprocess.run([
        'jupyter', 'nbconvert',
        '--to', 'html',
        notebook_path,
        '--output', 'strategy_autopsy_2025.html'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✓ HTML report generated: reports/strategy_autopsy_2025.html")
    else:
        print(f"❌ HTML export failed: {result.stderr}")
    
    # Export to PDF (requires additional dependencies)
    print("\nExporting to PDF...")
    try:
        result = subprocess.run([
            'jupyter', 'nbconvert',
            '--to', 'pdf',
            notebook_path,
            '--output', 'strategy_autopsy_2025.pdf'
        ], capture_output=True, text=True, timeout=180)
        
        if result.returncode == 0:
            print("✓ PDF report generated: reports/strategy_autopsy_2025.pdf")
        else:
            print(f"⚠️  PDF export failed (may need LaTeX installed): {result.stderr[:200]}")
            print("   HTML report is still available!")
    except Exception as e:
        print(f"⚠️  PDF generation skipped: {e}")
        print("   HTML report is available!")
    
    print("\n" + "="*80)
    print("REPORT GENERATION COMPLETE!")
    print("="*80)
    print(f"\n📊 View report:")
    print(f"   Notebook: {os.path.abspath(notebook_path)}")
    print(f"   HTML: {os.path.abspath('reports/strategy_autopsy_2025.html')}")
    if os.path.exists('reports/strategy_autopsy_2025.pdf'):
        print(f"   PDF: {os.path.abspath('reports/strategy_autopsy_2025.pdf')}")
    
except subprocess.TimeoutExpired:
    print("❌ Notebook execution timed out")
except Exception as e:
    print(f"❌ Error: {e}")

print()
