# 运行
## 一般运行
1.运行 `python3 scripts/*_consume.pyc [ID] -t [0|>]`

## 出现问题
1. 消息已被认领但无法消费
```bash
xinfo groups [stream_*]
```
查看pending状态

2. 查看哪些消息没被消费
```bash
XPENDING [stream_*] [steam_*]_consumers - + 10
```
查看消息阻塞情况

3. 查找原因，并修复消费者
```bash
python3 scripts/*_consume.pyc [ID] -t 0
```
使用 `-t 0` 消费掉历史数据, `-t >` 监听未被消费的数据


