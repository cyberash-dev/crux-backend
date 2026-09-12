"use node";

import { Daytona } from "@daytona/sdk";
import { DaytonaExaminerGateway } from "./daytonaExaminerGateway";
import type { ExaminerGateway } from "./examinerGateway";

export function daytonaExaminerGateway(apiKey: string): ExaminerGateway {
  return new DaytonaExaminerGateway(new Daytona({ apiKey }));
}
