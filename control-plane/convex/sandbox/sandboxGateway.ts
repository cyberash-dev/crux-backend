export type SandboxSpec = {
  snapshot: string;
  outboundProxyUrl: string;
  envVars: Record<string, string>;
  labels: Record<string, string>;
};

export interface SandboxGateway {
  create(spec: SandboxSpec): Promise<string>;
  startWorker(sandboxId: string): Promise<void>;
  delete(sandboxId: string): Promise<void>;
}
