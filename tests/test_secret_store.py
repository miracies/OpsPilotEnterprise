import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api-bff"))

from app.services.secret_store import parse_secret_payload


def test_parse_vcenter_secret_payload():
    payload = parse_secret_payload("vcenter", '{"username":"admin","password":"secret"}')
    assert payload["secret_type"] == "vcenter"
    assert payload["username"] == "admin"
    assert payload["password"] == "secret"


def test_parse_kubeconfig_secret_payload_from_yaml():
    payload = parse_secret_payload(
        "kubeconfig",
        """
apiVersion: v1
kind: Config
clusters:
  - name: demo
    cluster:
      server: https://k8s.example.local:6443
users:
  - name: demo
    user:
      token: abc
contexts:
  - name: demo
    context:
      cluster: demo
      user: demo
current-context: demo
""".strip(),
    )
    assert payload["secret_type"] == "kubeconfig"
    assert payload["kubeconfig"]["clusters"][0]["cluster"]["server"] == "https://k8s.example.local:6443"
