# 交易生命周期状态机

```text
candidate -> researched -> planned -> active -> triggered -> holding
                                                |           |
                                                v           v
                                           invalidated   reduced
                                                |           |
                                                +-----> closed -> evaluated
```

## 状态含义

- `candidate`：仅由扫描召回。
- `researched`：存在冻结的投资假设。
- `planned`：已生成本地计划，未确认券商条件单。
- `active`：用户确认条件单或观察计划已经生效。
- `triggered`：触发条件发生，尚未等同于实际成交。
- `holding`：用户确认实际持仓或成交。
- `reduced`：已确认部分减仓。
- `invalidated`：研究或价格失效，但可能尚未成交退出。
- `closed`：用户确认退出或计划到期关闭。
- `evaluated`：达到评价期限并完成结果结算。

## 不变量

1. 不能从 `candidate` 直接跳到 `holding`，除非补录历史成交且标记来源。
2. `triggered` 不等于 `executed`。
3. 普通A股当日新开仓即使失效，也只能记录最早可成交退出时间。
4. 历史状态只追加，不覆盖；修正错误应保存修正原因。
