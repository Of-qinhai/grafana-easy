# Grafana 手动配置完全指南

本指南将手把手教你如何在 Grafana 中手动配置监控系统，包括数据源、告警规则、通知渠道等所有核心功能。

---

## 目录

1. [环境准备](#1-环境准备)
2. [手动配置数据源 (Data Sources)](#2-手动配置数据源-data-sources)
3. [手动配置告警规则 (Alert Rules)](#3-手动配置告警规则-alert-rules)
4. [手动配置联系点 (Contact Points)](#4-手动配置联系点-contact-points)
5. [手动配置通知策略 (Notification Policies)](#5-手动配置通知策略-notification-policies)
6. [手动配置通知模板 (Notification Templates)](#6-手动配置通知模板-notification-templates)
7. [手动配置 Dashboard](#7-手动配置-dashboard)
8. [验证配置](#8-验证配置)
9. [常见问题与技巧](#9-常见问题与技巧)

---

## 1. 环境准备

### 1.1 启动基础环境

使用简化版的 docker-compose 启动 Grafana 和 Prometheus：

```bash
cd /Users/haiqin/k8s入门到精通/learning/grafana
docker-compose -f docker-compose-simple.yaml up -d
```

### 1.2 启动 Mock 数据生成器

为了产生测试指标数据，运行 mock 数据生成脚本：

```bash
# 使用 stress 模式，快速触发告警阈值
./run-mock-metrics.sh stress

# 或使用 normal 模式，产生正常流量
./run-mock-metrics.sh normal
```

### 1.3 访问 Grafana

- **URL**: http://localhost:10002
- **用户名**: admin
- **密码**: admin123（在 docker-compose-simple.yaml 中配置）

首次登录后，Grafana 可能会提示修改密码，可以选择跳过。

### 1.4 验证 Prometheus 数据

- **Prometheus URL**: http://localhost:9090
- 访问该地址,在查询框中输入任意指标（如 `up`）验证 Prometheus 正常运行

---

## 2. 手动配置数据源 (Data Sources)

数据源是 Grafana 获取监控数据的来源。我们需要添加 Prometheus 作为数据源。

### 2.1 打开数据源配置页面

1. 登录 Grafana (http://localhost:10002)
2. 点击左侧菜单栏的 **齿轮图标**  (Configuration)
3. 选择 **Data sources**
4. 点击右上角 **Add data source** 按钮

### 2.2 选择 Prometheus

1. 在数据源列表中找到 **Prometheus**
2. 点击 **Prometheus**

### 2.3 配置 Prometheus 数据源

填写以下配置：

| 字段 | 值 | 说明 |
|------|-----|------|
| **Name** | `Prometheus` | 数据源名称，后续告警规则会引用 |
| **Default** |  勾选 | 设为默认数据源 |
| **URL** | `http://prometheus:9090` | Prometheus 地址（Docker 内部网络） |
| **Access** | `Server (default)` | 通过 Grafana 后端访问 |

**重要配置项说明**：

```yaml
# 如果在 provisioning 文件中，对应配置如下：
name: Prometheus
uid: prometheus          # 唯一标识符，告警规则会用到
type: prometheus
access: proxy           # 等同于 "Server" 访问模式
url: http://prometheus:9090
isDefault: true
editable: false
```

### 2.4 高级配置（可选）

向下滚动找到 **Additional settings**，可以配置：

- **Scrape interval**: `15s` (Prometheus 抓取间隔)
- **Query timeout**: `60s` (查询超时时间)
- **HTTP Method**: `POST` (推荐用于复杂查询)

### 2.5 保存并测试

1. 滚动到页面底部
2. 点击 **Save & test** 按钮
3. 如果配置正确，会显示绿色提示：**Data source is working**

### 2.6 验证数据源

1. 点击左侧菜单 **Explore** (探索图标 )
2. 在查询框中输入 PromQL：`up`
3. 点击 **Run query** 按钮
4. 如果能看到数据，说明数据源配置成功

**测试查询示例**：
```promql
# 查看所有监控目标状态
up

# 查看 LLM 指标（如果 mock 数据生成器在运行）
llm_request_count

# 查看错误率
sum(rate(llm_record_mq_write_error_count[5m]))
```

---

## 3. 手动配置联系点 (Contact Points)

联系点定义了告警通知发送到哪里。Grafana 支持多种通知渠道：邮件、Webhook、Slack、钉钉、飞书等。

### 3.1 打开联系点配置页面

1. 点击左侧菜单 **警报图标**  (Alerting)
2. 在子菜单中选择 **Contact points**
3. 点击右上角 **Add contact point** 按钮

---

### 3.2 配置飞书 Webhook 联系点

#### 步骤 1: 创建飞书 Webhook（外部准备）

在配置 Grafana 之前，你需要在飞书中创建一个自定义机器人 Webhook：

1. 在飞书群组中，点击 **群设置** → **群机器人** → **添加机器人**
2. 选择 **自定义机器人**
3. 复制生成的 Webhook URL（格式类似：`https://open.feishu.cn/open-apis/bot/v2/hook/xxx`）

#### 步骤 2: 在 Grafana 中配置

在 **Add contact point** 页面填写：

| 字段 | 值 | 说明 |
|------|-----|------|
| **Name** | `feishu-webhook` | 联系点名称 |
| **Integration** | `Webhook` | 选择 Webhook 类型 |

展开 **Optional Webhook settings**：

| 字段 | 值 | 说明 |
|------|-----|------|
| **URL** | `你的飞书 Webhook URL` | 例如：`https://open.feishu.cn/open-apis/bot/v2/hook/xxx` |
| **HTTP Method** | `POST` | 使用 POST 请求 |
| **Max alerts** | `0` | 0 表示不限制告警数量 |

#### 步骤 3: 配置消息模板（高级）

如果需要自定义飞书卡片格式，可以在 **Body** 部分填写：

```json
{{ template "feishu_card" . }}
```

> **注意**：这里引用了自定义模板 `feishu_card`，稍后我们会在 **通知模板** 章节中创建它。

#### 步骤 4: 测试并保存

1. 点击 **Test** 按钮，发送测试通知到飞书群
2. 如果飞书群收到消息，说明配置成功
3. 点击 **Save contact point** 保存

---

### 3.3 配置邮件联系点

#### 前置条件：配置 SMTP

邮件通知需要先在 Grafana 中配置 SMTP 服务器。修改 `docker-compose-simple.yaml`，添加环境变量：

```yaml
environment:
  # ... 其他配置 ...
  GF_SMTP_ENABLED: "true"
  GF_SMTP_HOST: "smtp.qq.com:587"
  GF_SMTP_USER: "your-email@qq.com"
  GF_SMTP_PASSWORD: "your-qq-auth-code"  # QQ 邮箱授权码
  GF_SMTP_FROM_ADDRESS: "your-email@qq.com"
  GF_SMTP_FROM_NAME: "Grafana 告警通知"
```

重启容器使配置生效：
```bash
docker-compose -f docker-compose-simple.yaml down
docker-compose -f docker-compose-simple.yaml up -d
```

#### 创建邮件联系点

1. 在 **Contact points** 页面，点击 **Add contact point**
2. 填写配置：

| 字段 | 值 | 说明 |
|------|-----|------|
| **Name** | `email` | 联系点名称 |
| **Integration** | `Email` | 选择邮件类型 |
| **Addresses** | `user1@example.com,user2@example.com` | 收件人邮箱（多个用逗号分隔） |
| **Single email** | 不勾选 | 每个收件人单独收到邮件 |

#### 自定义邮件主题和内容（可选）

展开 **Optional Email settings**：

| 字段 | 值 |
|------|-----|
| **Subject** | `{{ template "__email_subject" . }}` |
| **Message** | `{{ template "__email_alert_text" . }}` |

3. 点击 **Test** 测试邮件发送
4. 点击 **Save contact point** 保存

---

### 3.4 查看 provisioning 文件对比

**手动配置 vs provisioning 配置**：

```yaml
# stack/grafana/provisioning/alerting/contact-points.yaml
apiVersion: 1

contactPoints:
  - orgId: 1
    name: feishu-webhook
    receivers:
      - uid: feishu-webhook
        type: webhook
        settings:
          url: ${FEISHU_WEBHOOK_URL}     # 环境变量引用
          httpMethod: POST
          maxAlerts: 0
          payload:
            template: '{{ template "feishu_card" . }}'
        disableResolveMessage: false

  - orgId: 1
    name: email
    receivers:
      - uid: email
        type: email
        settings:
          addresses: ${ALERT_EMAIL_ADDRESSES}
          singleEmail: false
          subject: '{{ template "__email_subject" . }}'
          message: '{{ template "__email_alert_text" . }}'
        disableResolveMessage: false
```

---

## 4. 手动配置通知模板 (Notification Templates)

通知模板用于自定义告警消息的格式。Grafana 使用 Go 模板语法。

### 4.1 打开通知模板配置页面

1. 点击左侧菜单 **警报图标**  (Alerting)
2. 选择 **Notification templates**
3. 点击 **Add notification template** 按钮

### 4.2 创建飞书卡片模板

#### 基础配置

| 字段 | 值 |
|------|-----|
| **Name** | `feishu_card` |

#### 模板内容

在 **Content** 区域粘贴以下 JSON 模板（简化版本）：

```json
{
  "msg_type": "interactive",
  "card": {
    "schema": "2.0",
    "header": {
      "title": {
        "tag": "plain_text",
        "content": {{ if .CommonAnnotations.customTitle }}{{ printf "%q" .CommonAnnotations.customTitle }}{{ else }}{{ printf "%q" .GroupLabels.alertname }}{{ end }}
      },
      "template": {{ if eq .Status "firing" }}{{ if eq .CommonLabels.severity "critical" }}{{ printf "%q" "red" }}{{ else }}{{ printf "%q" "orange" }}{{ end }}{{ else }}{{ printf "%q" "green" }}{{ end }}
    },
    "body": {
      "elements": [
        {
          "tag": "markdown",
          "content": {{ printf "%q" (printf "**告警描述**\n%s" .CommonAnnotations.description) }}
        },
        {
          "tag": "markdown",
          "content": {{ printf "%q" (printf "**建议操作**\n%s" .CommonAnnotations.summary) }}
        }
      ]
    }
  }
}
```

> **提示**：完整模板请参考 `stack/grafana/provisioning/alerting/notification-templates.yaml` 文件。

#### 保存模板

1. 点击 **Save template** 按钮
2. 模板将出现在模板列表中

### 4.3 创建邮件主题模板

#### 创建 `__email_subject` 模板

| 字段 | 值 |
|------|-----|
| **Name** | `__email_subject` |

**Content**:
```go
{{- if eq .Status "firing" -}}
  {{- if eq .CommonLabels.severity "critical" -}}[紧急告警]{{- else -}}[告警通知]{{- end -}}
{{- else -}}[告警已恢复]{{- end -}}
{{- if .CommonAnnotations.customTitle }} {{ .CommonAnnotations.customTitle }}{{- else }} {{ .GroupLabels.alertname }}{{- end -}}
```

### 4.4 创建邮件内容模板

#### 创建 `__email_alert_text` 模板

| 字段 | 值 |
|------|-----|
| **Name** | `__email_alert_text` |

**Content**（简化版 HTML）:
```html
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background-color: {{ if eq .Status "firing" }}#ff4d4f{{ else }}#52c41a{{ end }}; color: white; padding: 20px;">
    <h2>{{ if .CommonAnnotations.customTitle }}{{ .CommonAnnotations.customTitle }}{{ else }}{{ .GroupLabels.alertname }}{{ end }}</h2>
  </div>

  <div style="padding: 20px; background-color: #f5f5f5;">
    <p><strong>告警级别：</strong>{{ .CommonLabels.severity }}</p>
    <p><strong>触发时间：</strong>{{ if gt (len .Alerts) 0 }}{{ with index .Alerts 0 }}{{ .StartsAt.Format "2006-01-02 15:04:05" }}{{ end }}{{ end }}</p>

    <div style="margin-top: 20px;">
      <h3>告警描述</h3>
      <p>{{ .CommonAnnotations.description }}</p>
    </div>

    <div style="margin-top: 20px;">
      <h3>建议操作</h3>
      <p>{{ .CommonAnnotations.summary }}</p>
    </div>
  </div>
</div>
```

> **提示**：完整 HTML 邮件模板请参考 `stack/grafana/provisioning/alerting/notification-templates.yaml` 第 215-305 行。

#### 保存模板

点击 **Save template** 保存。

### 4.5 模板语法说明

**常用变量**：

| 变量 | 说明 | 示例 |
|------|------|------|
| `.Status` | 告警状态 | `firing` 或 `resolved` |
| `.CommonLabels` | 所有告警共享的标签 | `.CommonLabels.severity` |
| `.CommonAnnotations` | 所有告警共享的注解 | `.CommonAnnotations.description` |
| `.GroupLabels` | 分组标签 | `.GroupLabels.alertname` |
| `.Alerts` | 告警列表 | `{{ range .Alerts }}...{{ end }}` |
| `.ExternalURL` | Grafana 访问 URL | `http://localhost:10002` |

**条件判断示例**：
```go
{{ if eq .Status "firing" }}
  告警中
{{ else }}
  已恢复
{{ end }}
```

**格式化输出**：
```go
{{ printf "%q" .CommonAnnotations.summary }}  // 输出带引号的字符串
{{ printf "%.2f" $value }}                     // 保留两位小数
```

---

## 5. 手动配置通知策略 (Notification Policies)

通知策略决定哪些告警发送到哪个联系点，以及如何分组、聚合告警。

### 5.1 打开通知策略配置页面

1. 点击左侧菜单 **警报图标**  (Alerting)
2. 选择 **Notification policies**
3. 你会看到一个默认的 **Root policy**（根策略）

### 5.2 编辑根策略（Default contact point）

1. 点击根策略右侧的 **Edit** 按钮
2. 配置默认联系点：

| 字段 | 值 | 说明 |
|------|-----|------|
| **Default contact point** | `email` | 默认使用邮件通知 |
| **Group by** | `grafana_folder`, `alertname` | 按文件夹和告警名称分组 |
| **Group wait** | `10s` | 等待10秒再发送首次告警 |
| **Group interval** | `1m` | 同一组告警的发送间隔 |
| **Repeat interval** | `5m` | 重复告警的发送间隔 |

3. 点击 **Update default policy** 保存

### 5.3 添加子策略（路由飞书通知）

为带有 `notify=feishu` 标签的告警添加特定路由：

1. 在根策略下，点击 **+ New specific policy** 按钮
2. 填写配置：

| 字段 | 值 | 说明 |
|------|-----|------|
| **Matching labels** | `notify = feishu` | 匹配条件：标签 notify 等于 feishu |
| **Contact point** | `feishu-webhook` | 使用飞书 Webhook |
| **Continue matching** | 不勾选 | 匹配后停止继续匹配 |

3. 点击 **Save policy** 保存

### 5.4 再添加一个邮件策略（可选）

如果希望同时发送邮件和飞书通知：

1. 添加第二个子策略
2. 配置：

| 字段 | 值 |
|------|-----|
| **Matching labels** | `notify = feishu` |
| **Contact point** | `email` |
| **Continue matching** | 不勾选 |

3. 保存策略

### 5.5 策略层级结构

最终的策略结构如下：

```
Root Policy (默认: email)
├── 子策略 1: notify=feishu → feishu-webhook
└── 子策略 2: notify=feishu → email
```

### 5.6 查看 provisioning 文件对比

```yaml
# stack/grafana/provisioning/alerting/notification-policies.yaml
apiVersion: 1

policies:
  - orgId: 1
    receiver: email                    # 默认联系点
    group_by:
      - grafana_folder
      - alertname
    group_wait: 10s
    group_interval: 1m
    repeat_interval: 5m
    routes:                            # 子策略
      - receiver: feishu-webhook
        object_matchers:
          - ["notify", "=", "feishu"]
        continue: false
      - receiver: email
        object_matchers:
          - ["notify", "=", "feishu"]
        continue: false
```

### 5.7 策略配置参数说明

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| **Group by** | 告警分组依据，相同标签的告警会聚合 | `grafana_folder`, `alertname` |
| **Group wait** | 发送首次告警前的等待时间，用于聚合 | `10s` - `30s` |
| **Group interval** | 同一组新告警的发送间隔 | `1m` - `5m` |
| **Repeat interval** | 未恢复告警的重复通知间隔 | `4h` - `12h` |
| **Continue matching** | 是否继续匹配后续策略 | 一般为 `false` |

---

## 6. 手动配置告警规则 (Alert Rules)

告警规则是监控系统的核心，定义了何时触发告警。

### 6.1 创建告警文件夹

首先创建一个文件夹来组织告警规则：

1. 点击左侧菜单 **警报图标**  (Alerting)
2. 选择 **Alert rules**
3. 点击 **+ New folder** 按钮
4. 输入文件夹名称：`LLM`
5. 点击 **Create** 创建

### 6.2 创建第一个告警规则

#### 示例：MQ 写入错误告警

1. 在 **Alert rules** 页面，点击 **+ New alert rule** 按钮
2. 填写规则名称和文件夹：

| 字段 | 值 |
|------|-----|
| **Rule name** | `llm_record_mq_write_error_count` |
| **Folder** | `LLM` |

#### Step 1: 定义查询条件

在 **Section 1: Set alert rule** 下：

**Query A** (数据查询):

| 字段 | 值 |
|------|-----|
| **Data source** | `Prometheus` |
| **Query** | `sum(rate(llm_record_mq_write_error_count[5m]))` |
| **Legend** | (留空) |
| **Instant** |  勾选 |

点击 **Run queries** 验证查询是否返回数据。

**Expression B** (条件判断):

点击 **+ Expression** 按钮添加表达式：

| 字段 | 值 |
|------|-----|
| **Operation** | `Classic condition` |
| **Input** | `A` |
| **Reducer** | `last` (取最后一个值) |
| **Comparison** | `IS ABOVE` (大于) |
| **Threshold** | `0.01` |

#### Step 2: 设置触发条件

在 **Section 2: Set evaluation behavior** 下：

| 字段 | 值 | 说明 |
|------|-----|------|
| **Folder** | `LLM` | 告警所在文件夹 |
| **Evaluation group** | `llm-metrics` (新建) | 评估组名称 |
| **Evaluation interval** | `1m` | 每分钟评估一次 |
| **Pending period** | `1m` | 持续1分钟后才告警（for 语句） |

#### Step 3: 配置告警标签和注解

在 **Section 3: Add annotations and labels** 下：

**Labels** (标签，用于路由):

| Key | Value |
|-----|-------|
| `severity` | `critical` |
| `notify` | `feishu` |

**Annotations** (注解，用于描述):

| Key | Value |
|-----|-------|
| `summary` | `Redis Stream 写入失败，可能导致数据丢失` |
| `description` | `Redis Stream 写入失败累计次数；生产侧无法把事件写入 MQ，可能导致数据丢失。` |
| `customTitle` | `Redis Stream 写入失败` |
| `unit` | `次/秒` |
| `threshold` | `> 0.01` |
| `metricName` | `llm_record_mq_write_error_count` |

#### Step 4: 配置通知设置

在 **Section 4: Notifications** 下：

| 字段 | 值 |
|------|-----|
| **Contact point** | (使用策略自动路由) |
| **Mute timings** | (不设置) |

#### Step 5: 保存告警规则

1. 点击页面底部 **Save rule and exit** 按钮
2. 规则将出现在 `LLM` 文件夹下

### 6.3 查看 provisioning 文件对比

以下是同一条告警规则的 YAML 配置（来自 `alert-rules.yaml`）：

```yaml
apiVersion: 1

groups:
  - orgId: 1
    name: llm-metrics                # Evaluation group 名称
    folder: LLM                      # 文件夹名称
    interval: 1m                     # 评估间隔
    rules:
      - uid: llm-b94e7d988323        # 唯一标识符（自动生成）
        title: "llm_record_mq_write_error_count"
        condition: B                 # 使用 Expression B 作为触发条件
        data:
          - refId: A                 # Query A
            datasourceUid: prometheus
            relativeTimeRange:
              from: 600
              to: 0
            model:
              expr: "sum(rate(llm_record_mq_write_error_count[5m]))"
              instant: true
              refId: A
          - refId: B                 # Expression B
            datasourceUid: __expr__
            model:
              type: classic_conditions
              expression: A
              conditions:
                - evaluator:
                    type: gt
                    params:
                      - 0.01
                  reducer:
                    type: last
                  type: query
        noDataState: OK              # 无数据时状态
        execErrState: Error          # 执行错误时状态
        for: 1m                      # Pending period
        annotations:
          summary: "Redis Stream 写入失败，可能导致数据丢失"
          description: "..."
          customTitle: "Redis Stream 写入失败"
          unit: "次/秒"
          threshold: "> 0.01"
          metricName: "llm_record_mq_write_error_count"
        labels:
          severity: critical
          notify: feishu
        isPaused: false              # 是否暂停
```

### 6.4 快速创建更多告警规则

现在你已经掌握了创建告警的流程，可以参考 `stack/grafana/provisioning/alerting/alert-rules.yaml` 文件中的其他规则配置，手动创建以下告警：

1. **llm_record_temp_store_write_error_count** - 临时存储写入失败
2. **llm_record_mq_write_waiting** - MQ 写入队列积压
3. **llm_request_5xx_error_rate_high** - 全局 5xx 错误率
4. **llm_ttft** - 首字延迟过高

每个告警的 PromQL、阈值、标签等配置都可以在 `alert-rules.yaml` 文件中找到。

### 6.5 告警规则常用配置说明

| 配置项 | 说明 | 推荐值 |
|--------|------|--------|
| **Evaluation interval** | 多久评估一次告警条件 | `1m` - `5m` |
| **Pending period (for)** | 条件持续多久才触发告警 | `1m` - `5m` |
| **No data state** | 无数据时的状态 | `OK` 或 `NoData` |
| **Error state** | 查询错误时的状态 | `Error` 或 `Alerting` |

---

## 7. 手动配置 Dashboard

Dashboard 用于可视化监控数据，可以手动创建或导入现有的 Dashboard JSON 文件。

### 7.1 方法一：导入现有 Dashboard

如果你有现成的 Dashboard JSON 文件（如 `stack/grafana/dashboards/local-lab.json`）：

1. 点击左侧菜单 **+** (Create) 或 **Dashboards**
2. 点击 **Import dashboard** 按钮
3. 两种导入方式：
   - **方式 A**: 点击 **Upload JSON file**，选择 `local-lab.json` 文件
   - **方式 B**: 复制 JSON 内容，粘贴到 **Import via panel json** 文本框
4. 配置 Dashboard 选项：

| 字段 | 值 |
|------|-----|
| **Name** | `Local Lab Dashboard` (可自定义) |
| **Folder** | `Local Lab` (新建文件夹) |
| **Unique identifier (UID)** | (自动生成) |
| **Prometheus** | `Prometheus` (选择数据源) |

5. 点击 **Import** 完成导入

### 7.2 方法二：手动创建 Dashboard

#### 创建新 Dashboard

1. 点击左侧菜单 **+** (Create)
2. 选择 **Dashboard**
3. 点击 **Add visualization** 添加第一个面板

#### 创建面板示例：错误率监控

1. 选择数据源：`Prometheus`
2. 在查询框中输入 PromQL：

```promql
sum(rate(llm_record_mq_write_error_count[5m]))
```

3. 配置面板设置：

**Panel options**:
- **Title**: `MQ 写入错误率`
- **Description**: `Redis Stream 写入失败的速率`

**Graph styles**:
- **Style**: `Lines`
- **Line width**: `1`
- **Fill opacity**: `10`

**Standard options**:
- **Unit**: `ops` (operations per second)
- **Decimals**: `4`

4. 点击右上角 **Apply** 保存面板

#### 添加更多面板

重复上述步骤，创建其他监控面板：

- **并发处理数**: `sum(llm_chat_handler_active_count)`
- **P95 延迟**: `histogram_quantile(0.95, sum by (le) (rate(llm_request_duration_bucket[5m])))`
- **5xx 错误率**: `sum(rate(llm_request_count{status_code=~"5.."}[5m])) / sum(rate(llm_request_count[5m])) * 100`

#### 保存 Dashboard

1. 点击右上角 **Save dashboard** (软盘图标)
2. 填写信息：

| 字段 | 值 |
|------|-----|
| **Dashboard name** | `LLM Metrics Dashboard` |
| **Folder** | `LLM` |

3. 点击 **Save** 保存

### 7.3 配置 Dashboard 变量（可选）

变量可以让 Dashboard 支持动态筛选。

1. 在 Dashboard 页面，点击右上角 ** Settings**
2. 选择 **Variables** 标签
3. 点击 **Add variable** 按钮

#### 示例：创建 Channel 筛选变量

| 字段 | 值 |
|------|-----|
| **Name** | `channel` |
| **Type** | `Query` |
| **Data source** | `Prometheus` |
| **Query** | `label_values(channel_llm_request_count, channel)` |
| **Multi-value** |  勾选 |
| **Include All option** |  勾选 |

4. 点击 **Apply** 保存变量

现在可以在查询中使用 `$channel` 变量：

```promql
sum(rate(channel_llm_request_count{channel=~"$channel"}[5m]))
```

### 7.4 查看 provisioning 文件对比

如果使用文件 provisioning，需要创建配置文件：

```yaml
# stack/grafana/provisioning/dashboards/dashboards.yml
apiVersion: 1

providers:
  - name: LocalLab
    orgId: 1
    folder: Local Lab
    type: file
    disableDeletion: true
    editable: true
    options:
      path: /var/lib/grafana/dashboards  # Dashboard JSON 文件路径
```

---

## 8. 验证配置

完成所有配置后，需要验证整个告警流程是否正常工作。

### 8.1 检查数据源连接

1. 进入 **Configuration** → **Data sources**
2. 点击 **Prometheus** 数据源
3. 点击 **Save & test**
4. 确认显示绿色提示：**Data source is working**

### 8.2 验证告警规则

#### 查看告警状态

1. 进入 **Alerting** → **Alert rules**
2. 在 `LLM` 文件夹下查看所有告警规则
3. 检查状态列：
   -  **Normal**: 未触发
   -  **Pending**: 条件满足，等待 `for` 时长
   -  **Firing**: 正在告警

#### 手动触发测试告警

如果使用 `stress` 模式运行 mock 数据生成器，告警应该会自动触发。

验证步骤：
```bash
# 确认 mock 数据生成器正在运行
ps aux | grep mock_llm_metrics_server

# 查看 Prometheus 指标
curl http://localhost:9090/api/v1/query?query=sum\(rate\(llm_record_mq_write_error_count\[5m\]\)\)
```

### 8.3 验证通知发送

#### 测试联系点

1. 进入 **Alerting** → **Contact points**
2. 找到 `feishu-webhook` 或 `email` 联系点
3. 点击右侧 **Test** 按钮
4. 点击 **Send test notification**
5. 检查：
   - 飞书群是否收到测试消息
   - 邮箱是否收到测试邮件

#### 查看告警历史

1. 进入 **Alerting** → **Alert rules**
2. 点击某个告警规则，查看详情
3. 切换到 **History** 标签，查看触发历史
4. 切换到 **State history** 标签，查看状态变更时间线

### 8.4 验证通知策略路由

当告警触发时，验证消息是否正确路由：

1. 检查带有 `notify=feishu` 标签的告警是否发送到飞书
2. 检查默认告警是否发送到邮箱
3. 查看 **Alerting** → **Notification policies**，确认策略配置正确

---

## 9. 常见问题与技巧

### 9.1 常见问题排查

#### Q1: 数据源连接失败

**症状**：保存数据源时显示 "HTTP Error Bad Gateway"

**解决方案**：
- 检查 Prometheus 容器是否运行：`docker ps | grep prometheus`
- 检查 URL 是否正确：在 Docker 内部网络应使用 `http://prometheus:9090`
- 检查网络连接：`docker exec -it learning-grafana ping prometheus`

#### Q2: 告警规则不触发

**症状**：告警规则始终显示 Normal 状态

**排查步骤**：
1. 在 **Explore** 中手动运行 PromQL，确认有数据返回
2. 检查告警条件阈值是否合理
3. 查看 **Pending period (for)**，可能需要等待更长时间
4. 检查 **Evaluation interval** 是否设置正确

#### Q3: 未收到告警通知

**症状**：告警已触发（Firing），但未收到通知

**排查步骤**：
1. 检查联系点配置：进入 **Contact points**，点击 **Test** 发送测试通知
2. 检查通知策略：确认告警标签与策略匹配规则一致
3. 查看告警详情页的 **Notification** 标签，检查发送状态
4. 邮件通知：检查 SMTP 配置是否正确，查看 Grafana 日志：
   ```bash
   docker logs learning-grafana | grep -i smtp
   ```

#### Q4: 飞书 Webhook 返回错误

**症状**：测试飞书通知时显示 "Invalid JSON"

**解决方案**：
- 检查通知模板 JSON 格式是否正确
- 使用在线 JSON 验证工具验证模板
- 参考飞书官方文档：https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN

#### Q5: Dashboard 显示 "No data"

**症状**：Dashboard 面板显示无数据

**解决方案**：
1. 确认 mock 数据生成器正在运行
2. 在 **Explore** 中测试相同的 PromQL 查询
3. 检查时间范围选择器（右上角），确保在数据范围内
4. 检查 Dashboard 变量过滤是否过于严格

### 9.2 实用技巧

#### 技巧 1: 批量导出配置

手动配置完成后，可以导出配置为 YAML，方便迁移：

**导出告警规则**：
1. 进入 **Alerting** → **Alert rules**
2. 点击告警规则右侧的 **...** (More)
3. 选择 **Export**
4. 复制 YAML 内容保存到文件

**导出 Dashboard**：
1. 打开 Dashboard，点击右上角 ** Settings**
2. 选择 **JSON Model**
3. 复制 JSON 内容保存到文件

#### 技巧 2: 使用 Grafana API

可以通过 API 进行配置管理：

```bash
# 获取所有告警规则
curl -u admin:admin123 http://localhost:10002/api/v1/provisioning/alert-rules

# 创建联系点
curl -X POST -u admin:admin123 \
  -H "Content-Type: application/json" \
  -d '{"name":"test","type":"email","settings":{"addresses":"test@example.com"}}' \
  http://localhost:10002/api/v1/provisioning/contact-points
```

#### 技巧 3: 告警静默（Silences）

临时禁用某些告警，而不删除规则：

1. 进入 **Alerting** → **Silences**
2. 点击 **Add silence** 按钮
3. 配置静默条件（如 `alertname=llm_request_5xx_error_rate_high`）
4. 设置静默时长
5. 点击 **Create** 创建静默

#### 技巧 4: 告警分组优化

合理配置 `Group by` 可以减少告警噪音：

- **按服务分组**：`service`, `alertname`
- **按严重级别分组**：`severity`, `alertname`
- **按时间聚合**：调整 `group_wait` 和 `group_interval`

#### 技巧 5: 使用 Annotations 丰富告警信息

在告警规则的 Annotations 中添加更多上下文：

| Key | 示例值 | 用途 |
|-----|--------|------|
| `runbook_url` | `https://wiki.example.com/runbook/mq-error` | 故障处理手册链接 |
| `dashboard` | `http://localhost:10002/d/abc/llm-metrics` | 相关 Dashboard 链接 |
| `grafana_folder` | `LLM` | 告警分类 |

### 9.3 手动配置 vs Provisioning 对比

| 对比项 | 手动配置 | Provisioning 配置 |
|--------|----------|-------------------|
| **学习难度** | 低，图形界面友好 | 中，需要理解 YAML 格式 |
| **配置速度** | 慢，逐个点击配置 | 快，批量导入 |
| **版本控制** | 困难，需手动导出 | 容易，配置文件存储在 Git |
| **环境迁移** | 麻烦，需重新手动配置 | 简单，复制配置文件即可 |
| **适用场景** | 学习、测试、小规模部署 | 生产环境、多环境管理 |
| **配置灵活性** | 高，所见即所得 | 中，需要重启或刷新 |

**建议**：
- **学习阶段**：使用手动配置，熟悉各个功能
- **生产环境**：使用 Provisioning，便于管理和备份
- **混合使用**：手动配置后导出为 YAML，存储到代码仓库

### 9.4 下一步学习

完成本指南后，你已经掌握了 Grafana 监控系统的核心配置。接下来可以探索：

1. **高级 PromQL 查询**：学习更复杂的查询语法和函数
2. **自定义通知渠道**：集成钉钉、企业微信、Slack 等
3. **Grafana 插件**：安装可视化插件，如饼图、热力图等
4. **Loki 日志聚合**：结合 Grafana Loki 进行日志监控
5. **Grafana Mimir**：高可用 Prometheus 后端存储

---

## 附录

### 快速参考：配置文件位置

| 配置类型 | Provisioning 文件路径 | 手动配置位置 |
|----------|----------------------|--------------|
| 数据源 | `provisioning/datasources/datasource.yml` | Configuration → Data sources |
| 告警规则 | `provisioning/alerting/alert-rules.yaml` | Alerting → Alert rules |
| 联系点 | `provisioning/alerting/contact-points.yaml` | Alerting → Contact points |
| 通知策略 | `provisioning/alerting/notification-policies.yaml` | Alerting → Notification policies |
| 通知模板 | `provisioning/alerting/notification-templates.yaml` | Alerting → Notification templates |
| Dashboard | `provisioning/dashboards/dashboards.yml` | Dashboards → Import/Create |

### 相关文档链接

- **Grafana 官方文档**: https://grafana.com/docs/grafana/latest/
- **Prometheus 查询语法**: https://prometheus.io/docs/prometheus/latest/querying/basics/
- **飞书机器人文档**: https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
- **Grafana Provisioning**: https://grafana.com/docs/grafana/latest/administration/provisioning/

---

**祝你学习愉快！如有问题，请参考现有的 provisioning 配置文件作为参考示例。**
