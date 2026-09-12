export class MissingEnvError extends Error {
  constructor(names: readonly string[]) {
    super(`control-plane env not set: ${names.join(", ")}`);
    this.name = "MissingEnvError";
  }
}

export function isEnvSet(name: string): boolean {
  return (process.env[name] ?? "") !== "";
}

export function requiredEnv(name: string): string {
  const value = process.env[name];
  if (value === undefined || value === "") {
    throw new MissingEnvError([name]);
  }
  return value;
}
