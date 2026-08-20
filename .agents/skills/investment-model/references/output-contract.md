# 投资假设输出契约

冻结记录至少包含以下字段。未知字段使用 `null` 并解释原因，不得省略关键不确定性。

```yaml
hypothesis_id: ""
model_version: ""
recommendation_id: null
full_code: ""
stock_name: ""
created_at: ""
evidence_as_of: ""
benchmark_code: ""

evidence_ledger:
  - claim_id: ""
    claim_type: unknown
    claim: ""
    source_id: null
    source_kind: null
    published_at: null
    observed_at: null
    reporting_period: null
    raw_value: null
    unit: null
    formula: null
    derived_value: null
    available_at_t0: null
    freshness: unknown
    evidence_family: null

target_definition:
  horizon: ""
  improvement_event: ""
  threshold: null
  accounting_basis: "core"

data_reliability_gate:
  state: unknown
  audit_opinion: null
  accounting_restatement: null
  governance_issues: []
  legal_tax_rights: []
  evidence: []

model_audit:
  overall_status: fail
  hallucination_status: unknown
  exclusivity_status: unknown
  exhaustiveness_status: unknown
  probability_status: unknown
  double_counting_status: unknown
  state_elimination_status: unknown
  hysteresis_status: unknown
  blockers: []
  downgraded_claims: []
  required_evidence: []

causal_chain:
  industry: {state: unknown, evidence: []}
  technology_route: {state: unknown, evidence: []}
  company_share: {state: unknown, evidence: []}
  revenue_conversion: {state: unknown, evidence: []}
  profit_conversion: {state: unknown, evidence: []}
  cashflow_conversion: {state: unknown, evidence: []}

six_gates:
  change_detected: null
  causal_mechanism: null
  relative_advantage: null
  capital_efficiency: null
  persistence: null
  market_implied_expectation:
    state: unknown
    evidence: []
    note: "只传递给交易生命周期，不改变PF"

improvement_type: unknown
quality_state: unknown
predicted_pf: null
pf_range: [null, null]
theme_conversion_score: null
data_confidence: low
thesis: ""

cashflow_bridge:
  core_profit: null
  non_cash_items: null
  inventory_release: null
  receivables_release: null
  payables_increase: null
  one_off_operating_cash: null
  interpretation: unknown

market_conditioning:
  required: false
  observed_at: null
  session_basis: null
  data_sufficiency: unknown
  threshold_set_id: null
  classification_rule_id: null
  sentiment_level: null
  sentiment_delta: null
  sentiment_acceleration: null
  primary_regime: null
  transition_candidate: null
  regime_confidence: low
  breadth: null
  profit_effect: null
  risk_appetite: null
  news_reaction: null
  volume_crowding: null
  counterevidence: []
  engine_route: null
  regime_lock:
    lock_rule_id: null
    active_engine: null
    candidate_engine: null
    entered_at: null
    minimum_dwell_observations: null
    observations_in_lock: null
    required_consecutive_confirmations: null
    current_consecutive_confirmations: null
    enter_condition: null
    exit_condition: null
    emergency_exit_condition: null
    switch_status: unchanged
    switch_reason: null
  note: "市场状态和引擎路由不改变PF；PR(h)交给trade-lifecycle"

state_partition:
  partition_id: null
  target: null
  horizon: null
  settlement_at: null
  benchmark: null
  settlement_priority: []
  mutually_exclusive: null
  collectively_exhaustive: null
  residual_state: null
  probability_source: unavailable
  point_probability_sum: null
  range_probability_coherent: null
  hypotheses:
    - state_id: null
      definition: null
      settlement_rule: null
      prior_probability: null
      prior_range: [null, null]
      posterior_probability: null
      posterior_range: [null, null]
      evidence_for: []
      evidence_against: []
      falsification: []

state_elimination_updates:
  - update_id: null
    evidence_id: null
    affected_state: null
    update_type: unchanged
    causal_mechanism: null
    likelihood_direction: null
    reversible: null
    reason: null

lottery_odds_bridge:
  owner: trade-lifecycle
  mutually_exclusive: null
  collectively_exhaustive: null
  probability_sum: null
  joint_scenarios:
    - joint_state_id: null
      fundamental_state: null
      future_market_state: null
      repricing_state: null
      probability: null
      probability_source: unavailable
      payoff_input_status: missing
      conditional_tail_risks: []
  tail_risk_treatment: null
  ev_status: not_computed
  note: "本技能不计算净赔付和EV；不得把重叠尾部事件作为额外互斥状态"

scenarios:
  - name: base
    revenue_drivers: []
    margin_drivers: []
    working_capital_drivers: []
    capex_efficiency_drivers: []
    governance_legal_tax_drivers: []
    outcome: null
falsification_conditions: []
missing_evidence: []
next_validation_event: ""
status: frozen
```

`hypothesis_id` 应保持稳定。改变核心因果链、概率定义或失效条件时创建新假设或新模型版本，不更新原记录。

`market_conditioning` 在纯基本面任务中可以保持 `required: false` 和空值；一旦用于状态路由，必须冻结观察时点、盘前/盘后口径和可用数据。`profit_effect` 只能引用在 `evidence_as_of` 前已经走完观察窗口的历史队列。

`primary_regime` 只能保存一个 E1-E6 值；数据不足时为 `unclassified`。`transition_candidate` 不得参与当前状态概率求和。

`market_conditioning.regime_lock` 决定实际启用的引擎，不覆盖 `primary_regime`。其进入和退出条件、最短驻留期、连续确认数与紧急回退条件必须在 T0 冻结；未经校准不得填入看似精确的概率阈值。

`state_partition.hypotheses` 只有在同一目标、期限和结算规则下互斥且穷尽时才能填概率。点概率必须归一；区间必须通过可行性检查。没有概率依据时使用 `ordinal_only` 或 `unavailable`。

`state_elimination_updates.update_type` 只允许 `ruled_out`、`downweighted`、`unchanged` 或 `upweighted`。只有状态在冻结结算规则下已不可能成立时才使用 `ruled_out`；连续失败或暂未观察到风险不得作为排除依据。

`lottery_odds_bridge.joint_scenarios` 若进入 EV，也必须形成互斥且穷尽的联合终局并通过概率和检查；否则保持 `ev_status: not_computed`。

`scenarios` 是经济驱动叙事，默认不保证互斥。只有补齐结算规则并进入 `state_partition` 后，才允许参与彩票赔率和期望值计算。
