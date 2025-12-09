import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { resolve } from "path";

describe("Project setup", () => {
  it("root package.json has required fields", () => {
    const packagePath = resolve(process.cwd(), "package.json");
    const content = readFileSync(packagePath, "utf-8");
    const pkg = JSON.parse(content);

    expect(pkg.name).toBe("@meta-mcp/monorepo");
    expect(pkg.type).toBe("module");
    expect(pkg.devDependencies["typescript"]).toBeDefined();
  });

  it("meta-mcp package.json has required dependencies", () => {
    const packagePath = resolve(process.cwd(), "packages/meta-mcp/package.json");
    const content = readFileSync(packagePath, "utf-8");
    const pkg = JSON.parse(content);

    expect(pkg.name).toBe("@meta-mcp/server");
    expect(pkg.dependencies["@modelcontextprotocol/sdk"]).toBeDefined();
    expect(pkg.dependencies["zod"]).toBeDefined();
  });

  it("tsconfig.json exists and is valid", () => {
    const tsconfigPath = resolve(process.cwd(), "tsconfig.json");
    const content = readFileSync(tsconfigPath, "utf-8");
    const tsconfig = JSON.parse(content);

    expect(tsconfig.compilerOptions.target).toBe("ES2020");
    expect(tsconfig.compilerOptions.module).toBe("ES2020");
    expect(tsconfig.compilerOptions.strict).toBe(true);
  });
});
