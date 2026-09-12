"use node";

import { Daytona } from "@daytona/sdk";
import { DaytonaSandboxGateway } from "./daytonaSandboxGateway";
import type { SandboxGateway } from "./sandboxGateway";

export function daytonaSandboxGateway(apiKey: string): SandboxGateway {
  return new DaytonaSandboxGateway(new Daytona({ apiKey }));
}
