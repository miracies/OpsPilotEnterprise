---

# 一、vSphere 监控指标（Compute / VM / Host）

## 1️⃣ 虚拟机（VM）核心指标


| Key                       | 名称           | 用途            | 核心  |
| ------------------------- | ------------ | ------------- | --- |
| cpu.usage.average         | CPU 使用率 (%)  | 判断CPU是否瓶颈     | ✔   |
| cpu.ready.summation       | CPU Ready 时间 | 判断CPU争用（超卖关键） | ✔   |
| cpu.coStop.summation      | CPU Co-Stop  | 多核VM调度冲突      | △   |
| mem.usage.average         | 内存使用率 (%)    | VM整体内存压力      | ✔   |
| mem.active.average        | 活跃内存         | 判断真实使用量       | ✔   |
| mem.swapinRate.average    | Swap In      | 内存不足发生交换      | ✔   |
| mem.swapoutRate.average   | Swap Out     | 内存压力严重        | ✔   |
| mem.vmmemctl.average      | Balloon 使用量  | 内存回收压力        | ✔   |
| disk.usage.average        | 磁盘使用率        | IO负载总体情况      | ✔   |
| disk.read.average         | 磁盘读速率 (KB/s) | IO行为分析        | ✔   |
| disk.write.average        | 磁盘写速率 (KB/s) | IO行为分析        | ✔   |
| disk.latency.average      | 磁盘延迟 (ms)    | 性能瓶颈判断        | ✔   |
| disk.queueLatency.average | 队列延迟         | IO拥塞判断        | ✔   |
| net.usage.average         | 网络吞吐         | 流量监控          | ✔   |
| net.packetsRx.summation   | 接收包数         | 网络负载分析        | △   |
| net.packetsTx.summation   | 发送包数         | 网络负载分析        | △   |
| net.droppedRx.summation   | 丢包（接收）       | 网络异常          | ✔   |
| net.droppedTx.summation   | 丢包（发送）       | 网络异常          | ✔   |


---

## 2️⃣ ESXi 主机指标（Host）


| Key                        | 名称                       | 用途       | 核心  |
| -------------------------- | ------------------------ | -------- | --- |
| cpu.usage.average          | CPU 使用率                  | 主机负载     | ✔   |
| cpu.utilization.average    | CPU 利用率                  | 更精细CPU利用 | ✔   |
| cpu.ready.summation        | CPU Ready                | 资源争用     | ✔   |
| mem.usage.average          | 内存使用率                    | 主机内存压力   | ✔   |
| mem.state.latest           | 内存状态（high/soft/hard/low） | 判断内存级别压力 | ✔   |
| mem.swapinRate.average     | Swap In                  | 内存不足     | ✔   |
| mem.swapoutRate.average    | Swap Out                 | 内存不足     | ✔   |
| disk.usage.average         | 磁盘使用率                    | IO整体负载   | ✔   |
| disk.totalLatency.average  | 总延迟                      | IO性能瓶颈   | ✔   |
| disk.deviceLatency.average | 设备延迟                     | 存储侧问题    | ✔   |
| disk.kernelLatency.average | 内核延迟                     | ESXi内部瓶颈 | ✔   |
| disk.queueLatency.average  | 队列延迟                     | IO排队情况   | ✔   |
| net.usage.average          | 网络吞吐                     | 主机流量     | ✔   |
| net.errorsRx.summation     | 接收错误                     | 网络异常     | ✔   |
| net.errorsTx.summation     | 发送错误                     | 网络异常     | ✔   |
| net.droppedRx.summation    | 丢包接收                     | 网络问题     | ✔   |
| net.droppedTx.summation    | 丢包发送                     | 网络问题     | ✔   |


---

## 3️⃣ 数据存储（Datastore）


| Key                                   | 名称         | 用途   | 核心  |
| ------------------------------------- | ---------- | ---- | --- |
| datastore.capacity.usage              | 容量使用率      | 空间规划 | ✔   |
| datastore.read.average                | 读速率        | IO分析 | ✔   |
| datastore.write.average               | 写速率        | IO分析 | ✔   |
| datastore.totalLatency.average        | 总延迟        | 性能瓶颈 | ✔   |
| datastore.numberReadAveraged.average  | IOPS Read  | IO性能 | ✔   |
| datastore.numberWriteAveraged.average | IOPS Write | IO性能 | ✔   |


---

# 二、vSAN 监控指标（核心重点）

vSAN指标是AIOps重点（尤其你做故障诊断）

---

## 1️⃣ 集群级（Cluster）


| Key                            | 名称     | 用途       | 核心  |
| ------------------------------ | ------ | -------- | --- |
| vsan.cluster.capacity.used     | 已用容量   | 容量趋势     | ✔   |
| vsan.cluster.capacity.total    | 总容量    | 容量规划     | ✔   |
| vsan.cluster.capacity.free     | 剩余容量   | 预警       | ✔   |
| vsan.cluster.iops.read         | 读IOPS  | 性能负载     | ✔   |
| vsan.cluster.iops.write        | 写IOPS  | 性能负载     | ✔   |
| vsan.cluster.throughput.read   | 读吞吐    | 带宽分析     | ✔   |
| vsan.cluster.throughput.write  | 写吞吐    | 带宽分析     | ✔   |
| vsan.cluster.latency.read      | 读延迟    | 性能瓶颈     | ✔   |
| vsan.cluster.latency.write     | 写延迟    | 性能瓶颈     | ✔   |
| vsan.cluster.congestion        | 拥塞度    | 性能退化关键指标 | ✔   |
| vsan.cluster.resyncing.bytes   | 重同步流量  | 故障/恢复状态  | ✔   |
| vsan.cluster.resyncing.objects | 重同步对象数 | 数据恢复压力   | ✔   |


---

## 2️⃣ 磁盘组 / 磁盘层（Disk Group / Disk）


| Key                       | 名称      | 用途     | 核心  |
| ------------------------- | ------- | ------ | --- |
| vsan.diskgroup.iops       | 磁盘组IOPS | 性能定位   | ✔   |
| vsan.diskgroup.latency    | 磁盘组延迟   | 性能瓶颈   | ✔   |
| vsan.diskgroup.throughput | 吞吐      | 带宽瓶颈   | ✔   |
| vsan.diskgroup.congestion | 拥塞      | 关键瓶颈指标 | ✔   |
| vsan.disk.readLatency     | 磁盘读延迟   | 磁盘问题   | ✔   |
| vsan.disk.writeLatency    | 磁盘写延迟   | 磁盘问题   | ✔   |
| vsan.disk.queueDepth      | 队列深度    | IO拥塞   | ✔   |
| vsan.disk.capacity.used   | 磁盘已用容量  | 容量分析   | ✔   |


---

## 3️⃣ 主机 vSAN 网络


| Key                              | 名称   | 用途   | 核心  |
| -------------------------------- | ---- | ---- | --- |
| vsan.host.network.rxThroughput   | 接收吞吐 | 网络带宽 | ✔   |
| vsan.host.network.txThroughput   | 发送吞吐 | 网络带宽 | ✔   |
| vsan.host.network.packetsDropped | 丢包   | 网络问题 | ✔   |
| vsan.host.network.latency        | 网络延迟 | 性能瓶颈 | ✔   |


---

## 4️⃣ vSAN 对象 / 组件


| Key                   | 名称     | 用途   | 核心  |
| --------------------- | ------ | ---- | --- |
| vsan.object.health    | 对象健康状态 | 数据安全 | ✔   |
| vsan.object.absent    | 缺失对象   | 故障判断 | ✔   |
| vsan.component.state  | 组件状态   | 故障分析 | ✔   |
| vsan.component.resync | 是否重同步  | 故障恢复 | ✔   |


---

# 一、vSAN 主机级（Host）核心指标

## 1️⃣ 前端（Frontend Client Path）

👉 VM → vSAN（Guest IO路径）


| Key                                 | 名称      | 用途         | 核心  |
| ----------------------------------- | ------- | ---------- | --- |
| vsan.host.frontend.iops.read        | 前端读IOPS | VM读请求压力    | ✔   |
| vsan.host.frontend.iops.write       | 前端写IOPS | VM写请求压力    | ✔   |
| vsan.host.frontend.throughput.read  | 前端读吞吐   | 带宽消耗       | ✔   |
| vsan.host.frontend.throughput.write | 前端写吞吐   | 带宽消耗       | ✔   |
| vsan.host.frontend.latency.read     | 前端读延迟   | VM体验指标（关键） | ✔   |
| vsan.host.frontend.latency.write    | 前端写延迟   | VM体验指标（关键） | ✔   |
| vsan.host.frontend.congestion       | 前端拥塞度   | IO排队/阻塞    | ✔   |


👉 **关键解释：**

- 前端 latency = 用户真正感知的延迟
- 前端 congestion ↑ → 用户体验直接下降

---

## 2️⃣ 后端（Backend Storage Path）

👉 vSAN 内部（复制 / RAID / 网络）


| Key                                | 名称      | 用途      | 核心  |
| ---------------------------------- | ------- | ------- | --- |
| vsan.host.backend.iops.read        | 后端读IOPS | 磁盘读取压力  | ✔   |
| vsan.host.backend.iops.write       | 后端写IOPS | 写入复制压力  | ✔   |
| vsan.host.backend.throughput.read  | 后端读吞吐   | 带宽分析    | ✔   |
| vsan.host.backend.throughput.write | 后端写吞吐   | 带宽分析    | ✔   |
| vsan.host.backend.latency.read     | 后端读延迟   | 存储性能瓶颈  | ✔   |
| vsan.host.backend.latency.write    | 后端写延迟   | 存储性能瓶颈  | ✔   |
| vsan.host.backend.congestion       | 后端拥塞    | 磁盘或网络瓶颈 | ✔   |


👉 **关键解释：**

- 前端慢 ≠ 后端慢（要区分）
- 后端 latency ↑ → 磁盘 / 网络问题

---

## 3️⃣ Resync（重同步 / 数据修复）


| Key                             | 名称       | 用途     | 核心  |
| ------------------------------- | -------- | ------ | --- |
| vsan.host.resync.iops.read      | 重同步读IOPS | 修复读取压力 | ✔   |
| vsan.host.resync.iops.write     | 重同步写IOPS | 修复写入压力 | ✔   |
| vsan.host.resync.throughput     | 重同步吞吐    | 带宽占用   | ✔   |
| vsan.host.resync.latency        | 重同步延迟    | 修复效率   | ✔   |
| vsan.host.resync.congestion     | 重同步拥塞    | 是否影响业务 | ✔   |
| vsan.host.resync.bytesRemaining | 剩余数据量    | 恢复进度   | ✔   |
| vsan.host.resync.objects        | 重同步对象数   | 故障规模   | ✔   |


👉 **关键解释：**

- resync 是**性能杀手**
- AIOps必须识别：
👉 “业务慢 vs resync导致慢”

---

# 二、写缓存（Write Buffer / Cache Tier）指标

👉 vSAN性能问题80%来自缓存层

---

## 1️⃣ Cache 使用情况


| Key                             | 名称      | 用途    | 核心  |
| ------------------------------- | ------- | ----- | --- |
| vsan.host.cache.usage           | 缓存使用率   | 是否接近满 | ✔   |
| vsan.host.cache.writeBufferFree | 写缓冲剩余空间 | 写入能力  | ✔   |
| vsan.host.cache.evictionRate    | 淘汰速率    | 压力判断  | ✔   |


---

## 2️⃣ 写缓存 IO


| Key                           | 名称        | 用途     | 核心  |
| ----------------------------- | --------- | ------ | --- |
| vsan.host.cache.write.iops    | 写缓存IOPS   | 写入压力   | ✔   |
| vsan.host.cache.write.latency | 写缓存延迟     | 写入性能   | ✔   |
| vsan.host.cache.read.iops     | 缓存命中读IOPS | 命中率判断  | ✔   |
| vsan.host.cache.hitRate       | 缓存命中率     | 性能关键指标 | ✔   |


---

## 3️⃣ 写缓存拥塞（极其关键）


| Key                             | 名称     | 用途     | 核心  |
| ------------------------------- | ------ | ------ | --- |
| vsan.host.cache.congestion      | 缓存拥塞度  | 性能瓶颈核心 | ✔   |
| vsan.host.cache.writeBufferFull | 写缓冲是否满 | 写入阻塞   | ✔   |


👉 **关键解释（非常重要）：**

- cache congestion ↑ → 前端 latency ↑
- write buffer full → 写IO被阻塞（典型性能故障）

