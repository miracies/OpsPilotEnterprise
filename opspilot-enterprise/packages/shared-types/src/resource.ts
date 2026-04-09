export interface ResourceConnectionRef {
  connection_id: string;
  connection_name: string;
  connection_type: string;
  endpoint: string;
}

export interface VCenterOverview {
  connection: ResourceConnectionRef;
  vcenter: string;
  generated_at: string;
  summary: {
    datacenter_count: number;
    cluster_count: number;
    host_count: number;
    vm_count: number;
    datastore_count: number;
    powered_off_vm_count: number;
    unhealthy_host_count: number;
    unhealthy_vm_count: number;
  };
  datacenters: Array<{ id: string; name: string }>;
  clusters: Array<Record<string, unknown>>;
  hosts: Array<Record<string, unknown>>;
}

export interface VCenterInventory extends VCenterOverview {
  virtual_machines: Array<Record<string, unknown>>;
  datastores: Array<Record<string, unknown>>;
}

export interface K8sOverview {
  connection: ResourceConnectionRef;
  cluster_version: string;
  namespace: string | null;
  summary: {
    node_count: number;
    namespace_count: number;
    pod_count: number;
    deployment_count: number;
    ready_node_count: number;
    running_pod_count: number;
    unhealthy_node_count: number;
    unhealthy_pod_count: number;
  };
  namespaces: Array<Record<string, unknown>>;
  nodes: Array<Record<string, unknown>>;
}

export interface K8sWorkloadStatus extends K8sOverview {
  pods: Array<Record<string, unknown>>;
  deployments: Array<Record<string, unknown>>;
}
