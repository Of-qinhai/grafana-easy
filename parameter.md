# Grafana 告警通知模板变量速查


很好！你已经配置好了告警规则。现在告诉你如何在飞书卡片模板中使用这些字段：

## 可用的 Grafana 模板变量

基于你填写的内容，可以使用：

| 你填写的字段 | 模板变量 | 说明 |
|------------|---------|------|
| Alert rule name | `{{ .CommonLabels.alertname }}` | 告警规则名称 |
| Summary | `{{ .CommonAnnotations.summary }}` | 摘要信息 |
| Description | `{{ .CommonAnnotations.description }}` | 详细描述 |
| 告警状态 | `{{ .Status }}` | firing（触发中）或 resolved（已恢复）|
| 触发时间 | `{{ range .Alerts }}{{ .StartsAt }}{{ end }}` | 开始时间 |
| 指标值 | `{{ range .Alerts }}{{ .Values }}{{ end }}` | 当前指标值 |

## 完整的飞书卡片模板（带变量替换）

```json
{
    "msg_type": "interactive",
    "card": {
        "schema": "2.0",
        "config": {
            "update_multi": true
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "{{ .CommonLabels.alertname }}"
            },
            "text_tag_list": [
                {
                    "tag": "text_tag",
                    "text": {
                        "tag": "plain_text",
                        "content": "{{ if eq .Status \"firing\" }}告警中{{ else }}已恢复{{ end }}"
                    },
                    "color": "{{ if eq .Status \"firing\" }}red{{ else }}green{{ end }}"
                }
            ],
            "template": "{{ if eq .Status \"firing\" }}red{{ else }}green{{ end }}",
            "icon": {
                "tag": "standard_icon",
                "token": "alert-circle_outlined"
            }
        },
        "body": {
            "direction": "vertical",
            "elements": [
                {
                    "tag": "column_set",
                    "flex_mode": "stretch",
                    "horizontal_spacing": "12px",
                    "columns": [
                        {
                            "tag": "column",
                            "width": "weighted",
                            "weight": 1,
                            "elements": [
                                {
                                    "tag": "markdown",
                                    "content": "**告警状态**\n{{ .Status }}"
                                }
                            ]
                        },
                        {
                            "tag": "column",
                            "width": "weighted",
                            "weight": 1,
                            "elements": [
                                {
                                    "tag": "markdown",
                                    "content": "**触发时间**\n{{ range .Alerts }}{{ .StartsAt }}{{ end }}"
                                }
                            ]
                        }
                    ]
                },
                {
                    "tag": "markdown",
                    "content": "**告警摘要**\n{{ .CommonAnnotations.summary }}"
                },
                {
                    "tag": "markdown",
                    "content": "**详细描述**\n{{ .CommonAnnotations.description }}"
                },
                {
                    "tag": "markdown",
                    "content": "**当前值**\n{{ range .Alerts }}{{ .ValueString }}{{ end }}"
                },
                {
                    "tag": "column_set",
                    "flex_mode": "stretch",
                    "horizontal_spacing": "8px",
                    "columns": [
                        {
                            "tag": "column",
                            "width": "auto",
                            "elements": [
                                {
                                    "tag": "button",
                                    "text": {
                                        "tag": "plain_text",
                                        "content": "查看Grafana"
                                    },
                                    "type": "primary_filled",
                                    "behaviors": [
                                        {
                                            "type": "open_url",
                                            "default_url": "{{ .ExternalURL }}"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    }
}
```

## 如果还想显示具体指标信息

你的指标是 `sum(rate(llm_record_mq_write_duration_seconds_count[$__rate_interval]))`，可以这样显示：

```json
{
    "tag": "column_set",
    "flex_mode": "stretch",
    "horizontal_spacing": "12px",
    "columns": [
        {
            "tag": "column",
            "width": "weighted",
            "weight": 1,
            "background_style": "grey-50",
            "elements": [
                {
                    "tag": "markdown",
                    "content": "## {{ range .Alerts }}{{ .Values }}{{ end }}",
                    "text_align": "center"
                },
                {
                    "tag": "markdown",
                    "content": "<font color='grey'>MQ写入速率</font>",
                    "text_align": "center"
                }
            ],
            "padding": "12px 12px 12px 12px"
        }
    ]
}
```

## 简化版（推荐先测试这个）

```json
{
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "{{ .CommonLabels.alertname }}"
            },
            "template": "red"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "**告警状态**: {{ .Status }}\n**摘要**: {{ .CommonAnnotations.summary }}\n**描述**: {{ .CommonAnnotations.description }}\n{{ range .Alerts }}**当前值**: {{ .ValueString }}\n**触发时间**: {{ .StartsAt }}{{ end }}"
                }
            }
        ]
    }
}
```

## 测试步骤

1. **先触发告警**（让指标超过阈值 47000，持续 1 分钟）
2. **查看飞书消息**，确认变量是否正确替换
3. **根据实际效果调整**模板格式

## 关于 Keep firing for 1m

这个设置表示：
- 条件满足后，**等待 1 分钟**确认问题持续存在
- 1 分钟后才发送告警（避免瞬时波动误报）
- 不是"每 1 分钟发一次"

所以你触发告警后，需要等 1 分钟才会收到飞书消息！
