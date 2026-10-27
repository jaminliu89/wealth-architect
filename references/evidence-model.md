# 证据、主张与现金情景合同

版本：0.1.0；日期：2026年10月28日。执行前以随包 `scripts/radar.py` 为本版机器合同；本文件同时明确机器检查无法完成的语义核验。

## 分层与状态

原件/来源 → 可定位的事实主张 → 与本业务相关的推导 → 有界行动。不要用URL数量代替证据质量，也不要用结构校验通过替代事实和经营价值。

| status | 含义 |
|---|---|
| VERIFIED | 执行者声明已对照原始材料核验；仍须人工复核真实性、定位、口径和适用性，检查器不授予此身份 |
| COUNTERPARTY_CLAIM | 对手方或宣传方陈述，尚未独立确认 |
| ESTIMATE | 有显式方法和参数的估计，不能伪装成实测 |
| HYPOTHESIS | 待验证命题 |
| UNKNOWN | 关键事实或访问条件未知 |
| REJECTED | 已被反证或不适用；保留历史理由，不计支持 |

这些状态与原材料官方/私人来源、推理置信度是不同维度。官方材料证明发布内容，不保证该内容已变成你的经营结果。

## 本版 dossier JSON

顶层：`schema_version: 1`，`business`，`evidence`数组，`claims`数组，`scenarios`数组。`business`必含非空`name`、`region`、三位大写币种`currency`。`evidence`、`claims`各自ID唯一；引用必须存在且不可重复。

| evidence字段 | 要求与边界 |
|---|---|
| id、publisher | 非空，标识材料和发布者/提供者 |
| source_url | 无嵌入账号密码的`https://...`，或`urn:offline:<id>`（id仅字母数字下划线连字符）；不伪造公开URL |
| locator | 页/表/段/行；离线材料说明授权保存位置与提取点，不把秘密或个人资料写进公开包 |
| published_at / retrieved_at / expires_at | `YYYY-MM-DD`；公布≤获取且公布≤复核截止。获取晚于截止可保留，但不fresh。仅有取得日的线下记录如实采用记录形成日，不编造发布日期 |
| period、region、metric、unit | 非空；统计期、地域、指标、单位。不能以同名字段掩盖口径差异 |
| status、origin_id | 上述枚举；origin_id指共同原始来源，转载沿用同一origin |
| snapshot_sha256 | VERIFIED必填64位小写hex，由真实原件计算；不填占位摘要，检查器不下载原文或重算材料hash |

`claims`每项必含：`id`、非空`text`、`evidence_ids`数组、布尔`critical`、`stance: support|counter`。关键决策主张须标critical；相反主张用counter并保留引用，不从台账删去。

`scenarios`每项必含：唯一非空`name`、`currency`（必须与business完全一致）、`period: YYYY-MM/YYYY-MM`（起止月份合法且开始≤结束）、`opening_cash`、`revenue`、`cost`、`capex`、`working_capital`、`reserve`。六项金额必须有限非负数字，bool、NaN、Infinity拒绝。至少三个可比情景；情景期间不同会阻塞，先显式归一。混币输入拒绝；换算必须在输入前写明汇率、日期、来源与方法。

本版计算：

```text
cash_after_reserve = opening_cash + revenue - cost - capex - working_capital - reserve
```

这是同一期间、同一币种的净现金压力近似，不是IRR、估值、收益率预测，也不能代替分月收付款模型。`revenue`必须是同期实际或情景假设的收现收入；`cost`必须是同期现金支出，并说明覆盖的税费、固定/变动支出、融资及人工成本，不能直接填权责发生制营收/成本。`working_capital`仅填尚未体现在前述收付与capex中的额外新增资金占用；应收导致的未到账若已从revenue排除、库存采购若已计入cost，不可再次扣除。账期显著影响决策时另做分月情景，不能仅靠本式放行。opening_cash是本情景期初可支配现金，不含受限资金。reserve是需要留下的现金底线，不是已经发生的费用。

## 检查行为与退出码

执行 `python3 <installed-skill>/scripts/radar.py validate dossier.json --as-of YYYY-MM-DD`，as-of为真实决策截至日。证据只有在获取日≤as-of≤expires_at、地域字符串与business完全一致、status为VERIFIED时才成为本版可用引用。全国→地方、城市别名或跨区业务不能靠改字符串冒充适用，须真实复核并解释。

检查器把同origin_id、同source_url或同snapshot_sha256的引用传递归组，降低改名制造独立来源的风险；它不能识别所有未显式标明的转载关系或共同原始调查。

- 输入非法退出1，输出error。
- 材料合法但存在阻塞退出2，readiness为`EVIDENCE_INCOMPLETE`。
- 无机器阻塞退出0，readiness为`READY_FOR_HUMAN_REVIEW`，只允许进入实际复核。

阻塞包括：无critical主张；任一critical主张不足两个fresh、同地域、声明独立的VERIFIED来源组；有可用VERIFIED反证；少于三个不同名情景；情景期间不一致；任一情景cash_after_reserve为负。警告说明过期/截至日不可得或地域需复核。两个来源门槛和保守反证阻塞是首版启发式，不是统计置信度或真实性认证；有反证时应人工处理冲突并保留证据，不能删除反证来获得绿色状态。

## 合成示例：故意缺证

以下仅演示字段和缺证路径，不含真实生意或有效官方证据。保存后应得到EVIDENCE_INCOMPLETE，不能当成真实报告或通过样本。

```json
{
  "schema_version": 1,
  "business": {"name": "SYNTHETIC example", "region": "example-region", "currency": "CNY"},
  "evidence": [{
    "id": "e1", "source_url": "urn:offline:synthetic-note",
    "publisher": "synthetic fixture", "published_at": "2026-10-01",
    "retrieved_at": "2026-10-02", "expires_at": "2026-10-31",
    "period": "2026-10", "region": "example-region", "metric": "demand hypothesis",
    "unit": "statement", "status": "HYPOTHESIS", "origin_id": "synthetic-origin",
    "locator": "synthetic note only; no actual operating evidence"
  }],
  "claims": [{"id": "c1", "text": "Unverified demand hypothesis", "evidence_ids": ["e1"], "critical": true, "stance": "support"}],
  "scenarios": [
    {"name": "conservative", "currency": "CNY", "period": "2026-10/2026-10", "opening_cash": 0, "revenue": 100, "cost": 80, "capex": 10, "working_capital": 10, "reserve": 20},
    {"name": "base", "currency": "CNY", "period": "2026-10/2026-10", "opening_cash": 0, "revenue": 130, "cost": 80, "capex": 10, "working_capital": 10, "reserve": 20},
    {"name": "optimistic", "currency": "CNY", "period": "2026-10/2026-10", "opening_cash": 0, "revenue": 160, "cost": 80, "capex": 10, "working_capital": 10, "reserve": 20}
  ]
}
```

## 人工研究的扩展模型

本版没有强制验证以下字段，但真实报告仍须按适用性记录：业务决策/预算/最大损失/观察窗；证据收集者、方法、授权、样本和偏差；原件hash对应文件、公布/统计/适用/获取四种时间；行业与合并范围、币种、现价/不变价、季调、重述关系；政策有效/废止/资格/申报/拨付；主张引用的原话位置与反证；情景参数来源、税费/账期/退出/敏感性；来源获取失败；模型/工具版本和实际成本。这些是人工义务，不可宣称代码已经全部校验。

更新采用追加版本和失效引用标记，保留旧原件与旧判断。权限撤回、重述、政策改变或新反证影响结论时，进入补证/重算；不把后验信息写回旧预测。公开Skill只保存合成样本，实际材料和报告保存到获准私有目录。
