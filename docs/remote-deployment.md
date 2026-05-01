# OpsPilot 涓€閿繙绔儴缃?
閫傜敤鍦烘櫙锛?- 鏈満鏄?Windows
- 鐩爣鏈烘槸 Linux
- 閫氳繃 SSH 鍏嶅瘑鐧诲綍
- 闇€瑕佽嚜鍔ㄩ厤缃?Docker 鍥藉唴婧愬拰 pip 鍥藉唴婧?
## 鑴氭湰浣嶇疆

- 鏈湴涓€閿儴缃诧細`E:\work\git\OpsPilot\scripts\deploy-remote.ps1`
- 杩滅 bootstrap锛歚E:\work\git\OpsPilot\deploy\scripts\bootstrap-remote.sh`

## 榛樿琛屼负

閮ㄧ讲鑴氭湰浼氳嚜鍔ㄥ畬鎴愪互涓嬪姩浣滐細

1. 鎵撳寘椤圭洰婧愮爜
2. 涓婁紶鍒拌繙绔?3. 瀹夎杩滅渚濊禆
   - `docker.io`
   - `docker-compose-v2`
   - `python3-pip`
   - `curl`
   - `ca-certificates`
4. 閰嶇疆 Docker 鍥藉唴闀滃儚
5. 閰嶇疆 pip 娓呭崕婧?6. 瑙ｅ帇椤圭洰鍒拌繙绔洰褰?7. 娓呯悊 Dockerfile / `.env` / shell 鑴氭湰鐨?UTF-8 BOM
8. 鎵ц `docker compose up -d --build`
9. 鎵ц鍩虹鍋ュ悍妫€鏌?
## 鍩烘湰鐢ㄦ硶

```powershell
cd E:\work\git\OpsPilot
.\scripts\deploy-remote.ps1 -RemoteHost 192.168.51.169
```

榛樿鍙傛暟锛?
- `User=root`
- `Port=22`
- `RemoteBaseDir=/opt/opspilot`
- `ProjectDirName=opspilot-enterprise`

閮ㄧ讲瀹屾垚鍚庯紝椤圭洰浼氳惤鍒帮細

```text
/opt/opspilot/opspilot-enterprise
```

## 甯?kubeconfig 閮ㄧ讲

濡傛灉杩滅闇€瑕佸惎鐢?K8s 鐩戞帶锛屽彲浠ユ妸鏈湴 kubeconfig 涓€骞朵紶涓婂幓锛?
```powershell
.\scripts\deploy-remote.ps1 `
  -RemoteHost 192.168.51.169 `
  -KubeconfigPath C:\Users\mirac\.kube\config
```

鑴氭湰浼氭妸 kubeconfig 涓婁紶鍒帮細

```text
/root/.kube/config
```

骞舵妸 `.env` 閲岀殑 `K8S_KUBECONFIG_PATH` 鍥哄畾涓猴細

```text
/root/.kube/config
```

## 涓嶅惎鐢?K8s 鐩戞帶

濡傛灉鐩爣鏈烘病鏈?kubeconfig锛屽彲浠ュ湪閮ㄧ讲鏃剁洿鎺ュ叧闂?`k8s_workload` collector锛?
```powershell
.\scripts\deploy-remote.ps1 `
  -RemoteHost 192.168.51.169 `
  -DisableK8sMonitoring
```

杩欎細鎶?`.env` 涓殑锛?
```text
K8S_WORKLOAD_INTERVAL_SECONDS=0
```

鍐欏叆椤圭洰閰嶇疆銆傚綋鍓嶄唬鐮佸凡鏀寔 `interval=0` 鏃跺皢 collector 鏍囪涓?`disabled`锛屼笉浼氭寔缁姤閿欍€?
## 甯哥敤鍙傛暟

```powershell
.\scripts\deploy-remote.ps1 `
  -RemoteHost 192.168.51.169 `
  -User root `
  -Port 22 `
  -RemoteBaseDir /opt/opspilot
```

鍙€夊弬鏁帮細

- `-SkipBootstrap`
  - 璺宠繃杩滅渚濊禆瀹夎鍜屽浗鍐呮簮閰嶇疆
- `-SkipBuild`
  - 鍙笂浼犲拰瑙ｅ帇锛屼笉鎵ц `docker compose up -d --build`

## 閮ㄧ讲鍚庤闂湴鍧€

- Web: `http://<host>:3000`
- API BFF: `http://<host>:8000`
- Orchestrator: `http://<host>:8010`
- Tool Gateway: `http://<host>:8020`

## 褰撳墠鑴氭湰鐨勯儴缃茬害鏉?
1. 杩滅蹇呴』鏄?Debian/Ubuntu 绯?Linux
2. 杩滅蹇呴』鍏佽 root SSH
3. 鏈湴蹇呴』鏈夛細
   - `ssh`
   - `scp`
   - `tar`
4. 椤圭洰鏍圭洰褰曞繀椤诲瓨鍦?`.env`

## 鎺ㄨ崘鐢ㄦ硶

褰撳墠瀹為檯鐜鎺ㄨ崘鐩存帴浣跨敤锛?
```powershell
.\scripts\deploy-remote.ps1 `
  -RemoteHost 192.168.51.169 `
  -DisableK8sMonitoring
```

濡傛灉鍚庣画瑕佹帴鍏?K8s锛屽啀鏀规垚锛?
```powershell
.\scripts\deploy-remote.ps1 `
  -RemoteHost 192.168.51.169 `
  -KubeconfigPath C:\Users\mirac\.kube\config
```
