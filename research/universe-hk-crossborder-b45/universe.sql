-- hk_crossborder: cross-border / HK-tagged ETFs (hk filter)
-- full_pool: top ~280 equity ETFs by avg turnover Jul-Sep 2025 >= 25M

-- Group A: hk_crossborder
-- Tags: 跨境ETF or 港股通基金, plus 投资区域 in (香港, 中国香港和美国)
SELECT DISTINCT s.SecuCode, s.SecuAbbr, s.InnerCode
FROM secumain s
JOIN mf_fundtagchange t ON t.innercode = s.InnerCode AND t.ifeffected = 1
WHERE s.SecuAbbr LIKE '%ETF%'
  AND (
    (t.labelname IN ('ETF基金分类', '深交所ETF分类', '上交所ETF分类') AND t.labeldataname = '跨境ETF')
    OR t.labeldataname = '港股通基金'
  )
  AND EXISTS (
    SELECT 1 FROM mf_fundtagchange t2
    WHERE t2.innercode = s.InnerCode AND t2.ifeffected = 1
      AND t2.labelname = '投资区域'
      AND t2.labeldataname IN ('香港', '中国香港和美国')
  );

-- Group B: full_pool (run separately in application code)
-- SELECT s.SecuCode, s.SecuAbbr, AVG(h.TurnoverValue) AS avg_tv
-- FROM qt_fundsperformancehis h
-- JOIN secumain s ON s.InnerCode = h.InnerCode
-- JOIN mf_fundarchives a ON a.InnerCode = h.InnerCode
-- WHERE h.TradingDay BETWEEN '2025-07-01' AND '2025-09-30'
--   AND s.SecuAbbr LIKE '%ETF%'
--   AND a.FundType NOT LIKE '%债券%' AND a.FundType NOT LIKE '%货币%'
--   AND a.FundType NOT LIKE '%黄金%' AND a.FundType NOT LIKE '%商品%'
--   AND a.FundType NOT LIKE '%短融%'
--   AND (s.SecuAbbr NOT LIKE '%黄金%' AND s.SecuAbbr NOT LIKE '%债%' AND s.SecuAbbr NOT LIKE '%短融%')
-- GROUP BY s.SecuCode, s.SecuAbbr
-- HAVING avg_tv >= 25000000
-- ORDER BY avg_tv DESC
-- LIMIT 280;
