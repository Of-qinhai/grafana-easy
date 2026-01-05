# Grafana + Prometheus：PromQL 教学文档（关键字 / 函数 / 实战）

很多人在 Grafana 里写 Prometheus 查询时会口误写成 “GraphQL/GraphQL 语法”，但实际最常用的是 **PromQL（Prometheus Query Language）**。本文以 Grafana + Prometheus 为主线，把 **PromQL 的关键字、数据类型、运算规则、常用函数（如 `sum`、`rate`）** 以及 Grafana 使用细节整理成一份可直接查阅的学习文档。

---

## 1. PromQL 解决什么问题？

PromQL 用来从 Prometheus 的时序数据库里取数并计算：

- **筛选**：按指标名与标签（labels）筛选时间序列。
- **聚合**：跨实例/容器/Pod 汇总（`sum by (...)` 等）。
- **计算速率/增量**：对 Counter 做 `rate`/`increase`，把“累计值”转换成“每秒速率/区间增量”。
- **拼接/对齐**：通过向量匹配（`on`/`ignoring`/`group_left`）把两类序列按标签做运算。
- **统计/降采样**：`*_over_time` 在一个时间窗口内做均值、最大值、分位数等。

---

## 2. PromQL 的 4 种数据类型（非常关键）

PromQL 的很多“报错/结果不对”，根源都是类型不匹配。PromQL 主要有：

1. **Instant Vector（瞬时向量）**：在“某个评估时刻”得到的一组时间序列（每条序列一个样本值）。
   - 例：`up{job="kubelet"}` 的结果是很多条序列，每条一个当前值（0/1）。
2. **Range Vector（区间向量）**：每条时间序列在一个时间窗口里的样本序列。
   - 例：`http_requests_total[5m]` 表示每条序列在过去 5 分钟的样本点集合。
3. **Scalar（标量）**：单个数字。
   - 例：`2`、`time()`（返回 Unix 时间戳秒）。
4. **String（字符串）**：很少见，主要用于少数函数的参数/返回。

常见规则：

- `rate()`、`increase()` 这类函数 **需要 Range Vector 输入**：`rate(metric_total[5m])`
- 聚合（`sum`/`avg`/`max` 等）通常作用于 **Instant Vector**（也可以对某些函数输出的 instant vector 聚合）
- `*_over_time` 这类函数 **需要 Range Vector 输入**：`avg_over_time(metric[10m])`

---

## 3. 选择器（Selector）与标签匹配

### 3.1 指标名 + 标签选择

最常见形式：

```promql
metric_name{label1="value1", label2="value2"}
```

例：

```promql
up{job="apiserver", instance="10.0.0.12:443"}
```

### 3.2 标签匹配符：`=` / `!=` / `=~` / `!~`

| 匹配符 | 含义 | 示例 |
|---|---|---|
| `=` | 等于 | `{job="kubelet"}` |
| `!=` | 不等于 | `{namespace!="kube-system"}` |
| `=~` | 正则匹配 | `{status=~"5..|429"}` |
| `!~` | 正则不匹配 | `{pod!~".*test.*"}` |

实战提示（Grafana 变量常用）：

- 单选变量可用 `=`：`{namespace="$namespace"}`
- 多选/All 变量通常要用 `=~`：`{pod=~"$pod"}`（Grafana 会把多选拼成正则）

---

## 4. 时间窗口与关键字：`[5m]`、`offset`、子查询、`@`

### 4.1 Range Selector：`[5m]`

把“瞬时选择器”变成“区间向量”：

```promql
http_requests_total{job="api"}[5m]
```

### 4.2 `offset`：把查询整体向过去平移

对比“今天”和“昨天同一时刻”很常用：

```promql
sum(rate(http_requests_total[$__rate_interval]))
/
sum(rate(http_requests_total[$__rate_interval] offset 1d))
```

注意：`offset` 是把**取样时间窗**平移，而不是简单把结果延迟。

### 4.3 子查询（Subquery）：`[1h:5m]`

子查询常用于：先得到一条序列的“即时结果”，再对这个结果在一个更大窗口内做二次计算。

语法：

```promql
(expr)[1h:5m]
```

含义：

- 外层窗口：`1h`
- 子查询步长：`5m`（每 5 分钟对 `expr` 评估一次，得到一个 range vector）

例：先算 QPS，再取 1 小时最大值：

```promql
max_over_time(
  (sum(rate(http_requests_total[$__rate_interval])))[1h:1m]
)
```

### 4.4 `@`：在指定时间点求值（了解即可）

PromQL 支持在特定时间点求值（依赖 Prometheus 版本）：

```promql
up{job="api"} @ 1700000000
```

在 Grafana 面板里通常不需要用 `@`，更多用于调试或回放。

---

## 5. 运算符：算术 / 比较 / 集合（逻辑）

### 5.1 算术运算符：`+ - * / % ^`

支持：

- 向量 ⊕ 标量：`rate(x[5m]) * 60`
- 向量 ⊕ 向量：会进行“向量匹配”（见后面 `on/ignoring`）

### 5.2 比较运算符：`== != > < >= <=`

默认行为：**过滤（filter）**。只有条件为真的序列会保留。

```promql
up == 0
```

`bool` 关键字：让比较结果变成 0/1（不再过滤掉序列），用于把条件当作数值参与后续计算。

```promql
up == bool 0
```

### 5.3 集合运算符：`and` / `or` / `unless`

它们按“标签集合”做集合运算（常用来做兜底、补 0、排除）：

- `or`：左边没数据时用右边补上（常见：`... or vector(0)`）
- `and`：只保留两边都存在的序列
- `unless`：从左边剔除右边存在的序列

例：没有数据时显示 0（避免 Grafana 面板空白）：

```promql
sum(rate(http_requests_total[$__rate_interval])) or vector(0)
```

---

## 6. 聚合关键字（常说的“sum/avg/max...”）

在 PromQL 里，`sum`/`avg`/`max` 等属于 **聚合操作符（aggregation operators）**，经常被口语称为“内置函数”。

### 6.1 最常用：`sum` / `avg` / `min` / `max` / `count`

```promql
sum(instant_vector)
avg(instant_vector)
max(instant_vector)
count(instant_vector)
```

默认会把所有标签维度都聚合掉（只剩下一条序列），所以通常要配合 `by()` 或 `without()`。

### 6.2 `by (...)` 与 `without (...)`（高频关键字）

- `by (a,b)`：聚合后**保留**这些标签维度（按它们分组）
- `without (a,b)`：聚合后**丢弃**这些标签（保留其它标签分组）

例：按 `namespace` 汇总 Pod 的 CPU 使用率（每秒核数）：

```promql
sum by (namespace) (
  rate(container_cpu_usage_seconds_total{container!="",pod!=""}[$__rate_interval])
)
```

例：汇总全局 QPS，但不关心 `instance`：

```promql
sum without (instance) (
  rate(http_requests_total[$__rate_interval])
)
```

### 6.3 TopK/BottomK/Quantile 等（常用统计）

| 操作符 | 作用 | 示例 |
|---|---|---|
| `topk(k, v)` | 取值最大的 k 条序列 | `topk(5, rate(http_requests_total[5m]))` |
| `bottomk(k, v)` | 取值最小的 k 条序列 | `bottomk(5, node_memory_MemAvailable_bytes)` |
| `quantile(φ, v)` | 计算 instant vector 的分位数（按“序列集合”分位，不是按时间） | `quantile(0.99, rate(...))` |
| `count_values("label", v)` | 统计值分布并把“值”写入指定 label | `count_values("code", http_response_code)` |
| `group(v)` | 把值变成 1，仅用于保留标签集合 | `group(up)` |

提示：`quantile()` 经常被误用在延迟上；延迟如果来自 Prometheus Histogram，应该优先用 `histogram_quantile()`（见后文）。

---

## 7. 向量匹配关键字：`on` / `ignoring` / `group_left` / `group_right`

当你写 `A / B` 且 A、B 都是向量时，PromQL 需要根据标签把两边序列“对齐”。默认匹配规则是：**除 `__name__` 外，标签集合完全一致** 才能匹配。

### 7.1 `on(labels...)`：只按这些标签做匹配

例：按 `instance` 对齐 CPU 使用与 CPU 核数：

```promql
rate(node_cpu_seconds_total{mode!="idle"}[5m])
/
on(instance)
count by (instance) (node_cpu_seconds_total{mode="idle"})
```

### 7.2 `ignoring(labels...)`：忽略这些标签，其它标签必须一致

例：忽略 `cpu` 维度，把每核 CPU 时间汇总：

```promql
sum by (instance, mode) (
  rate(node_cpu_seconds_total[5m])
)
```

（这个例子更常见是用 `sum by(...)` 直接聚合掉 `cpu` 标签，而不是二元运算里写 `ignoring(cpu)`。）

### 7.3 `group_left` / `group_right`：允许一对多 / 多对一

当一边存在多个匹配序列（例如：Pod 指标想关联 Namespace 的额外标签），需要 group 修饰。

例：把 `kube_pod_labels` 的业务标签“带到”CPU 指标上（示例写法，具体指标取决于你的监控栈）：

```promql
sum by (namespace, pod, label_app) (
  rate(container_cpu_usage_seconds_total{container!="",pod!=""}[$__rate_interval])
  * on (namespace, pod) group_left(label_app)
  kube_pod_labels{label_app!=""}
)
```

要点：

- `on(namespace, pod)`：按 Pod 主键对齐
- `group_left(label_app)`：允许右边比左边“多标签”，并把 `label_app` 从右侧带到结果中

---

## 8. 常用函数与“什么时候用”（重点：`sum`、`rate`、`increase`）

PromQL 函数很多，但 80% 的场景集中在少数几类。下面按使用频率整理，并把关键点写清楚。

### 8.1 Counter 与 Gauge：先分清指标类型

很多函数对指标类型有前提：

- **Counter（计数器）**：只增不减，重启会归零（例如 `*_total`、`*_count`、`*_sum` 多是 counter）
  - 典型用法：`rate()` / `increase()`
- **Gauge（仪表盘）**：可增可减（例如内存使用、队列长度、温度）
  - 典型用法：直接用当前值、或 `avg_over_time()`/`max_over_time()`、或 `delta()`（看场景）

### 8.2 `rate(v range-vector)`：把 Counter 转成“每秒增长率”（QPS/吞吐）

**输入**：Range Vector（必须带 `[5m]` 这类窗口）  
**输出**：Instant Vector（每条序列变成一个“每秒”的值）  
**适用**：Counter（如 `http_requests_total`）

典型写法：

```promql
rate(http_requests_total[$__rate_interval])
```

配合 `sum` 计算全局 QPS：

```promql
sum(rate(http_requests_total[$__rate_interval]))
```

配合 `by()` 做分组（推荐）：

```promql
sum by (job, status) (
  rate(http_requests_total[$__rate_interval])
)
```

实战注意点：

- `rate()` 的窗口不能太小；通常建议 **至少覆盖 4 个抓取周期**。Grafana 提供 `$__rate_interval` 就是为了解决“窗口过小导致速率不准/噪声大”的问题。
- 看到 `*_total`，默认优先考虑 `rate()` 或 `increase()`，而不是直接画 `*_total`（累计曲线很难读）。

### 8.3 `irate(v range-vector)`：更灵敏的“瞬时速率”（只看最后两个点）

适合看尖峰（spike），不适合作为稳定告警指标：

```promql
irate(http_requests_total[2m])
```

经验：

- 图表想“平滑稳定”用 `rate`
- 想抓尖峰、瞬时抖动用 `irate`

### 8.4 `increase(v range-vector)`：区间内总增量（Counter 在窗口内增加了多少）

**输出单位**：与 Counter 本身一致（例如请求数、字节数），不是“每秒”

例：过去 1 小时总请求数：

```promql
sum(increase(http_requests_total[1h]))
```

和 `rate` 的关系（直觉理解）：

- `increase(x[1h]) ≈ rate(x[1h]) * 3600`

### 8.5 `delta(v range-vector)` / `idelta(v range-vector)`：窗口内差值（常用于 Gauge）

- `delta`：窗口内首尾差值（对 gauge 更直观）
- `idelta`：只看最后两个点的差值

例：队列深度 10 分钟内变化量：

```promql
delta(queue_depth[10m])
```

### 8.6 `*_over_time`：在时间窗口内做统计（输入 Range Vector）

| 函数 | 作用 | 示例 |
|---|---|---|
| `avg_over_time(v[5m])` | 5 分钟均值 | `avg_over_time(node_load1[10m])` |
| `max_over_time(v[5m])` | 5 分钟最大值 | `max_over_time(container_memory_working_set_bytes[30m])` |
| `min_over_time(v[5m])` | 5 分钟最小值 | `min_over_time(up[15m])` |
| `sum_over_time(v[5m])` | 5 分钟求和（注意：对 gauge 是“样本求和”，不是业务含义的累计） | `sum_over_time(temp_celsius[1h])` |
| `count_over_time(v[5m])` | 样本点数量 | `count_over_time(up[5m])` |
| `quantile_over_time(0.95, v[5m])` | 窗口内分位数（按时间维度） | `quantile_over_time(0.99, latency_seconds[10m])` |
| `stddev_over_time(v[5m])` | 标准差 | `stddev_over_time(cpu_usage[15m])` |

常见误区：

- `sum_over_time` 不是 “increase”；对 counter 的增量请用 `increase()`，对 counter 的速率请用 `rate()`。

### 8.7 `histogram_quantile(φ, buckets)`：Histogram 延迟分位数（P95/P99）

Prometheus Histogram 会生成三类指标：

- `xxx_bucket{le="0.1"}`：各桶累积计数（Counter）
- `xxx_sum`：总和（Counter）
- `xxx_count`：总次数（Counter）

用 `histogram_quantile` 计算延迟分位（最常用写法）：

```promql
histogram_quantile(
  0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket[$__rate_interval]))
)
```

分组到服务维度：

```promql
histogram_quantile(
  0.99,
  sum by (job, le) (
    rate(http_request_duration_seconds_bucket{job="api"}[$__rate_interval])
  )
)
```

注意点：

- `sum by (le)`（或 `sum by (job, le)`）是必须的，否则桶不会按正确维度聚合。
- `le` 是桶上界标签；`histogram_quantile` 需要它来重建分布。

### 8.8 `absent()` / `absent_over_time()`：检测“指标缺失”

告警经常需要区分：

- 值为 0（业务为 0）
- 没有数据（采集断了、实例挂了、label 变了）

`absent(up{job="api"})` 在没有任何匹配序列时返回 1（否则无结果），可用于“缺失告警”：

```promql
absent(up{job="api"})
```

### 8.9 标签处理函数：`label_replace` / `label_join`（高级但实用）

用正则从某个 label 提取字段写到新 label：

```promql
label_replace(
  up,
  "node",
  "$1",
  "instance",
  "(.*):.*"
)
```

把多个 label 拼成一个 label（用于 legend 展示）：

```promql
label_join(up, "target", "/", "job", "instance")
```

---

## 9. Grafana 里写 PromQL：宏变量与面板分辨率

Grafana 面板对 Prometheus 是“范围查询（query_range）”，会带一个 `step`（分辨率）。如果 `step` 很小、或者窗口写死，就容易出现：

- 查询很慢
- 图很抖
- `rate()` 窗口太小导致速率不准

### 9.1 Grafana 常用宏变量（Prometheus 数据源）

| 变量 | 含义 | 常用位置 |
|---|---|---|
| `$__interval` | Grafana 根据时间范围与图宽计算的建议 step | `avg_over_time(x[$__interval])`、子查询步长等 |
| `$__rate_interval` | 给 `rate/increase` 用的建议窗口（通常 >= 多个抓取周期） | `rate(x[$__rate_interval])` |
| `$__range` | 当前 dashboard 的时间范围（如 `6h`） | `increase(x[$__range])` |
| `$__range_s` | 时间范围（秒） | 需要数值时 |
| `$__range_ms` | 时间范围（毫秒） | 需要数值时 |

推荐习惯：

- `rate()`/`increase()`：优先用 `$__rate_interval`
- 其它窗口统计：根据业务选择固定窗口（如 5m/10m）或 `$__interval`

### 9.2 `step`（分辨率）与 `[window]`（窗口）不是一回事

- `step`：Prometheus 在一个时间范围内“每隔多久算一个点”（Grafana 控制）
- `[window]`：`rate()` 这类函数回看历史的窗口

经验值：

- `step` 小会让图更细，但会更慢
- `rate()` 的窗口通常要大于 `step`，否则会出现锯齿/噪声

### 9.3 Grafana 模板变量（Templating）与 Prometheus 常用写法

Grafana 的“Dashboard 变量”常用于做下拉选择（集群/命名空间/服务/实例/Pod），再把变量带入 PromQL 的 label matcher。

#### 9.3.1 变量查询（Prometheus 数据源）

下面是 Grafana Prometheus 变量里最常见的几种写法（不同 Grafana 版本 UI 名称可能略有差异）：

```promql
# 取某个 label 的所有取值
label_values(up, job)

# 带筛选条件再取 label 值（最常用）
label_values(kube_pod_info{namespace="$namespace"}, pod)

# 取所有 label 名称（用于排查）
label_names()

# 取 metric 名称（按正则过滤）
metrics(kube_.*)

# 把 PromQL 结果作为变量值（需要配合 Grafana 的正则提取/格式化）
query_result(topk(5, sum(rate(http_requests_total[$__rate_interval])) by (job)))
```

#### 9.3.2 在 PromQL 里引用变量：`=` vs `=~`

经验法则：

- **单选**：`{namespace="$namespace"}`
- **多选/All**：`{pod=~"$pod"}`（Grafana 多选变量通常会变成正则表达式）

如果你启用了变量的 **Include All**，建议把 **All value** 设为 `.*`，然后在 PromQL 里统一使用 `=~"$var"`，可以减少“单选 OK、多选无结果”的问题。

### 9.4 Grafana Legend（图例）常用写法

Prometheus 查询返回多条序列时，建议用 legend 把关键标签拼出来，便于阅读：

- `{{namespace}}/{{pod}}`
- `{{job}} - {{instance}}`

（写法取决于 Grafana 面板类型与版本，一般在 Legend/Display name 里配置。）

### 9.5 Grafana 调试：Query Inspector（查询检查器）

排查“结果不对/太慢”时，优先打开 Grafana 的 Query inspector：

- 看最终发给 Prometheus 的 query、`start/end/step`
- 确认 `$__interval`、`$__rate_interval` 展开后的真实值
- 确认是不是因为 step 太小、返回点太多导致慢

### 9.6 Grafana 告警里写 PromQL（稳定性优先）

面板的目标是“可视化”，告警的目标是“稳定可靠”。同一条 PromQL 在告警里经常需要做一些取舍：

- **窗口选择**：告警评估间隔如果是 1m，`rate()` 常用窗口建议 `5m` 或 `10m`（更平滑），避免 `irate()` 造成抖动误报。
- **维度控制**：告警如果不想按 Pod/instance 炸开，记得用 `sum by (...)` 收敛维度；反之想做“多维度告警”，就保留关键标签（例如 `namespace,pod`），让每个标签组合各自触发。
- **无数据处理**：用 `absent()` 做“指标缺失告警”；用 `... or vector(0)` 做“展示兜底”（两者目的不同）。

Grafana 告警条件（Is above/Is below 等）与通知模板变量示例可参考：

- `grafana/condistion.md`
- `grafana/parameter.md`

---

## 10. PromQL 实战模板（可直接复制改标签）

下面示例假设常见的命名习惯（不同监控栈指标名可能略有差异）。

### 10.1 服务是否存活：`up`

```promql
up{job="api"}
```

只看挂了的：

```promql
up{job="api"} == 0
```

### 10.2 QPS（每秒请求数）

```promql
sum(rate(http_requests_total{job="api"}[$__rate_interval]))
```

按状态码拆分：

```promql
sum by (status) (rate(http_requests_total{job="api"}[$__rate_interval]))
```

### 10.3 错误率（5xx / 总量）

```promql
sum(rate(http_requests_total{job="api",status=~"5.."}[$__rate_interval]))
/
sum(rate(http_requests_total{job="api"}[$__rate_interval]))
```

### 10.4 平均延迟（Histogram：sum/count）

```promql
sum(rate(http_request_duration_seconds_sum{job="api"}[$__rate_interval]))
/
sum(rate(http_request_duration_seconds_count{job="api"}[$__rate_interval]))
```

### 10.5 P95/P99 延迟（Histogram：bucket + histogram_quantile）

```promql
histogram_quantile(
  0.95,
  sum by (le) (
    rate(http_request_duration_seconds_bucket{job="api"}[$__rate_interval])
  )
)
```

### 10.6 Kubernetes：Pod CPU 使用率（核）

```promql
sum by (namespace, pod) (
  rate(container_cpu_usage_seconds_total{container!="",pod!=""}[$__rate_interval])
)
```

### 10.7 Kubernetes：Pod 内存（工作集）

```promql
sum by (namespace, pod) (
  container_memory_working_set_bytes{container!="",pod!=""}
)
```

### 10.8 节点 CPU 使用率（非 idle 的比例）

```promql
1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))
```

### 10.9 Top N：最耗 CPU 的 Pod

```promql
topk(
  10,
  sum by (namespace, pod) (
    rate(container_cpu_usage_seconds_total{container!="",pod!=""}[$__rate_interval])
  )
)
```

---

## 11. 常见坑与排查清单

### 11.1 `rate()` 用在 Gauge 上

症状：图形怪异、数值没意义。  
处理：确认是不是 counter（一般以 `_total`/`_count` 结尾），counter 才用 `rate/increase`。

### 11.2 `sum(rate(...))` 没写 `by()`，导致“维度丢失”

症状：所有实例汇总成一条线，看不到按服务/Pod 拆分。  
处理：按你关心的维度写 `by()`。

### 11.3 Grafana 变量多选没用 `=~`

症状：单选正常，多选/All 无结果。  
处理：多选变量通常用 `label=~"$var"`，并在 Grafana 变量里设置合适的 All 值（一般是 `.*`）。

### 11.4 没有数据 vs 值为 0

症状：面板断线、告警误判。  
处理：用 `absent()` 做缺失检测；用 `or vector(0)` 兜底显示。

### 11.5 查询太慢

排查方向：

- 缩小时间范围、提高 `Min interval`
- 减少高基数 label（如 `path`、`request_id`）
- 优先在 Prometheus 用 recording rules 预聚合（把常用 `sum(rate(...))` 变成新指标）

---

## 12. 关键字速查表（你提到的“关键字之类的”）

| 关键字 | 类别 | 用途一句话 |
|---|---|---|
| `by` | 聚合分组 | 聚合后保留哪些标签维度 |
| `without` | 聚合分组 | 聚合后丢弃哪些标签维度 |
| `on` | 向量匹配 | 二元运算只按指定标签对齐 |
| `ignoring` | 向量匹配 | 二元运算忽略指定标签对齐 |
| `group_left` | 向量匹配 | 允许右侧一对多，并可携带右侧额外标签 |
| `group_right` | 向量匹配 | 允许左侧一对多（较少用） |
| `bool` | 比较修饰 | 比较结果返回 0/1 而不是过滤 |
| `offset` | 时间修饰 | 把查询窗口整体平移到过去 |
| `and/or/unless` | 集合运算 | 以标签集合做交/并/差运算 |

---

## 13. 建议的学习路径（如何用这份文档）

1. 先把第 2 章（数据类型）和第 6 章（`sum by/without`）吃透  
2. 接着掌握第 8 章（`rate`/`increase`/`*_over_time`/`histogram_quantile`）  
3. 最后再看第 7 章（向量匹配）解决复杂拼接问题  

如果你愿意把你们的 Prometheus 里“最常用的指标名”（例如入口网关、业务服务、Kafka/MQ、数据库）发我几条，我可以按你们的真实指标把第 10 章的模板进一步补齐成“公司可直接套用版”。
