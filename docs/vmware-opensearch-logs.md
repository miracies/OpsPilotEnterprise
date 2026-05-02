# VMware vCenter / ESXi 日志接入 OpenSearch

OpsPilot 的日志接入边界是：采集、索引、保留策略交给 OpenSearch 与 Fluent Bit；OpsPilot 通过 Log Gateway 检索日志、引用原始日志证据，并在 RCA 中生成可追溯的证据链。

## 部署组件

`deploy/docker/docker-compose.yml` 已包含：

- `opensearch`: 单节点 OpenSearch，默认 HTTPS + Basic Auth。
- `opensearch-dashboards`: 原生日志检索 UI。
- `fluent-bit`: syslog receiver，监听 `1514/tcp` 与 `1514/udp`。
- `log-gateway`: 自动使用 `OPENSEARCH_URL` / `OPENSEARCH_USERNAME` / `OPENSEARCH_PASSWORD` seed 默认日志源。

默认索引：

- `opspilot-vmware-esxi-logs-YYYY.MM.DD`
- `opspilot-vmware-vcenter-logs-YYYY.MM.DD`

默认字段：

```text
@timestamp, collector_received_time, raw_message, message,
source_type, product, component, severity,
hostname, source_host, source,
vcenter, object_name, object_moid, vm_name, vm_moid,
datastore, datastore_name, event_type, task_id
```

## ESXi 配置

在每台 ESXi 上配置 remote syslog：

```bash
esxcli system syslog config set --loghost='tcp://192.168.51.169:1514'
esxcli system syslog reload
esxcli network firewall ruleset set --ruleset-id=syslog --enabled=true
esxcli network firewall refresh
esxcli system syslog mark --message "OpsPilot ESXi syslog test message"
```

也可以使用 UDP：

```bash
esxcli system syslog config set --loghost='udp://192.168.51.169:1514'
esxcli system syslog reload
```

## vCenter 配置

在 vCenter Server Appliance 管理界面或 API 中配置 syslog forwarding：

```text
tcp://192.168.51.169:1514
```

推荐至少转发 vCenter 主服务与告警相关日志，例如 `vpxd`、`vpxd-alert`、`sps`、`eam`。Fluent Bit 会根据组件名将日志写入 vCenter 索引。

## 验收流程

1. 启动服务：

   ```bash
   cd /opt/opspilot/opspilot-enterprise/deploy/docker
   docker compose up -d --build
   ```

2. 验证 OpenSearch：

   ```bash
   curl -k -u admin:${OPENSEARCH_PASSWORD} https://127.0.0.1:9200/_cluster/health
   ```

3. 验证 Fluent Bit 端口：

   ```bash
   nc -vz 127.0.0.1 1514
   ```

4. 发送测试日志：

   ```bash
   logger -n 192.168.51.169 -P 1514 -T "hostd: OpsPilot test VM overallStatus red vm-123 Datastore ds-prod-01"
   ```

5. 验证索引：

   ```bash
   curl -k -u admin:${OPENSEARCH_PASSWORD} \
     "https://127.0.0.1:9200/opspilot-vmware-*/_search?q=OpsPilot%20test&pretty"
   ```

6. 验证 OpsPilot：

   - 打开 `http://192.168.51.169:3000/logs/search`
   - 搜索 `OpsPilot test`、`vm-123`、`hostd`
   - 在 VM `overallStatus=red` 诊断中确认 RCA evidence 出现 `source_type=log` 与 OpenSearch Dashboards 外链。
   - Dashboards 外链使用 `/auth/anonymous?nextUrl=...`，会以匿名只读身份自动进入日志页面，不应停在登录表单。

## RCA 行为

当前阶段日志只作为 RCA 证据召回与引用：

- 缺日志源、OpenSearch 不可达、认证失败不会中断 RCA。
- 命中的日志证据保留 `raw_message`、`backend`、`index`、`document_id`、`timestamp`。
- 不根据 APD/PDL、vpxa timeout、FDM 等日志模式直接改写根因结论；日志判因规则留作下一阶段。
