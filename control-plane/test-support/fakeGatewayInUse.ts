import { vi } from "vitest";
import { daytonaSandboxGateway } from "../convex/sandbox/daytonaGatewayFactory";
import { FakeSandboxGateway } from "./FakeSandboxGateway";

/* Callers must vi.mock("./sandbox/daytonaGatewayFactory") so that the
   provisioning actions receive this fake instead of a Daytona client. */
export function fakeGatewayInUse(
  failure: ConstructorParameters<typeof FakeSandboxGateway>[0] = null,
): FakeSandboxGateway {
  const gateway = new FakeSandboxGateway(failure);
  vi.mocked(daytonaSandboxGateway).mockReturnValue(gateway);
  return gateway;
}
