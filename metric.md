# Grafana 指标监控清单（按截图整理）

> 数据源：Prometheus（PromQL）。以下内容按“逐个指标”整理：含义 + 建议面板查询 + 建议告警表达式。
>
> 说明（务必对照你们实际 labels/指标类型校验一次）：
>
> - 文中默认可能存在的 labels：`service`、`channel`、`status_code`、`token_bucket`、`instance`（若你们实际键名不同请替换）。
> - Counter 建议用 `rate(...[5m])`/`increase(...[1h])`；Gauge 直接取值（常配合 `max/sum` 聚合）。
> - 分位数写法分两类：
>   - Histogram：使用 `*_bucket` + `histogram_quantile()`（推荐，Prometheus 原生）。
>   - Summary：使用 `metric{quantile="0.xx"}`（若你们暴露的是 Summary）。

## Gateway（生产者）侧（Prometheus-Business / Gateway）

### llm_record_mq_write_error_count（Redis Stream 写入失败总数）

- 含义：Redis Stream 写入失败累计次数；生产侧无法把事件写入 MQ，可能导致数据丢失。
- 面板（错误速率，errors/s）：`sum(rate(llm_record_mq_write_error_count[5m]))`
- 告警（高优先级，立即告警）：`sum(rate(llm_record_mq_write_error_count[5m])) > 0.01`
- 可选（错误比例≈1%，假设每次写入都会记录 duration 的 count）：`sum(rate(llm_record_mq_write_error_count[5m])) / sum(rate(llm_record_mq_write_duration_seconds_count[5m])) > 0.01`

### llm_record_temp_store_write_error_count（临时存储写入失败总数）

- 含义：降级/缓存（临时存储）写入失败累计次数；通常意味着降级链路也不可用。
- 面板（错误速率，errors/s）：`sum(rate(llm_record_temp_store_write_error_count[5m]))`
- 告警（高优先级，立即告警）：`sum(rate(llm_record_temp_store_write_error_count[5m])) > 0.01`

### llm_record_mq_write_waiting（内存中等待写入 MQ 的请求数）

- 含义：Gateway 内部缓冲区积压（等待写入 MQ 的请求数）；持续升高说明写入速率跟不上生产速率。
- 面板（积压深度，取最大实例）：`max(llm_record_mq_write_waiting)`
- 告警（中优先级）：`max(llm_record_mq_write_waiting) > 100`
- 可选（全局总积压，按实例求和）：`sum(llm_record_mq_write_waiting)`

### llm_record_mq_write_duration_seconds（写入 MQ 耗时分布）

- 含义：写入 MQ（Redis Stream）的耗时分布；反映 Redis/网络/下游响应性能。
- 面板（P99，Histogram）：`histogram_quantile(0.99, sum by (le) (rate(llm_record_mq_write_duration_seconds_bucket[5m])))`
- 告警（中优先级，性能退化预警）：`histogram_quantile(0.99, sum by (le) (rate(llm_record_mq_write_duration_seconds_bucket[5m]))) > 1`
- 面板（平均耗时，秒）：`sum(rate(llm_record_mq_write_duration_seconds_sum[5m])) / sum(rate(llm_record_mq_write_duration_seconds_count[5m]))`
- 若你们暴露的是 Summary（非 Histogram）：`llm_record_mq_write_duration_seconds{quantile="0.99"} > 1`

### llm_record_mq_write_retry_count（写入重试次数）

- 含义：写入 MQ 的重试累计次数；通常由网络抖动、Redis 短暂不可用导致。
- 面板（重试速率，retries/s）：`sum(rate(llm_record_mq_write_retry_count[5m]))`
- 告警（预警关注，无需深夜电话）：`sum(rate(llm_record_mq_write_retry_count[5m])) > 0.1`
- 可选（每次写入平均重试次数，依赖 duration_count）：`sum(rate(llm_record_mq_write_retry_count[5m])) / sum(rate(llm_record_mq_write_duration_seconds_count[5m]))`

## 流量与可用性（Traffic & Availability）

### QPS / 请求速率（llm_request_count, channel_llm_request_count）

- 含义：系统吞吐（每秒请求数），可用于观察流量波动/路由倾斜。
- 面板（全局 QPS）：`sum(rate(llm_request_count[1m]))`
- 面板（按 Service）：`sum by (service) (rate(llm_request_count[1m]))`
- 面板（按 Service + Channel）：`sum by (service, channel) (rate(channel_llm_request_count[1m]))`
- 面板（按状态码）：`sum by (service, status_code) (rate(llm_request_count[1m]))`
- 备注：Dashboard 中可把 `[1m]` 换成 `[$__rate_interval]`，更适配不同时间范围。

### 错误率 / 成功率（基于 status_code）

- 含义：基于 HTTP 状态码计算错误比例；用于 P1 可用性告警与 Channel 级质量分布分析。
- 面板（全局 5xx 错误率）：`sum(rate(llm_request_count{status_code=~"5.."}[5m])) / sum(rate(llm_request_count[5m]))`
- 告警（P1：全局 5xx 错误率 > 5%）：`sum(rate(llm_request_count{status_code=~"5.."}[5m])) / sum(rate(llm_request_count[5m])) > 0.05`
- 面板（按 Service 5xx 错误率）：`sum by (service) (rate(llm_request_count{status_code=~"5.."}[5m])) / sum by (service) (rate(llm_request_count[5m]))`
- 面板（按 Service + Channel 5xx 错误率）：`sum by (service, channel) (rate(channel_llm_request_count{status_code=~"5.."}[5m])) / sum by (service, channel) (rate(channel_llm_request_count[5m]))`
- 告警（P2：Channel 级 5xx 错误率 > 5%）：`sum by (service, channel) (rate(channel_llm_request_count{status_code=~"5.."}[5m])) / sum by (service, channel) (rate(channel_llm_request_count[5m])) > 0.05`
- 可选（全局成功率 2xx）：`sum(rate(llm_request_count{status_code=~"2.."}[5m])) / sum(rate(llm_request_count[5m]))`

### 请求分布特征（*_request_count_by_token_bucket，label: token_bucket）

- 含义：请求按 Token 长度分桶（短文本 vs 长文本）；长文本占比升高常伴随延迟/超时上升。
- 面板（Service 级分桶 QPS）：`sum by (service, token_bucket) (rate(llm_request_count_by_token_bucket[5m]))`
- 面板（Service + Channel 分桶 QPS）：`sum by (service, channel, token_bucket) (rate(channel_llm_request_count_by_token_bucket[5m]))`
- 可选（分桶占比）：`sum by (service, token_bucket) (rate(llm_request_count_by_token_bucket[5m])) / sum by (service) (rate(llm_request_count_by_token_bucket[5m]))`
- 如果你不确定具体指标名（按名称正则匹配，谨慎使用）：`sum by (service, channel, token_bucket, __name__) (rate({__name__=~".*_request_count_by_token_bucket"}[5m]))`

## 性能与体验（Performance / UX）

### 端到端延迟（End-to-End Latency：llm_request_duration）

- 含义：整次请求从开始到结束的总耗时。
- 面板（P95，Histogram）：`histogram_quantile(0.95, sum by (le) (rate(llm_request_duration_bucket[5m])))`
- 面板（P99，Histogram）：`histogram_quantile(0.99, sum by (le) (rate(llm_request_duration_bucket[5m])))`
- 面板（平均耗时，秒）：`sum(rate(llm_request_duration_sum[5m])) / sum(rate(llm_request_duration_count[5m]))`
- 告警（示例：P95 > 60s，按你们 SLA 调整）：`histogram_quantile(0.95, sum by (le) (rate(llm_request_duration_bucket[5m]))) > 60`
- 若需按 Service/Channel 维度：`histogram_quantile(0.95, sum by (service, channel, le) (rate(llm_request_duration_bucket[5m])))`

### 首字延迟 TTFT（Time To First Token：llm_ttft）

- 含义：用户看到第一个输出 token 的时间，直接影响“流畅感”（关键体验指标）。
- 面板（Heatmap，Histogram）：`sum by (le) (rate(llm_ttft_bucket[5m]))`
- 面板（P90，Histogram）：`histogram_quantile(0.90, sum by (le) (rate(llm_ttft_bucket[5m])))`
- 告警（示例：P90 > 2s，流式场景）：`histogram_quantile(0.90, sum by (le) (rate(llm_ttft_bucket[5m]))) > 2`
- 若你们暴露的是 Summary：`llm_ttft{quantile="0.90"} > 2`

### 生成速度 OTPS（Output Tokens Per Second：llm_otps）

- 含义：输出 token 的生成速度（tokens/s）；数值越低，用户越觉得“卡顿”。
- 面板（P50，Histogram）：`histogram_quantile(0.50, sum by (le) (rate(llm_otps_bucket[5m])))`
- 面板（P90，Histogram）：`histogram_quantile(0.90, sum by (le) (rate(llm_otps_bucket[5m])))`
- 若你们暴露的是 Summary：`llm_otps{quantile="0.50"}`、`llm_otps{quantile="0.90"}`

### 单 Token 耗时 TPOT（Time Per Output Token：llm_tpot）

- 含义：生成每个输出 token 的平均耗时（秒/token），通常近似为 OTPS 的倒数。
- 面板（P50，Histogram）：`histogram_quantile(0.50, sum by (le) (rate(llm_tpot_bucket[5m])))`
- 面板（P90，Histogram）：`histogram_quantile(0.90, sum by (le) (rate(llm_tpot_bucket[5m])))`
- 面板（平均耗时，秒/token）：`sum(rate(llm_tpot_sum[5m])) / sum(rate(llm_tpot_count[5m]))`
- 若你们暴露的是 Summary：`llm_tpot{quantile="0.90"}`

## 成本与用量（Cost & Usage）

### Token 消耗速率（llm_total_tokens / llm_input_tokens / llm_output_tokens）

- 含义：每秒 token 消耗量（输入/输出/总），用于实时监控成本与异常突增。
- 面板（Input tokens/s）：`sum(rate(llm_input_tokens[1m]))`
- 面板（Output tokens/s）：`sum(rate(llm_output_tokens[1m]))`
- 面板（Total tokens/s）：`sum(rate(llm_total_tokens[1m]))`
- 若需按 Service/Channel 维度：`sum by (service, channel) (rate(llm_total_tokens[1m]))`

### 累计 Token 用量（同上）

- 含义：某时间窗口内累计消耗 token（更贴近计费/配额/对账）。
- 面板（过去 1h 总量）：`sum(increase(llm_total_tokens[1h]))`
- 面板（Dashboard 时间范围总量）：`sum(increase(llm_total_tokens[$__range]))`
- Input/Output 同理：`sum(increase(llm_input_tokens[$__range]))`、`sum(increase(llm_output_tokens[$__range]))`

### Token 长度分布（*_total_tokens_by_token_bucket，label: token_bucket）

- 含义：token 消耗主要集中在哪些长度区间；用于优化上下文窗口、路由到不同成本模型。
- 面板（按 bucket 的 token/s）：`sum by (token_bucket) (rate(llm_total_tokens_by_token_bucket[5m]))`
- 面板（按 bucket 的窗口累计，适合饼图/占比）：`sum by (token_bucket) (increase(llm_total_tokens_by_token_bucket[$__range]))`
- 如果你不确定具体指标名（按名称正则匹配，谨慎使用）：`sum by (service, channel, token_bucket, __name__) (increase({__name__=~".*_total_tokens_by_token_bucket"}[$__range]))`

## 系统饱和度（Saturation）

### 并发处理数（In-flight requests：llm_chat_handler_active_count）

- 含义：当前正在处理中的请求数量；用于判断是否需要扩容/限流。
- 面板（全局并发）：`sum(llm_chat_handler_active_count)`
- 面板（按 Service）：`sum by (service) (llm_chat_handler_active_count)`
- 告警（接近 Max Concurrency 阈值时报警，示例 90%）：`sum(llm_chat_handler_active_count) > <max_concurrency> * 0.9`
