# A股投资研究系统

本项目将全市场扫描、经济模型、交易生命周期和模型验证分层，目标是保存每次决策当时的证据并允许未来数据证伪，而不是只生成一次性荐股结论。

## 目录

```text
.
├── .agents/skills/          # Codex可发现的五个Skill入口
├── stock-screener/          # 市场扫描Skill实现、策略参考、行情脚本与热力图
│   ├── references/strategies/
│   ├── scripts/
│   └── heatmap/
├── 持仓/                    # 私有持仓数据库与SQL资产
│   ├── migrations/
│   ├── imports/
│   └── queries/
├── data/                    # 行情快照和热力图运行数据
├── docs/                    # 项目架构和维护约定
└── tests/                   # MCP、行情与热力图测试
```

完整边界见[项目架构](docs/architecture.md)。`.agents/skills/stock-screener` 保留为指向 `stock-screener/` 的兼容软链接。

## 能力分层

| 层 | Skill | 责任 |
|---|---|---|
| 工作流 | `$investment-workflow` | 编排每日扫描、研究、跟踪与复盘 |
| 市场发现 | `$stock-screener` | 全市场基数扫描、榜单召回、实时刷新与候选复核 |
| 经济模型 | `$investment-model` | 因果链、相对竞争优势、资本效率和基本面概率PF |
| 交易生命周期 | `$trade-lifecycle` | 重定价概率PR(h)、触发、条件单、持仓观察和退出 |
| 模型评价 | `$model-evaluator` | 胜率、期望值、超额收益、概率校准与错误归因 |

策略形态只负责召回候选，不能绕过经济模型和交易生命周期直接成为买入结论。

## 数据主链

```text
scan_run_id
-> model_version
-> hypothesis_id
-> probability_estimate_id
-> plan_id
-> experiment_id
```

上面的 `model_version` 在假设创建前确定；它表示当前使用的模型定义，不等于已经通过样本外验证。

- `data/market_heatmap.sqlite3`：全市场行情快照和热力图批次。
- `持仓/holdings.sqlite3`：持仓、推荐、条件单、投资假设、交易计划和模型实验。
- `持仓/schema.sql`：完整新建结构。
- `持仓/migrations/migration_003_investment_model.sql`：现有持仓数据库的增量升级。

## 每日流程

1. 开盘前读取持仓、开放计划、到期实验和上一交易日市场状态。
2. 竞价或盘中执行全市场扫描，冻结实时复核后的候选。
3. 对候选建立可证伪投资假设，再制定期限相关的交易计划。
4. 持仓期间追加观察，优先检查失效与退出窗口。
5. 收盘后冻结新实验并结算到期样本；未到期样本不进入胜率。

模型记分卡只读查询：

```sh
.venv-eltdx/bin/python .agents/skills/model-evaluator/scripts/model_scorecard.py
```

本项目仅用于研究与决策记录，不执行自动下单，也不承诺收益。
