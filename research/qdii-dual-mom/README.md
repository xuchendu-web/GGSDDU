# 海外 QDII 双动量袖（研究）

独立书：研究池 `海外权益` QDII ETF，周频周五收盘信号（对齐 LIVE1430 周五调仓栅格），**不**接 A 股 breadth45。

## 规则（主簿 `QDII-DM-MA20-K3`）

- 绝对：`close > MA20` 且 `R12w > 0`
- 相对：按 `R12w` 降序，等权 Top3，`L≤1`，不合格全现金
- 成本：单边 0.1%（往返 0.2%）

## 复现

```bash
pip install -r requirements.txt
python scripts/build_panel.py
python scripts/run_backtest.py
pytest tests/
```

产物：`results/metrics.csv`、`fourpack.png`、`ATTRIBUTION.md`（由回测摘要更新）。
