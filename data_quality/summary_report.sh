#!/bin/bash
# Data Quality Summary Report

clear
echo "================================================================================"
echo "OPTION CHAIN DATA QUALITY SUMMARY"
echo "================================================================================"
echo ""

echo "📊 Overall Statistics:"
echo "--------------------------------------------------------------------------------"
docker exec trading_db psql -U trading_user -d trading_db -c "
SELECT 
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE data_quality_flag = 'CLEAN') as clean,
    COUNT(*) FILTER (WHERE data_quality_flag = 'SUSPECT') as suspect,
    COUNT(*) FILTER (WHERE data_quality_flag = 'BAD') as bad,
    ROUND(COUNT(*) FILTER (WHERE data_quality_flag = 'CLEAN') * 100.0 / COUNT(*), 2) as clean_pct
FROM option_chain_snapshots;
"

echo ""
echo "📅 Daily Quality Breakdown:"
echo "--------------------------------------------------------------------------------"
docker exec trading_db psql -U trading_user -d trading_db -c "
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE data_quality_flag = 'CLEAN') as clean,
    ROUND(COUNT(*) FILTER (WHERE data_quality_flag = 'CLEAN') * 100.0 / COUNT(*), 2) as clean_pct,
    COUNT(*) FILTER (WHERE data_quality_flag = 'BAD') as bad,
    COUNT(*) FILTER (WHERE data_quality_flag = 'SUSPECT') as suspect
FROM option_chain_snapshots
GROUP BY DATE(timestamp)
ORDER BY date;
"

echo ""
echo "🔍 Top Quality Issues:"
echo "--------------------------------------------------------------------------------"
docker exec trading_db psql -U trading_user -d trading_db -c "
SELECT 
    UNNEST(string_to_array(quality_issues, ';')) as issue,
    COUNT(*) as count
FROM option_chain_snapshots
WHERE quality_issues IS NOT NULL AND quality_issues != ''
GROUP BY issue
ORDER BY count DESC
LIMIT 10;
"

echo ""
echo "📈 Symbol-wise Quality:"
echo "--------------------------------------------------------------------------------"
docker exec trading_db psql -U trading_user -d trading_db -c "
SELECT 
    symbol,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE data_quality_flag = 'CLEAN') as clean,
    ROUND(COUNT(*) FILTER (WHERE data_quality_flag = 'CLEAN') * 100.0 / COUNT(*), 2) as clean_pct
FROM option_chain_snapshots
GROUP BY symbol
ORDER BY symbol;
"

echo ""
echo "💡 Usage:"
echo "--------------------------------------------------------------------------------"
echo "  • Clean data view: SELECT * FROM option_chain_snapshots_clean;"
echo "  • Check bad data: SELECT * FROM option_chain_snapshots WHERE data_quality_flag = 'BAD';"
echo "  • Detailed logs: ls -lh data_quality/logs/"
echo ""
echo "================================================================================"
