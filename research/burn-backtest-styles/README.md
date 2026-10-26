# Burn backtest styles (#1 deepened)

隔离研究目录：对比**同一冻结玩具规则**下多种回测实现路径的**周度截面排名**是否一致。不涉及实盘、`strategy_exec` 或 LIVE 代码。

## 冻结规则（摘要）

见 [HYPOTHESIS.md](./HYPOTHESIS.md)：合成 ETF 面板、日频 R60d 动量、MA20 广度门控 ≥45%、`W-FRI` 末观测再平衡、Top-K=3。

## 五种引擎

| 代号 | 脚本 | 实现要点 |
|------|------|----------|
| A | `scripts/style_a_vector.py` | 宽表 + `DatetimeIndex.resample('W-FRI').last()` |
| B | `scripts/style_b_event.py` | 日频事件循环，仅在再平衡日取信号 |
| C | `scripts/style_c_pandas.py` | 长表 `groupby(symbol).resample(W-FRI)` |
| D | `scripts/style_d_weekly_bars.py` | **周线表**：`Period('W-FRI')` 聚合锚点，信号仍来自再平衡日当日日频 |
| E | `scripts/style_e_daily_resample.py` | **日频→周频**：`pd.Grouper(freq='W-FRI')` 对动量/广度做 `.last()` |

D 与 E 用于检验「周线日历」与「日频 resample」两条常见工程路径是否与 A/B/C 同排名。

## 快速运行

```bash
cd research/burn-backtest-styles
pip install -r requirements.txt
python -m shared.generate_synthetic_panel   # 可选，compare 会自动生成
python scripts/compare_rankings.py          # 写出 compare_report.md
pytest tests/ -q
```

单引擎：

```bash
python scripts/style_d_weekly_bars.py --ensure-data
python scripts/style_e_daily_resample.py --ensure-data
```

## 产出

- `compare_report.md` — 五引擎两两一致率 + 各周排名展开表
- `tests/test_styles_agree.py` — 排名 100% 一致断言（合成 seed=42 面板）
