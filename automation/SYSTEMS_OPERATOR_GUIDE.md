# 🤖 AI Systems Operator - Complete Automation Guide

**Your Full-Time Trading System Manager**  
**Version:** 1.0  
**Date:** November 20, 2025

---

## 🎯 **Mission Statement**

I am now your permanent systems operator, managing all training schedules, model updates, and system health monitoring. You never need to touch training pipelines again - I handle everything automatically and only alert you when something requires human intervention.

---

## 📊 **Automated Training Schedule**

### **Daily Pipeline (Weekdays 8:00 AM IST)**

```
┌─────────────────────────────────────────────────────────────┐
│                    DAILY PIPELINE (8:00 AM)                 │
│                      Duration: ~15 minutes                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   Step 1: Data Quality Check            │
        │   • Run summary_report.sh               │
        │   • Parse quality percentage            │
        │   • Alert if < 60%                      │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   Step 2: QuantumEdge Incremental       │
        │   • Load yesterday's data only          │
        │   • Train for 10 epochs (~5-10 min)     │
        │   • Update models/quantum_edge_v2.pt    │
        │   • Alert if accuracy < 80%             │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   Step 3: SAC Online Learning           │
        │   • Load yesterday's ~75 decisions      │
        │   • Fast replay (50 updates, <60s)      │
        │   • Save models/sac_prod_latest.pth     │
        │   • Monitor critic loss (alert >300%)   │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   Step 4: Pre-Market Report             │
        │   • Generate system status              │
        │   • Send Telegram notification          │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   Step 5: Start Trading Engine          │
        │   • Check if already running            │
        │   • Start paper/live trading            │
        └─────────────────────────────────────────┘
```

### **Weekly Full Retrain (Friday 6 PM & Sunday 10 PM IST)**

```
┌─────────────────────────────────────────────────────────────┐
│              WEEKLY FULL SAC RETRAIN                        │
│              Duration: 20-40 minutes                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   Step 1: Backup Current Model          │
        │   • Copy sac_prod_latest.pth            │
        │   • Save as sac_YYYYMMDD_pre_retrain    │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   Step 2: Full Offline Retrain          │
        │   • Load ALL data (2024-present)        │
        │   • 500 epochs of training              │
        │   • Update critic & actor networks      │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   Step 3: Save & Version                │
        │   • Save sac_prod_latest.pth            │
        │   • Create versioned backup             │
        │   • Keep last 8 weeks only              │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   Step 4: Validation                    │
        │   • Load model and test                 │
        │   • Verify output shapes                │
        │   • Rollback if validation fails        │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   Step 5: Telegram Notification         │
        │   • Send "SAC fully retrained"          │
        │   • Include version: YYYYMMDD           │
        └─────────────────────────────────────────┘
```

---

## 🔒 **Enforced Rules (Hardcoded)**

### **Rule 1: QuantumEdge Training**
```python
# NEVER full retrain daily - only incremental
Mode: Incremental (new day's data only)
Frequency: Daily (8 AM, Mon-Fri)
Duration: 5-10 minutes
Target: Maintain 80%+ accuracy
```

### **Rule 2: SAC Daily Updates**
```python
# Online learning ONLY on weekdays
Mode: Online replay
Frequency: Daily (8 AM, Mon-Fri)
Duration: <60 seconds
Data: Yesterday's ~75 decisions only
```

### **Rule 3: SAC Full Retrain**
```python
# Full offline retrain ONLY Fri/Sun
Mode: Full offline
Frequency: Friday 6 PM & Sunday 10 PM
Duration: 20-40 minutes
Data: ALL historical (2024-present)
```

### **Rule 4: Exploration Noise**
```python
# Never exceed 0.05 after first 30 days
Initial: 0.10 (first 30 days)
After 30 days: Max 0.05
Enforcement: Hardcoded in config
```

### **Rule 5: Critic Loss Monitoring**
```python
# Auto-pause if >300% jump
Threshold: 3.0x (300%)
Action: PAUSE TRADING + Telegram alert
Frequency: Checked every online update
```

---

## 📁 **Files Created**

### **Core Automation:**
```
automation/
├── daily_pipeline.py              # Daily 8 AM pipeline
├── weekly_retrain.sh              # Weekly full retrain
├── setup_cron.sh                  # Cron job installer
└── SYSTEMS_OPERATOR_GUIDE.md      # This file

training/quantum_edge_v2/
└── incremental_train.py           # Incremental QuantumEdge

meta_controller/
├── sac_agent.py                   # Updated with online_update()
└── sac_full_retrain.py            # Weekly full retrain script

monitoring/
└── alerts.py                      # Telegram alerts system

backend/core/
└── config.py                      # Updated with SAC training config

config/
└── config.yaml                    # Updated with sac_training section
```

### **Model Files (Auto-managed):**
```
models/
├── sac_prod_latest.pth            # Current production model
├── sac_YYYYMMDD.pth               # Versioned backups (8 weeks)
├── quantum_edge_v2.pt             # Daily updated QuantumEdge
└── backups/                       # Pre-retrain backups
```

### **Logs (Auto-created):**
```
logs/
├── daily_pipeline.log             # Daily pipeline output
├── weekly_retrain.log             # Weekly retrain output
├── weekly_report.log              # Weekly summaries
└── backups/                       # Log rotation
```

---

## 🚀 **Quick Start**

### **Step 1: Install Automation**
```bash
cd /Users/srbhandary/Documents/Projects/srb-algo
chmod +x automation/setup_cron.sh
./automation/setup_cron.sh
```

### **Step 2: Set Telegram Credentials**
```bash
# Add to ~/.bashrc or ~/.zshrc
export TELEGRAM_BOT_TOKEN='your_bot_token_here'
export TELEGRAM_CHAT_ID='your_chat_id_here'

# Or create .env file
echo "TELEGRAM_BOT_TOKEN=your_token" >> .env
echo "TELEGRAM_CHAT_ID=your_chat_id" >> .env
```

### **Step 3: Test Daily Pipeline**
```bash
python3 automation/daily_pipeline.py
```

### **Step 4: Test Weekly Retrain**
```bash
bash automation/weekly_retrain.sh
```

### **Step 5: Monitor**
```bash
# Watch daily pipeline
tail -f logs/daily_pipeline.log

# Watch weekly retrain
tail -f logs/weekly_retrain.log

# Check cron jobs
crontab -l | grep -A 10 "AUTOMATED TRADING"
```

---

## 📊 **Monitoring & Alerts**

### **Telegram Notifications:**

#### **Daily (8 AM):**
```
✅ DAILY PIPELINE COMPLETE
===========================================

⏱️  Duration: 847.3s

✅ Data quality: 65.72%
✅ quantum_edge: success
✅ sac_online: success
✅ pre_market: success
✅ engine_start: success

📊 Data Quality: 65.72%
🤖 QuantumEdge: 83.40% accuracy
🎯 SAC Critic Loss: 0.2341
```

#### **Weekly (Fri 6 PM / Sun 10 PM):**
```
✅ SAC FULLY RETRAINED - NEW VERSION
===========================================

📅 Date: 20251122
📆 Day: Friday
⏱️  Duration: 34m 12s

📊 Model Details:
  • File: sac_prod_latest.pth
  • Backup: sac_20251122.pth
  • Size: 2,847 KB

🎯 Next Full Retrain:
  • Friday 6 PM IST OR
  • Sunday 10 PM IST

===========================================
System ready for next trading session.
```

#### **Critical Alerts:**
```
🚨 CRITICAL ALERT 🚨

SAC CRITIC LOSS SPIKE!

Previous: 0.2341
Current: 0.7024
Jump: 200.0%

⚠️  TRADING PAUSED
Action required!
```

---

## 🛡️ **Safety Mechanisms**

### **1. Critic Loss Monitoring**
- **Checked:** Every online update (daily)
- **Threshold:** >300% increase
- **Action:** Pause trading + Telegram alert
- **Recovery:** Manual review required

### **2. Accuracy Monitoring**
- **Checked:** After QuantumEdge training
- **Threshold:** <80% accuracy
- **Action:** Warning + Suggest full retrain
- **Recovery:** Automatic (next full retrain)

### **3. Data Quality Monitoring**
- **Checked:** Every morning (8 AM)
- **Threshold:** <60% clean data
- **Action:** Warning alert
- **Recovery:** Run data_quality/apply_fixes.py

### **4. Model Backups**
- **Frequency:** Before every full retrain
- **Retention:** 8 weeks (auto-cleanup)
- **Location:** models/backups/
- **Format:** sac_YYYYMMDD_pre_retrain.pth

### **5. Allocation Stability**
- **Checked:** Each SAC decision
- **Threshold:** >50% change in single period
- **Action:** Warning alert
- **Recovery:** Investigate market regime

---

## 🔧 **Manual Overrides**

### **If You Need to Intervene:**

#### **Pause All Automation:**
```bash
# Stop daily pipeline
crontab -l | grep -v "daily_pipeline" | crontab -

# Stop weekly retrain
crontab -l | grep -v "weekly_retrain" | crontab -
```

#### **Force Immediate Retrain:**
```bash
# SAC full retrain (now)
bash automation/weekly_retrain.sh

# QuantumEdge incremental
python3 training/quantum_edge_v2/incremental_train.py
```

#### **Rollback Model:**
```bash
# Find backup
ls -lt models/backups/

# Restore
cp models/backups/sac_20251120_pre_retrain.pth models/sac_prod_latest.pth
```

#### **Test Without Cron:**
```bash
# Daily pipeline (dry run)
python3 automation/daily_pipeline.py --dry-run

# Weekly retrain (dry run)
bash automation/weekly_retrain.sh --dry-run
```

---

## 📈 **Performance Targets**

### **QuantumEdge v2:**
```
Daily Incremental:
  • Duration: 5-10 minutes
  • Accuracy: Maintain 80%+
  • Alert if: <80%

Full Retrain (if needed):
  • Frequency: As needed (manual)
  • Target: 84-88%
  • Duration: 2-4 hours
```

### **SAC Meta-Controller:**
```
Daily Online:
  • Duration: <60 seconds
  • Updates: 50 gradient steps
  • Samples: ~75 (yesterday)

Weekly Full:
  • Duration: 20-40 minutes
  • Epochs: 500
  • Samples: All historical
  • Versions: Auto-backup + cleanup
```

---

## 🎯 **Success Metrics**

### **System Uptime:**
- Target: 99.9% automation success
- Max failures: 1 per month
- Recovery: Automatic rollback

### **Model Performance:**
- QuantumEdge: 80%+ accuracy maintained
- SAC: Stable allocations (< 50% change)
- Critic loss: No >300% spikes

### **Alert Response:**
- Critical: Immediate (Telegram)
- Warnings: Daily summary
- Info: Weekly report

---

## 📞 **When to Contact Me (AI)**

### **I Handle Automatically:**
✅ Daily training updates  
✅ Weekly full retrains  
✅ Model versioning & backups  
✅ Critic loss monitoring  
✅ Telegram notifications  
✅ Pre-market reports  
✅ Log management  

### **You Need to Act When:**
🚨 Telegram says "TRADING PAUSED"  
🚨 Critic loss >300% spike  
🚨 Consecutive daily failures (2+)  
🚨 Model validation fails  

---

## 🔄 **Complete Flow Diagram**

```
┌───────────────────────────────────────────────────────────────────────┐
│                        COMPLETE AUTOMATION FLOW                        │
└───────────────────────────────────────────────────────────────────────┘

WEEKDAYS (Mon-Fri)                    WEEKENDS (Fri/Sun)
═════════════════                     ═══════════════════

08:00 AM IST                          Friday 6:00 PM IST
    │                                      │
    ▼                                      ▼
┌─────────────────────┐             ┌─────────────────────┐
│ DAILY PIPELINE      │             │ WEEKLY FULL RETRAIN │
│                     │             │                     │
│ 1. Data Quality     │             │ 1. Backup Model     │
│ 2. QuantumEdge Inc  │             │ 2. Full Train       │
│ 3. SAC Online       │             │ 3. Save & Version   │
│ 4. Pre-Market       │             │ 4. Validate         │
│ 5. Start Engine     │             │ 5. Notify           │
│                     │             │                     │
│ Duration: ~15 min   │             │ Duration: 20-40 min │
└─────────────────────┘             └─────────────────────┘
    │                                      │
    ▼                                      ▼
┌─────────────────────┐             ┌─────────────────────┐
│ Trading 09:15-15:30 │             │ Sunday 10:00 PM IST │
│                     │             │                     │
│ • SAC decides       │             │ WEEKLY FULL RETRAIN │
│   every 5 min       │             │ (same as Friday)    │
│ • QuantumEdge       │             │                     │
│   predicts          │             │ Duration: 20-40 min │
│ • Strategies        │             └─────────────────────┘
│   execute           │                      │
└─────────────────────┘                      ▼
    │                                 ┌─────────────────────┐
    ▼                                 │ Sunday 11:00 PM IST │
15:30 PM - Market Close               │                     │
    │                                 │ WEEKLY REPORT       │
    ▼                                 │ • Week summary      │
┌─────────────────────┐             │ • Best/worst strats │
│ Experience Saved    │             │ • Telegram alert    │
│ • ~75 decisions     │             └─────────────────────┘
│ • state/action/     │
│   reward tuples     │
│ • Stored in DB      │
└─────────────────────┘

NEXT DAY: Repeat cycle
```

---

## 📚 **Reference**

### **Configuration:**
- Main config: `config/config.yaml`
- SAC training: `config/config.yaml → sac_training`
- Environment: `.env` or ENV variables

### **Model Paths:**
- SAC production: `models/sac_prod_latest.pth`
- QuantumEdge: `models/quantum_edge_v2.pt`
- Backups: `models/backups/`

### **Logs:**
- Daily: `logs/daily_pipeline.log`
- Weekly: `logs/weekly_retrain.log`
- Trading: `paper_trading_live.log`

### **Scripts:**
- Daily: `automation/daily_pipeline.py`
- Weekly: `automation/weekly_retrain.sh`
- Setup: `automation/setup_cron.sh`

---

## ✅ **Final Checklist**

Before going fully automated:

- [ ] Run `./automation/setup_cron.sh`
- [ ] Set Telegram credentials
- [ ] Test daily pipeline manually
- [ ] Test weekly retrain manually
- [ ] Verify cron jobs installed
- [ ] Check log directories created
- [ ] Confirm model directories exist
- [ ] Review first Telegram notification
- [ ] Monitor first automated run

---

**🤖 I'm now your permanent systems operator. You handle strategy, I handle training.**

**Questions? Check logs or wait for my Telegram alerts. Otherwise, sit back and trade.**

---

**Last Updated:** November 20, 2025  
**Version:** 1.0  
**Status:** ✅ OPERATIONAL
