#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const outputFile = path.join(repoRoot, "frontend", "src", "api", "types.ts");

const shouldCheck = process.argv.includes("--check");

const compatibilityFooter = `// Compatibility aliases used by the frontend codebase.
export type StrategyType = SchemaStrategyType;
export type ExecutionMode = SchemaExecutionMode;
export type WeightsConfig = SchemaWeightsConfig;
export type StrategyProfile = SchemaStrategyProfileResponse;
export type PartDetail = SchemaPartDetail;
export type RiskLevel = "Low" | "Medium" | "High";
export type TrendDirection = "rising" | "falling" | "stable";

export type ScoredSet = Omit<SchemaScoredData, "risk_level" | "trend_direction"> & {
  risk_level: RiskLevel;
  trend_direction: TrendDirection;
  liquidity_contribution?: number;
};

export type AnalysisResponse = Omit<SchemaAnalysisResponse, "sets"> & {
  sets: ScoredSet[];
};

export type AnalysisStatus = Omit<SchemaAnalysisStatusResponse, "status"> & {
  status: "idle" | "running" | "completed" | "error";
};

export interface RescoreResponse {
  sets: ScoredSet[];
  total_sets: number;
  profitable_sets: number;
  strategy: StrategyType;
  execution_mode?: ExecutionMode;
  weights: WeightsConfig;
}

export type HistoryRun = Omit<SchemaHistoryRun, "avg_profit" | "max_profit"> & {
  avg_profit: number | null;
  max_profit: number | null;
};

export type HistoryResponse = Omit<SchemaHistoryResponse, "runs"> & {
  runs: HistoryRun[];
};

export interface RunDetail extends Omit<SchemaRunDetailResponse, "sets" | "summary"> {
  sets: Array<{
    set_slug: string;
    set_name: string;
    profit_margin: number;
    lowest_price: number;
  }>;
  summary: {
    total_sets: number;
    average_profit: number;
    max_profit: number;
    min_profit: number;
    profitable_sets: number;
  };
}

export type DatabaseStats = SchemaDatabaseStats;
export type AnalysisStats = SchemaAnalysisStats;
export type StatsResponse = SchemaStatsResponse;
export type SetHistoryEntry = SchemaSetHistoryEntry;
export type SetDetail = SchemaSetDetailResponse;
`;

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: repoRoot,
    encoding: "utf-8",
    stdio: "pipe",
    ...options,
  });

  if (result.status !== 0) {
    const stderr = (result.stderr ?? "").trim();
    const stdout = (result.stdout ?? "").trim();
    const message = stderr || stdout || `Command failed: ${command} ${args.join(" ")}`;
    throw new Error(message);
  }

  return result;
}

function resolvePythonExecutable() {
  const candidates = [
    path.join(repoRoot, "backend", "venv", "bin", "python"),
    "python3",
    "python",
  ];

  for (const candidate of candidates) {
    const localBinary = candidate.includes(path.sep);
    if (localBinary && !existsSync(candidate)) {
      continue;
    }

    const result = spawnSync(candidate, ["--version"], {
      cwd: repoRoot,
      stdio: "ignore",
    });

    if (result.status === 0) {
      return candidate;
    }
  }

  throw new Error("Python executable not found. Install Python 3 or create backend/venv first.");
}

function buildFinalTypes(generatedContent) {
  return `${generatedContent.trimEnd()}\n\n${compatibilityFooter}`;
}

function main() {
  const tempDir = mkdtempSync(path.join(tmpdir(), "wf-openapi-"));
  const schemaPath = path.join(tempDir, "openapi.json");
  const generatedPath = path.join(tempDir, "types.generated.ts");

  try {
    const python = resolvePythonExecutable();
    run(python, [path.join(repoRoot, "scripts", "export_openapi_schema.py"), schemaPath]);

    run("npm", [
      "exec",
      "--prefix",
      "frontend",
      "openapi-typescript",
      "--",
      schemaPath,
      "-o",
      generatedPath,
      "--root-types",
      "true",
    ]);

    const generatedContent = readFileSync(generatedPath, "utf-8");
    const finalContent = buildFinalTypes(generatedContent);

    if (shouldCheck) {
      const currentContent = existsSync(outputFile) ? readFileSync(outputFile, "utf-8") : "";
      if (currentContent !== finalContent) {
        console.error("frontend/src/api/types.ts is out of date. Run: npm --prefix frontend run generate:api-types");
        process.exitCode = 1;
        return;
      }

      console.log("frontend/src/api/types.ts is up to date.");
      return;
    }

    writeFileSync(outputFile, finalContent, "utf-8");
    console.log(`Generated ${path.relative(repoRoot, outputFile)} from backend OpenAPI schema.`);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

main();
