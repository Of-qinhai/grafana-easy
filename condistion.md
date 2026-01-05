## 条件说明

| 英文 | 中文 | 说明 | 示例 |
|------|------|------|------|
| **Is above** | 大于 | 当值超过阈值时触发 | CPU > 80% |
| **Is below** | 小于 | 当值低于阈值时触发 | 磁盘空间 < 10GB |
| **Is equal to** | 等于 | 当值等于某个数时触发 | 错误数 = 0 |
| **Is not equal to** | 不等于 | 当值不等于某个数时触发 | 状态 ≠ 1 |
| **Is above or equal to** | 大于等于 | 当值 ≥ 阈值时触发 | 内存 ≥ 90% |
| **Is below or equal to** | 小于等于 | 当值 ≤ 阈值时触发 | 响应时间 ≤ 100ms |
| **Is within range** | 在范围内 | 当值在某个区间内触发 | 温度在 20-30℃ |
| **Is outside range** | 在范围外 | 当值不在某个区间内触发 | 温度不在 18-25℃ |
| **Is within range included** | 在范围内（含边界） | 包含边界值的范围内 | 值在 [10, 20] |
| **Is outside range included** | 在范围外（含边界） | 包含边界值的范围外 | 值不在 [10, 20] |

## 常用场景举例

### 1. CPU 告警（大于）
```
WHEN QUERY IS ABOVE 80
```
意思：当 CPU 使用率超过 80% 时触发告警

### 2. 磁盘空间告警（小于）
```
WHEN QUERY IS BELOW 10
```
意思：当磁盘剩余空间小于 10GB 时触发告警

### 3. 错误率告警（大于等于）
```
WHEN QUERY IS ABOVE OR EQUAL TO 5
```
意思：当错误率达到或超过 5% 时触发告警

### 4. 响应时间正常（在范围内）
```
WHEN QUERY IS WITHIN RANGE 0 TO 1000
```
意思：当响应时间在 0-1000ms 范围内时触发（通常用于恢复通知）

### 5. 服务异常（在范围外）
```
WHEN QUERY IS OUTSIDE RANGE 200 TO 299
```
意思：当 HTTP 状态码不在 200-299（成功）范围内时触发告警

## 你应该选哪个？

根据你的监控需求：
- **监控 CPU/内存过高** → 选 **Is above**（大于）
- **监控磁盘空间不足** → 选 **Is below**（小于）
- **监控错误率** → 选 **Is above**（大于）
- **监控服务宕机** → 选 **Is equal to 0**（等于 0）

最常用的是 **Is above**（大于）和 **Is below**（小于）！


