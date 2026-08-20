# 指标定义

## 样本单位

一个样本是一个在 `T0` 冻结的“假设 × 评价期限 × 基准”。同一股票的5日和20日实验是两个样本，但必须共享同一原始假设快照。

## 结果指标

- `actual_return_pct`：按冻结规则可成交的起止价格计算。
- `benchmark_return_pct`：同期冻结基准收益。
- `excess_return_pct = actual_return_pct - benchmark_return_pct`。
- `MFE`：评价期内最大有利波动。
- `MAE`：评价期内最大不利波动。
- `max_drawdown`：评价期内从峰值到谷值的最大跌幅。
- `recovery_rate`：冲击后已收复幅度除以初始冲击幅度；需保存具体定义。

## 聚合指标

- 胜率：盈利样本数除以已结算样本数；持平进入分母。
- 盈亏比：盈利样本平均收益除以亏损样本平均亏损绝对值。
- 利润因子：总盈利除以总亏损绝对值。
- 期望收益：样本净收益均值，不能由胜率替代。
- Brier分数：`mean((预测成功概率 - 实际结果)^2)`，只对可二元判定的赢/亏样本计算。

胜率必须同时展示样本数。小样本优先给 Wilson 区间或 Beta 后验区间，不以单一百分比宣称稳定能力。

## 分组

至少按以下维度分组，数据不足时不强行细分：

```text
model_version
horizon_trade_days
market_regime
improvement_type
signal_state
```
