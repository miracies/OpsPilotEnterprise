export type SecretType =
  | "vcenter"
  | "kubeconfig"
  | "api_key"
  | "database"
  | "ssh_key"
  | "certificate"
  | "generic";

export interface SecretMeta {
  id: string;
  name: string;
  display_name: string;
  secret_type: SecretType | string;
  description: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface SecretStats {
  total: number;
  by_type: Record<string, number>;
}

export interface RevealedSecret {
  name: string;
  value: string;
}
