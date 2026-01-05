#!/bin/bash

# 测试飞书 webhook 模板
# 这个脚本会发送一个测试告警到飞书

WEBHOOK_URL=""

# 创建一个简单的测试 payload
cat > /tmp/test-feishu.json << 'EOF'
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
        "content": "测试告警"
      },
      "text_tag_list": [
        {
          "tag": "text_tag",
          "text": {
            "tag": "plain_text",
            "content": "告警中"
          },
          "color": "red"
        }
      ],
      "template": "red",
      "padding": "12px 8px 12px 8px"
    },
    "body": {
      "direction": "vertical",
      "elements": [
        {
          "tag": "markdown",
          "content": "**规则**\n测试规则",
          "margin": "0px 0px 0px 0px"
        },
        {
          "tag": "markdown",
          "content": "**摘要**\n这是一个测试消息",
          "margin": "0px 0px 0px 0px"
        }
      ]
    }
  }
}
EOF

echo "发送测试消息到飞书..."
curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d @/tmp/test-feishu.json \
  -v

echo ""
echo "测试完成"
