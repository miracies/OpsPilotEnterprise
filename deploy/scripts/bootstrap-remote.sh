#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y docker.io docker-compose-v2 git curl ca-certificates python3-pip

mkdir -p /etc/docker /root/.pip

cat >/etc/docker/daemon.json <<'JSON'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1ms.run"
  ]
}
JSON

cat >/root/.pip/pip.conf <<'CONF'
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
CONF

systemctl enable docker
systemctl restart docker

cat >/etc/sysctl.d/99-opspilot-opensearch.conf <<'CONF'
vm.max_map_count=262144
CONF
sysctl --system >/dev/null

docker --version
docker compose version
python3 -m pip --version
