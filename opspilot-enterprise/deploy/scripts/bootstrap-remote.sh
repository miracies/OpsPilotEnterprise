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
    "https://mirror.ccs.tencentyun.com",
    "https://hub-mirror.c.163.com"
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

docker --version
docker compose version
python3 -m pip --version
