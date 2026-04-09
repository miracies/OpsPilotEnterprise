from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from opspilot_schema.envelope import make_success

from app.services.k8s_service import KubernetesConnection, _to_api_client, client

router = APIRouter(prefix="/execute", tags=["execute"])


class RestartDeploymentBody(BaseModel):
    namespace: str
    deployment_name: str
    dry_run: bool = False
    connection: dict | None = None


@router.post("/restart_deployment")
async def restart_deployment(body: RestartDeploymentBody) -> dict:
    if body.dry_run:
        return make_success(
            {
                "dry_run": True,
                "namespace": body.namespace,
                "deployment_name": body.deployment_name,
                "action": "rollout_restart",
            }
        )

    connection = KubernetesConnection.from_input(body.connection)
    api_client = _to_api_client(connection)
    apps = client.AppsV1Api(api_client)
    patch = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "kubectl.kubernetes.io/restartedAt": datetime.utcnow().isoformat() + "Z"
                    }
                }
            }
        }
    }
    apps.patch_namespaced_deployment(name=body.deployment_name, namespace=body.namespace, body=patch)
    return make_success(
        {
            "namespace": body.namespace,
            "deployment_name": body.deployment_name,
            "status": "submitted",
            "action": "rollout_restart",
        }
    )
