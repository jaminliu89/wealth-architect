# Wealth Architect · 财富与经营机会雷达

Agent Skills 标准包：联合官方统计、财报、政策、线上需求和授权线下经营证据，帮助判断已有生意与新机会。输出可追溯假设、反证、现金压力情景和有预算/停止条件的试验。

## 安装

```sh
npx skills add jaminliu89/wealth-architect
```

在独立测试项目内安装到 Codex：

```sh
npx skills add jaminliu89/wealth-architect --agent codex --yes --copy
```

支持本地目录安装；不需要 API key。安装本身不启动后台服务，不授予数据或交易权限。Skill 的实时研究依赖宿主可用且获准的浏览器/连接器。

## 使用

对安装后的 Agent 说：

> 用 Wealth Architect 判断我的现有生意还有哪些经营机会。结合当前地域、官方政策、财报和行业增速、线上需求与我授权的线下经营数据；列反证、现金流压力和下一步试验，未知项不要编造。

也可输入一个待判断机会、预算上限、截止日、地区、币种与授权资料。缺私有数据时输出证据缺口与补证计划。

入口：[SKILL.md](SKILL.md)。规划与架构见 [docs](docs/)，运行参考见 [references](references/)。

## 离线证据检查

Python 3.10+，仅标准库：

```sh
python3 scripts/radar.py validate dossier.json --as-of 2026-10-28
python3 -m unittest discover -s tests -v
```

JSON 合同见 [证据模型](references/evidence-model.md)。返回 0＝可交人工复核；2＝合法材料存在决策阻塞；1＝输入非法。检查范围包括日期、声明的来源独立性、关键结论覆盖、地域与现金底线。它不联网、不会认证来源或判断原文语义；快照摘要只是声明，未在此读取原文件校验。

本包没有自动采集、持久化数据库、行情订阅或模型执行器，不承诺收益，也不执行交易、购买数据、对外联络或生产部署。测试使用合成夹具，不是已验证经营机会。源代码测试、安装成功和 Skill 真实决策质量分开验收。

标准参考：[Agent Skills specification](https://agentskills.io/specification)；安装器：[vercel-labs/skills](https://github.com/vercel-labs/skills)。
