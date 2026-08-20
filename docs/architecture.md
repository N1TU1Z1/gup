# 项目架构

## 目标

项目按“发现、解释、执行、评价”分层。市场扫描产生候选，经济模型建立假设，交易生命周期维护触发与退出，模型评价负责胜率和反思。任何一层都不能用自己的分数替代下一层的职责。

## 目录所有权

| 目录 | 所有权 | 允许存放 | 不应存放 |
|---|---|---|---|
| `.agents/skills/` | Skill接口 | `SKILL.md`、按需参考、Skill专用脚本 | 行情数据库、构建缓存 |
| `stock-screener/references/strategies/` | 市场发现 | 候选召回形态和过滤规则 | 完整投资结论、胜率结果 |
| `stock-screener/scripts/` | 行情适配 | eltdx包装、扫描和热力图采集 | 持仓或券商写操作 |
| `stock-screener/heatmap/` | 展示应用 | Next.js代码、前端资源和依赖声明 | 私有持仓数据 |
| `持仓/` | 决策台账 | 主数据库、基础schema、人工说明 | 行情构建缓存 |
| `持仓/migrations/` | 数据库演进 | 只追加的版本迁移 | 截图、临时查询 |
| `持仓/imports/` | 数据导入 | 可追溯的持仓或历史补录SQL | schema定义 |
| `持仓/queries/` | 只读查询 | 日报、复盘和统计SQL | 修改schema的语句 |
| `data/` | 运行数据 | 市场快照、WAL和派生缓存 | Skill说明文档 |
| `docs/` | 项目文档 | 架构、约定和模型演进说明 | 可执行代码 |
| `tests/` | 验证 | 单元测试与只读探针 | 生产数据库 |

## Skill数据流

```text
$stock-screener
  scan_run_id
      |
      v
$investment-model
  model_version + hypothesis_id + PF
      |
      v
$trade-lifecycle
  plan_id + PR(h) + 触发/退出
      |
      v
$model-evaluator
  experiment_id + 绩效 + 反思
```

`$investment-workflow` 只编排这条链，不重复专业计算。

## 兼容路径

`stock-screener/` 仍是市场扫描Skill的实际目录；`.agents/skills/stock-screener` 是发现入口软链接。热力图和Python脚本保持原路径，避免破坏现有命令、测试和本地MCP配置。

## 文件维护规则

1. 新的策略形态进入 `stock-screener/references/strategies/`，不要放回Skill根目录。
2. 数据库变化创建新的编号迁移，同时同步 `持仓/schema.sql`。
3. 历史导入只追加到 `持仓/imports/`，不覆盖旧文件。
4. 复盘查询保持只读并放入 `持仓/queries/`。
5. SQLite、持仓截图、虚拟环境、依赖和构建缓存只保留本地，不进入版本控制。
6. 不移动开放中的SQLite数据库；运行时出现的 `-wal` 和 `-shm` 文件由SQLite管理。
7. 候选、计划、实验和评价只写SQLite；需要人工摘要时由只读查询生成，不维护第二份Markdown台账。
