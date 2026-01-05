# Grafana 学习笔记

本目录主要整理 Grafana 的日常使用与查询语言相关内容（以 Prometheus 数据源的 PromQL 为主）。

## 文档索引

- `promql.md`：PromQL（Grafana + Prometheus 最常用查询语言）从概念、关键字到常用函数与实战示例
- `alert-rules.md`：Grafana Alert Rules（统一告警）配置全链路科普（查询/表达式/阈值/评估/路由/通知）
- `docker-compose.yaml`：本地实验环境一键启动（Grafana + Prometheus，自动接入数据源与示例仪表盘）
- `condistion.md`：Grafana 告警条件（Is above/Is below 等）速查与场景举例
- `parameter.md`：Grafana 告警通知（如飞书卡片）模板变量示例

## 推荐阅读顺序

1. 先理解怎么查数据：`promql.md`
2. 再理解怎么做告警：`alert-rules.md`
3. 最后查表与套模板：`condistion.md`、`parameter.md`

## 本地实验环境（Docker Compose）

在本目录执行：

```bash
docker compose -f docker-compose.yaml up -d
```

访问：

- Grafana：`http://localhost:10002`（用户名/密码：`admin` / `admin`）
- Prometheus：`http://localhost:9090`

说明：

- Prometheus 会抓取 Prometheus/Grafana 自身的 `/metrics`，用于练习 CPU/内存相关查询与告警。
- Grafana 会自动配置 Prometheus 数据源，并预置一个示例仪表盘：`Local Lab: Prometheus & Grafana CPU/Memory`。


• - 已新增一个本地 mock 指标服务：grafana/mock_llm_metrics_server.py:1（标准库实现 /metrics，会生成你整理的那些 llm_* 指标/labels/histogram）。
  - 便捷启动脚本：grafana/run-mock-metrics.sh:1（默认 stress，更容易触发告警阈值）。
  - Prometheus 已接入抓取目标：grafana/stack/prometheus/prometheus.yml:1（job=mock-llm → host.docker.internal:18080）。

  使用方法（你本地已 docker-compose 起服务的前提下）：

  - 终端1：bash grafana/run-mock-metrics.sh（或 python3 grafana/mock_llm_metrics_server.py --mode normal）
  - 终端2：docker compose -f grafana/docker-compose.yaml restart prometheus
  - 验证：打开 http://localhost:9090/targets 看 mock-llm 是否 UP，或在 Prometheus/Grafana 直接查 llm_request_count

  如果 mock-llm 抓取失败：把 grafana/stack/prometheus/prometheus.yml:1 里的 host.docker.internal 改成你的宿主机 IP 再重启 Prometheus。

## 告警批量化（文件化 Provisioning）

本目录已把 **Grafana Unified Alerting** 做成可拷贝的 provisioning 目录：`stack/grafana/provisioning/alerting/`，用于在新环境“一键复用”告警/路由/飞书模板。

- 飞书 webhook URL：用 `.env` 或环境变量提供 `FEISHU_WEBHOOK_URL`
- 说明：这些规则的 `provenance=file`（文件化管理），因此在 `Alerting` 页面是只读的；需要改 `metric.md`/生成文件并重启 Grafana 才会生效（或在 UI 里 Duplicate 一份变成可编辑规则）。
