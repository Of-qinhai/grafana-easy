# Grafana Alert Rules（统一告警）科普：配置思路、关键概念与实战模板

本文面向 **Grafana 的 Alert rules（Unified Alerting / 统一告警）** 使用场景：你不只是想“把阈值填进去”，而是要理解一条告警从 **查询 → 计算 → 判定 → 触发/恢复 → 路由 → 通知** 全链路发生了什么，以及为什么有时“面板上看着正常，告警却不按预期触发/恢复”。

> 说明：Grafana 不同版本 UI 文案会有差异，但核心模型一致。本文尽量用“概念 + 配置套路 + 示例”来覆盖版本差异。

相关文档：

- `grafana/promql.md`：Prometheus 数据源查询（PromQL）的关键字/函数（`sum`、`rate` 等）
- `grafana/condistion.md`：阈值条件（Is above/Is below 等）速查
- `grafana/parameter.md`：通知模板变量示例（偏通知侧）

---

## 1. 你现在用的是什么：Grafana Alert Rules 的位置与边界

Grafana Alert Rules（统一告警）通常具备这些特点：

- **在 Grafana 中创建与管理**：规则挂在某个 Folder/Group 下。
- **通过数据源查询拿数据**：常见是 Prometheus，也可能是 Loki、InfluxDB、CloudWatch 等。
- **可用 Grafana Expressions 做二次计算**：比如 Reduce/Math/Threshold/Resample。
- **用 Notification policies 做路由**：根据标签（labels）决定发给哪个 Contact point。
- **通知模板可定制**：可输出到飞书/钉钉/企业微信/Slack/Webhook 等。

它和 “Prometheus 自己的 alerting rules + Alertmanager” 的关系：

- Prometheus 规则：运行在 Prometheus 内部，语法是 PromQL，规则文件通常是 YAML；通知由 Alertmanager 负责。
- Grafana 规则：运行在 Grafana（或其告警引擎）中，查询可跨多数据源，路由/通知由 Grafana 的 Alerting 模块负责（也可以对接外部 Alertmanager）。

如果你主要使用 Grafana UI 的 “Alert rules” 配置界面，那么本文就是讲这一套。

---

## 2. 核心术语速通（理解这些后配置就不迷糊了）

### 2.1 Rule / Rule group / Folder

- **Alert rule（告警规则）**：一条告警的定义（查询、表达式、阈值、持续时间、标签、描述等）。
- **Rule group（规则组）**：把多条规则放在一起统一调度（通常共享 Evaluate interval）。
- **Folder（文件夹）**：规则的组织与权限边界（RBAC/团队隔离常用）。

### 2.2 Query（查询）与 Ref ID（A/B/C…）

在规则编辑器里，你会看到多个“Query / Expression”，每个都有一个 **Ref ID**（例如 `A`、`B`、`C`）。

一个典型流水线是：

1. `A`：数据源查询（Prometheus/Loki…）拿到一组时间序列
2. `B`：Reduce（把时间序列压成单值）
3. `C`：Threshold（把单值与阈值比较，生成告警判定）

### 2.3 Expression（表达式）是什么？为什么经常要 Reduce？

Grafana Alert Rules 里常见表达式类型：

- **Reduce**：把“时间序列”变成“单个值”（例如取 last/mean/max）
- **Math**：对多个查询/表达式做数学计算（例如 `错误率 = 5xx / total`）
- **Resample**：把不同 step 的序列对齐（跨数据源/跨查询更常用）
- **Threshold**：阈值判定（Is above/Is below/Is within range…）
- **Classic condition**：兼容旧式写法（“WHEN query(A) IS ABOVE 80”那种）

为什么经常要 Reduce？

- 告警最终要判断“现在是否超过阈值”，需要一个**可比较的数值**。
- 但查询（尤其是 range query）返回的是“随时间变化的一串点”。你必须定义“用哪种方式把这一串点代表为一个数”：
  - `last`：取最新值（适合看“当前是否超标”）
  - `mean`：取平均值（适合做平滑、减少抖动）
  - `max`：取最大值（适合抓峰值，但容易误报）
  - `min`：取最小值（适合保证底线，例如可用性/余量）

### 2.4 Condition（告警条件）与多维告警（Alert instances）

**Condition** 指“哪个表达式的结果决定告警状态”。通常你会把 Condition 指向最后一步（例如 Threshold `C`）。

重要：**一条规则可以产生多个告警实例（Alert instances）**。

- 如果你的查询结果按 `namespace/pod` 分组返回多条序列，那么每个标签组合可能各自变成一个告警实例。
- 这也是为什么你会遇到“一条规则突然炸出几百条告警”：往往是维度（labels）没有收敛。

### 2.5 Evaluate every / For / Keep firing for（高频但最容易误解）

这三个字段决定“什么时候触发、什么时候恢复、是否抖动”：

- **Evaluate every（评估间隔）**：Grafana 多久评估一次规则（例如每 1m）。
- **For（持续时间）**：条件成立后，需要连续成立多久才进入 Firing（例如持续 5m 才触发）。
- **Keep firing for（保持触发）**：条件恢复后，仍保持 Firing 状态一段时间（例如再保持 2m 才恢复）。

你可以把状态机想象成：

- 条件刚满足：进入 **Pending**
- 满足持续到 For：进入 **Firing**
- 条件不再满足：进入 **Normal/Resolved**
- 但如果配置了 Keep firing for：会在条件恢复后继续保持 Firing 一段时间，减少“抖动式恢复/再触发”

### 2.6 No data / Error（无数据与执行错误）

告警系统里，“没有数据”与“值为 0”是两回事：

- **值为 0**：说明数据存在，业务就是 0。
- **No data**：说明根本没有序列/没有点（采集断了、标签变了、过滤条件写错、权限不足…）。
- **Error**：查询失败或执行错误（超时、数据源不可达、表达式报错、除零产生 NaN…）。

Grafana 允许你分别配置：

- No data 状态该如何处理（例如当作 Alerting，或当作 OK，或保持上次状态）
- Error 状态该如何处理（例如当作 Alerting，或保持上次状态）

这对“监控链路断了要不要告警”非常关键。

### 2.7 Labels / Annotations：路由靠 Labels，信息靠 Annotations

- **Labels（标签）**：用于路由、分组、抑制（silence）、去重。建议放“稳定、不随时间乱变”的维度。
  - 典型：`severity`、`team`、`service`、`env`、`cluster`、`region`
- **Annotations（注解）**：用于描述告警内容（summary/description/runbook_url 等）。
  - 典型：`summary` 一句话；`description` 细节 + 排查思路；`runbook_url` 链接；`dashboard_url` 链接

---

## 3. 一条告警规则从 0 到 1：推荐的配置套路（Prometheus 数据源示例）

下面用最常见的“阈值告警”套路讲清楚每一步的目的。

### 3.1 第 0 步：先把“告警意图”说清楚

建议在动手前写下这 5 个问题的答案：

1. 你监控的对象是谁？（服务/接口/Pod/节点/队列…）
2. 你关心的指标是什么？（QPS/错误率/延迟/CPU/内存/磁盘…）
3. 阈值是什么？单位是什么？（5%、200ms、80%、10GB…）
4. 需要持续多久才算问题？（For：2m/5m/10m…）
5. 需要按什么维度触发？（按 service？按 namespace+pod？还是全局一条？）

这一步没想清楚，后面就容易出现：要么告警太泛、要么告警爆炸。

### 3.2 第 1 步：Query A（写出“可解释”的查询）

Prometheus 数据源建议优先把业务计算写在 PromQL 里（可迁移、可复用、也更容易在 Prometheus 侧做 recording rule）。

示例：全局 QPS（每秒）：

```promql
sum(rate(http_requests_total{job="api"}[5m]))
```

示例：按状态码分组的 QPS：

```promql
sum by (status) (rate(http_requests_total{job="api"}[5m]))
```

关于 `rate/sum` 等函数含义请看：`grafana/promql.md`

#### 关于 Query 的“时间范围”

Grafana Alert Rules 的查询通常会有“Relative time range / 查询时间范围”之类设置：

- 例如设置为最近 `10m`，意味着每次评估时都会取“过去 10 分钟”的数据来计算表达式。
- 如果你的 PromQL 已经内置窗口（如 `rate(x[5m])`），查询范围也不要小于这个窗口。

经验：评估间隔 1m 时，很多 `rate` 类告警会选择 `5m` 或 `10m` 的窗口来平滑。

### 3.3 第 2 步：Reduce B（把序列变成可比较的值）

Query A 很可能返回的是一条或多条时间序列。告警通常需要“现在的值是多少”：

- Reduce function 选 `last`：取最新值（最常用）
- 或选 `mean`：想抗抖、抗尖峰
- 或选 `max`：你想抓到任何峰值就告警（但容易误报）

常见模式：

- `B = last(A)`

### 3.4 第 3 步：Threshold C（定义阈值条件）

Threshold 基本就是“把数值映射为告警判定”：

- `Is above 80`
- `Is below 10`
- `Is within range 200 to 299`

常见模式：

- `C = B is above 80`

阈值条件中英文对照可参考：`grafana/condistion.md`

### 3.5 第 4 步：设置 Condition、评估与状态处理

**Condition** 指向 `C`（Threshold）后，再配置：

- Evaluate every：例如 `1m`
- For：例如 `5m`
- Keep firing for：例如 `2m`（可选，用于减少恢复抖动）
- No data / Error：按你的监控策略选择（后面有详细建议）

### 3.6 第 5 步：补齐 Labels（路由）与 Annotations（告警内容）

建议最少补齐这些 Labels：

- `severity`: `critical` / `warning` / `info`
- `team`: 团队名
- `service`: 服务名
- `env`: `prod` / `staging`

建议最少补齐这些 Annotations：

- `summary`：一句话概括（用于通知标题）
- `description`：细节（阈值、当前值、影响范围、排查建议）
- `runbook_url`：排查手册（可选但强烈建议）

很多团队“告警不落地”的原因就是：只有阈值没有 runbook，收到告警的人不知道下一步做什么。

### 3.7 第 6 步：确保 Notification policies 能路由到正确 Contact point

告警能不能发出去，往往不是规则写错，而是路由没匹配上：

- Notification policy matchers 是否能匹配到你这条规则的 labels（如 `team=xxx`、`severity=critical`）
- 是否被 Silence/Mute timing 抑制了
- Contact point 是否配置正确（Webhook URL、鉴权、消息模板）

---

## 4. Grafana Expressions 详解（怎么选、什么时候用）

下面把最常用的几类表达式讲透（这是 Grafana Alert Rules 和纯 PromQL 告警最大的差异点）。

### 4.1 Reduce：把时间序列“压成一个值”

**目的**：从“过去 N 分钟的一堆点”得到“一个代表值”。

典型选择建议：

- `last`：当前值是否超标（最常用）
- `mean`：均值是否超标（抗抖）
- `max`：窗口内只要出现过超标就认为异常（偏敏感）
- `min`：窗口内是否一直低于某条线（例如余量必须一直足够）

常见坑：

- 窗口太短 + last：非常容易抖动（尤其是 `irate`/尖峰指标）
- max：会把短暂尖峰也当作异常（适合“任何峰值都不可接受”的场景）

### 4.2 Threshold：把数值映射为“是否触发”

Threshold 就是把 Reduce/Math 的结果按条件转换成告警状态。

条件含义（更全的对照见 `grafana/condistion.md`）：

- Is above：大于
- Is below：小于
- Is equal to：等于
- Is within range：在区间内
- Is outside range：在区间外

### 4.3 Math：把多个查询结果组合起来（比纯 PromQL 更“拼装”）

适用场景：

- 你已经有两个结果：`错误数` 与 `总数`，想做 `错误率 = 错误数 / 总数`
- 你有两个数据源（比如云监控 + Prometheus），想做组合判断（此时 Resample 也可能需要）

对于 Prometheus 来说，很多数学组合在 PromQL 里也能直接写；选 Math 还是 PromQL 的建议：

- **能用 PromQL 清晰表达**：优先 PromQL（可移植、可在 Prometheus 侧做 recording rule）
- **跨数据源/需要 Grafana 统一表达式**：用 Math

Math 常见技巧：

- 把结果转换成百分比：`ratio * 100`
- 避免除零：在 PromQL 侧用 `clamp_min(x, 1)` 或在表达式里做 max 保护（具体取决于你的数据结构）

### 4.4 Resample：对齐步长（step）以便可计算

当你对两个序列做 Math，而它们的采样步长不一致时，可能需要 Resample。

典型场景：

- 一个序列来自 Prometheus（15s 抓取），另一个来自云监控（1m 粒度）
- 一个查询用较大窗口/step，另一个用较小 step

如果你只用单个 Prometheus 查询 + Reduce + Threshold，通常不需要 Resample。

### 4.5 Classic condition：旧式写法（知道即可）

Classic condition 往往把 “Reduce + Threshold” 合在一处写成一句：

- WHEN query(A) IS ABOVE 80

如果你已经习惯新版的 “Reduce/Threshold” 管道式写法，通常不需要 Classic condition。

---

## 5. No data / Error：怎么配才符合“监控策略”

不同团队对“监控链路自身故障”容忍度不同。下面给一套常用策略（你可以按团队偏好调整）。

### 5.1 No data（无数据）常见原因

- Exporter/采集端挂了
- Prometheus 抓取失败/权限问题
- 指标名变了（版本升级）
- 标签变了（例如 `pod` label 结构变化）
- 查询过滤条件写错（regex 不匹配）
- 数据真的不存在（比如某服务没部署）

### 5.2 No data 的处理建议（按场景）

| 场景 | No data 建议 | 理由 |
|---|---|---|
| 存活性（`up`）/关键链路 | 当作 Alerting 或单独告警 | 指标缺失本身就是严重问题 |
| 业务指标（可选、低优先级） | OK 或保持上次状态 | 避免缺失导致误报 |
| 每个实例都必须有指标（SLO/关键服务） | 当作 Alerting | “无数据”意味着不可观测 |

推荐做法：对关键服务单独加“缺失告警”，而不是把所有规则的 No data 都当作 Alerting，避免“监控雪崩时告警雪崩”。

### 5.3 Error（执行错误）常见原因

- 查询超时（范围太大、基数太高）
- 数据源不可达（网络/鉴权）
- 表达式错误（类型不匹配、除零、NaN）

Error 的处理建议：

- 关键规则：Error 当作 Alerting（因为“你已经失去对关键指标的判断能力”）
- 非关键规则：保持上次状态（减少误报）

同时要做工程治理：缩小时间范围、降基数、做 recording rule、提高 Prometheus 性能或做分片等。

---

## 6. 实战模板：常见告警怎么写（Prometheus + Grafana Alert Rules）

这一节给“能直接套用”的模板。每个模板都按同一结构说明：

- 目标
- Query（PromQL）
- Expressions（Reduce/Threshold/Math）
- 推荐 Evaluate/For/Keep firing for
- 推荐 Labels/Annotations

> 指标名因监控栈不同会有差异（cAdvisor/kube-state-metrics/node-exporter/业务埋点），你需要按实际指标替换。

### 6.1 模板：服务宕机（Up == 0）

**目标**：某服务实例不可达 2 分钟触发。

Query A：

```promql
up{job="api"} == 0
```

Expressions：

- B：Reduce `last(A)`（如果 A 已经是 0/1，也可以直接 last）
- C：Threshold `B is above 0`（或 `is equal to 1`，取决于你的表达式结果）

评估建议：

- Evaluate every：`1m`
- For：`2m`
- Keep firing for：`2m`（可选，避免短暂抖动恢复）
- No data：建议当作 Alerting（up 都没了更危险）

Labels 建议：

- `severity=critical`
- `team=...`
- `service=api`
- `env=prod`

Annotations 建议：

- `summary`: `{{ $labels.instance }} up == 0`
- `description`: `实例不可达，可能是进程退出、网络故障或采集失败。`
- `runbook_url`: `...`

> 关于 annotations 模板变量：Grafana 规则侧通常提供 `$labels`/`$values` 等变量，不同版本字段略有差异，建议在规则编辑器的预览（Preview）里确认可用结构后再固化模板。

### 6.2 模板：错误率过高（5xx / total）

**目标**：错误率（5xx）在 5 分钟窗口内持续超过 5%。

Query A（错误率，结果为 0~1）：

```promql
sum(rate(http_requests_total{job="api",status=~"5.."}[5m]))
/
sum(rate(http_requests_total{job="api"}[5m]))
```

Expressions：

- B：Reduce `last(A)`
- C：Math `$B * 100`（变成百分比，便于阈值与展示）
- D：Threshold `C is above 5`

评估建议：

- Evaluate every：`1m`
- For：`5m`
- Keep firing for：`2m`（可选）

常见坑：

- 分母可能为 0（低流量服务），会产生 NaN/Inf。可在 PromQL 侧做保护：对分母用 `clamp_min(…, 1)` 或先判断总量是否足够再告警。

### 6.3 模板：P95/P99 延迟过高（Histogram）

**目标**：P99 延迟超过 500ms 持续 10 分钟。

Query A（P99 延迟，单位秒）：

```promql
histogram_quantile(
  0.99,
  sum by (le) (rate(http_request_duration_seconds_bucket{job="api"}[5m]))
)
```

Expressions：

- B：Reduce `last(A)`
- C：Math `$B * 1000`（秒转毫秒）
- D：Threshold `C is above 500`

评估建议：

- Evaluate every：`1m`
- For：`10m`

### 6.4 模板：CPU 使用率过高（节点）

**目标**：节点 CPU 使用率超过 80% 持续 10 分钟。

Query A（0~1 的比例）：

```promql
1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))
```

Expressions：

- B：Reduce `last(A)`
- C：Math `$B * 100`
- D：Threshold `C is above 80`

### 6.5 模板：磁盘剩余空间不足（节点）

**目标**：磁盘剩余低于 10% 持续 15 分钟。

Query A（剩余百分比 0~100）：

```promql
100 * (
  node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} /
  node_filesystem_size_bytes{fstype!~"tmpfs|overlay"}
)
```

Expressions：

- B：Reduce `min(A)`（窗口内最小值更贴近“余量是否曾经不足”）
- C：Threshold `B is below 10`

评估建议：

- Evaluate every：`1m` 或 `5m`
- For：`15m`

### 6.6 模板：Pod CPU 使用过高（多维告警）

**目标**：每个 Pod 的 CPU 使用（核）超过 2 cores 持续 5 分钟，各 Pod 独立触发。

Query A：

```promql
sum by (namespace, pod) (
  rate(container_cpu_usage_seconds_total{container!="",pod!=""}[5m])
)
```

Expressions：

- B：Reduce `last(A)`（每个 pod 一条序列，last 后仍然是“每 pod 一个值”）
- C：Threshold `B is above 2`

要点：

- 这条规则会产生很多 alert instances：每个 `(namespace,pod)` 一条。
- 如果你只想要“整体告警一条”，需要在 PromQL 里把维度聚合掉：去掉 `by(namespace,pod)`。

### 6.7 模板：容器重启次数异常（Counter 增量）

**目标**：10 分钟内某容器重启次数 >= 3。

Query A：

```promql
increase(kube_pod_container_status_restarts_total[10m])
```

Expressions：

- B：Reduce `last(A)`
- C：Threshold `B is above or equal to 3`

提示：

- `increase` 输出的是“窗口内增加了多少次”，比直接看累计值更适合告警。

### 6.8 模板：业务自定义指标（以你的 MQ 写入速率为例）

你之前的示例类似：

```promql
sum(rate(llm_record_mq_write_duration_seconds_count[5m]))
```

可以按这种模式配置：

- Query A：`sum(rate(llm_record_mq_write_duration_seconds_count[5m]))`
- Reduce B：`last(A)`
- Threshold C：`B is above 47000`
- Evaluate every：`1m`
- For：`1m`（你原来写的 “Keep firing for 1m” 是另一回事，别混淆）
- Keep firing for：可选 `1m~5m`（看你是否需要减少抖动恢复）

单位说明：

- `rate(...[5m])` 是“每秒增长率”
- `sum(rate(...))` 把多个实例汇总为“总每秒速率”

---

## 7. Notification policies（通知策略）与 Contact points（联系点）：告警发给谁？

Grafana 的“路由”通常是：**按 labels 匹配策略 → 发送到 contact point**。

### 7.1 建议的标签体系（用于路由/分组）

强烈建议统一以下标签键（否则路由树很难维护）：

- `severity`: `critical|warning|info`
- `team`: `platform|sre|backend|...`
- `service`: 业务服务名（稳定）
- `env`: `prod|staging|test`
- `cluster`: 集群名（可选但很实用）

### 7.2 Notification policy 的关键配置项（常见）

- **Matchers**：匹配哪些 labels（例如 `severity=critical`）
- **Contact point**：发到哪里（Webhook/飞书/邮件…）
- **Group by**：用哪些 labels 把多个告警实例合并成一条通知
- **Group wait**：第一次触发后等待多久再发（避免瞬时抖动）
- **Group interval**：同一组告警多久再汇总发一次
- **Repeat interval**：同一条告警持续触发时多久重复提醒

经验建议（可按团队调整）：

- Group by：通常至少包含 `alertname`，再按需加 `service/env/cluster`；是否包含 `pod/instance` 取决于你想“一条消息里汇总多个实例”还是“每个实例一条消息”。
- Repeat interval：过短会吵，过长会漏；critical 常用 30m~2h，warning 常用 2h~6h。

### 7.3 Mute timings vs Silences（抑制的两种方式）

- **Mute timings**：按时间表静默（例如每天 00:00-08:00 不通知）
- **Silence**：临时静默（按 label matcher 静默某些告警一段时间）

运维场景：

- 发布窗口：用 Silence（只静默某服务/某集群）
- 夜间免打扰：用 Mute timings（但要谨慎，critical 通常不建议全局静默）

---

## 8. 通知内容怎么写：从规则 annotations 到消息模板

通知通常分两层：

1. **规则侧（Alert rule）**：你填的 Summary/Description 等（会变成 annotations）
2. **通知侧（Contact point / Notification template）**：决定最终消息长什么样

### 8.1 规则侧建议：把“可操作信息”写进 annotations

最少三件套：

- `summary`：一句话（对象 + 现象 + 阈值）
- `description`：补齐关键维度（当前值/窗口/持续时间/影响范围/排查路径）
- `runbook_url`：链接到 SOP（最好有）

例（思路示意）：

- summary：`api 错误率过高（>5%）`
- description：`当前={{...}}%，持续 5m；按 status 拆分...；优先检查...`

### 8.2 通知侧模板变量（Alertmanager 风格）

Grafana 的通知模板（尤其是 webhook/飞书/钉钉卡片）通常使用类似 Alertmanager 的数据结构：

- `.Status`
- `.CommonLabels.alertname`
- `.CommonAnnotations.summary`
- `.CommonAnnotations.description`
- `.Alerts`（列表，包含每个告警实例）
- `.ExternalURL`

你已有的模板变量示例可参考：`grafana/parameter.md`

---

## 9. 告警写得“稳定且有用”的经验清单

- **优先写清楚维度**：这条告警是按 service 触发，还是按 pod 触发？维度不清必炸。
- **Counter 一律先 rate/increase**：`*_total` 直接告警几乎都不对（见 `grafana/promql.md`）。
- **For 用来抗抖**：不是所有告警都需要 For，但没有 For 的告警往往会吵。
- **Keep firing for 用来抗恢复抖动**：适合波动指标（延迟、队列、短暂抖动）。
- **No data 单独治理**：关键指标缺失要告警，但别把所有规则 No data 都当 critical。
- **加 runbook_url**：告警要可执行，不然就是“消息噪音”。
- **必要时做 recording rules**：把昂贵的查询预聚合成新指标，提高稳定性与性能。

---

## 10. 排查指南：为什么“面板有数据但告警不触发/不恢复/不通知”？

按优先级排查：

1. **告警条件到底在看哪个表达式？**（Condition 指向错了很常见）
2. **Reduce 选了什么函数？**（last/mean/max 会导致完全不同结果）
3. **查询时间范围是否覆盖窗口？**（你用 `rate(...[5m])`，但查询范围只取 1m 就会不稳定）
4. **是否产生了多维实例？**（你以为一条，实际上 200 条，有的触发有的不触发）
5. **No data / Error 策略是否把状态“吞掉”了？**（比如保持上次状态导致看起来不恢复）
6. **路由是否命中？**（Notification policies matchers 不匹配 labels，就不会通知）
7. **是否被静默？**（Silence/Mute timings）
8. **联系点是否成功？**（Webhook 鉴权/返回码/超时）

建议做法：

- 在规则编辑器里用预览（Preview）观察每一步表达式的结果（A/B/C）
- 确认最终 Condition 的输出是否符合预期
- 再去看通知路由（policy）与 contact point 的发送记录

