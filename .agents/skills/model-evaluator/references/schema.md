# 决策台账结构

结构化源数据位于项目的 `持仓/holdings.sqlite3`，建表定义位于 `持仓/migrations/migration_003_investment_model.sql`。

## 主链

```text
recommendations
  -> investment_hypotheses
  -> probability_estimates
  -> trade_plans
  -> position_observations
  -> model_experiments
  -> model_evaluations
  -> model_reflections
```

`model_versions` 管理模型定义；`trade_plan_condition_orders` 关联本地交易计划和已有条件单。

## 不变量

- 冻结实验只追加评价，不覆盖预测。
- `model_evaluations.experiment_id` 唯一。
- `model_performance` 只统计 `win`、`loss` 和 `flat`。
- 无效实验、未到期实验和缺少基准的实验不进入胜率。
- 所有 JSON 文本应保存字段版本；读取方不得假设未知键不存在。
