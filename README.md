# trans-jms

将 JustMySocks 订阅转换为 Clash 可用配置的 Python 工具，支持命令行一次性转换，也支持通过 HTTP 接口按 `id` 动态转换。

适合：
- 本地自用（在电脑上运行并生成 Clash 配置）
- 部署到你可控的安全服务器（通过 API 输出 YAML/JSON）

## 功能

- 将订阅地址转换为 Clash 配置
- 当前支持协议：`ss://`、`vmess://`
- 支持输出 Clash YAML（默认）或 JSON
- 通过 `config.yaml` 管理多个订阅源并使用 `id` 调用

## 项目结构

- `jms_to_clash.py`：核心转换逻辑与 CLI 入口
- `service.py`：Flask HTTP 服务
- `config.yaml.template`：配置模板（已脱敏）
- `config.yaml`：本地真实配置（已在 `.gitignore` 忽略）

## 环境要求

- Python 3.8+
- 依赖：`Flask`、`requests`、`PyYAML`

安装依赖：

```bash
pip install -r requirements.txt
```

或使用安装脚本：

```bash
bash ./install.sh
```

## 配置

复制模板并填写你自己的订阅地址：

```bash
cp config.yaml.template config.yaml
```

示例：

```yaml
subscriptions:
  test: "http://localhost:8080/your-subscription"
  jms: "https://your-domain/members/getsub.php?service=YOUR_SERVICE_ID&id=YOUR_UUID"
```

> 注意：`config.yaml` 包含敏感 URL，请勿提交到仓库。

## 用法一：命令行转换

```bash
python3 ./jms_to_clash.py -u "你的订阅地址" -o clash.yaml
```

参数：
- `-u, --url`：订阅地址（必填）
- `-o, --output`：输出文件（默认 `clash.yaml`）
- `--ua`：自定义 User-Agent（可选）

## 用法二：HTTP 服务模式

启动服务（前台）：

```bash
python3 ./service.py
```

或使用 nohup 后台启动脚本：

```bash
bash ./start.sh
```

脚本行为：
- 自动创建 `logs/`
- 日志输出到 `logs/service.log`
- PID 写入 `logs/service.pid`

停止服务：

```bash
bash ./stop.sh
```

重启服务：

```bash
bash ./restart.sh
```

默认监听：`0.0.0.0:9527`

接口：

- `GET /api/v1/convert/{id}`
- `{id}` 来自 `config.yaml` 的 `subscriptions` 键名

可选查询参数：
- `ua`：自定义 User-Agent
- `output_format`：`yaml`（默认）或 `json`

示例：

```bash
curl -i "http://127.0.0.1:9527/api/v1/convert/jms?output_format=yaml"
curl -i "http://127.0.0.1:9527/api/v1/convert/jms?output_format=json"
```

常见状态码：
- `200`：成功
- `400`：参数错误或 `id` 无效
- `422`：未解析到可用节点
- `502`：拉取订阅失败
- `500`：服务内部错误

## 安全建议

如果部署到公网，请至少做到：

- 仅放行可信来源 IP（防火墙/安全组）
- 在反向代理层增加鉴权（Basic Auth / Token）
- 避免在日志、截图、工单中泄露订阅 URL

更推荐：仅在本地或内网使用该服务。