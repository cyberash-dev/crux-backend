export interface OperatorChat {
  send(text: string): Promise<void>;
}
