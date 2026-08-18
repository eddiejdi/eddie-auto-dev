/**
 * Spawn existing Python Claude hooks and parse JSON decisions.
 * Fail-open on timeout/parse errors (except explicit deny/ask in valid JSON).
 */

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

export type HookDecision = {
  ok: boolean;
  raw: string;
  parsed: Record<string, unknown> | null;
  permissionDecision?: "deny" | "ask" | "allow";
  permissionReason?: string;
  additionalContext?: string;
  stopDecision?: "block" | "continue";
  stopReason?: string;
  error?: string;
};

function findRepoRoot(startCwd: string): string {
  // Prefer monorepo markers walking up from cwd
  let dir = resolve(startCwd);
  for (let i = 0; i < 12; i++) {
    if (
      existsSync(join(dir, "tools", "copilot_hooks")) &&
      existsSync(join(dir, "tools", "hooks"))
    ) {
      return dir;
    }
    const parent = resolve(dir, "..");
    if (parent === dir) break;
    dir = parent;
  }
  // Fallback to known workspace path
  const fallback = "/workspace/eddie-auto-dev";
  if (existsSync(join(fallback, "tools", "copilot_hooks"))) {
    return fallback;
  }
  return startCwd;
}

export function resolveScript(repoRoot: string, scriptRel: string): string {
  return join(repoRoot, scriptRel);
}

export async function runPythonHook(
  scriptRel: string,
  payload: Record<string, unknown>,
  options: {
    cwd: string;
    timeoutMs: number;
    env?: Record<string, string | undefined>;
    args?: string[];
  },
): Promise<HookDecision> {
  const repoRoot = findRepoRoot(options.cwd);
  const scriptPath = resolveScript(repoRoot, scriptRel);

  if (!existsSync(scriptPath)) {
    return {
      ok: false,
      raw: "",
      parsed: null,
      error: `hook script not found: ${scriptPath}`,
    };
  }

  const stdinPayload = JSON.stringify(payload);
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    CLAUDE_PROJECT_DIR: repoRoot,
    PI_CODING_AGENT: "true",
    ...options.env,
  };

  return await new Promise((resolveDecision) => {
    const child = spawn("python3", [scriptPath, ...(options.args ?? [])], {
      cwd: repoRoot,
      env,
      stdio: ["pipe", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let settled = false;

    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      try {
        child.kill("SIGTERM");
      } catch {
        /* ignore */
      }
      resolveDecision({
        ok: false,
        raw: stdout,
        parsed: null,
        error: `timeout after ${options.timeoutMs}ms (${scriptRel}): ${stderr.slice(0, 200)}`,
      });
    }, options.timeoutMs);

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
    });

    child.on("error", (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolveDecision({
        ok: false,
        raw: stdout,
        parsed: null,
        error: `spawn error: ${err.message}`,
      });
    });

    child.on("close", () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolveDecision(parseHookOutput(stdout, stderr));
    });

    child.stdin.write(stdinPayload);
    child.stdin.end();
  });
}

function parseHookOutput(stdout: string, stderr: string): HookDecision {
  const raw = stdout.trim();
  if (!raw) {
    // Many hooks exit 0 with empty stdout = allow
    return { ok: true, raw: "", parsed: null, permissionDecision: "allow" };
  }

  let parsed: Record<string, unknown> | null = null;
  try {
    // Some hooks may print multiple lines; take last JSON object line
    const lines = raw
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    const candidate = lines[lines.length - 1] ?? raw;
    parsed = JSON.parse(candidate) as Record<string, unknown>;
  } catch {
    return {
      ok: false,
      raw,
      parsed: null,
      error: `invalid JSON from hook: ${raw.slice(0, 200)} stderr=${stderr.slice(0, 120)}`,
    };
  }

  const nested =
    parsed.hookSpecificOutput && typeof parsed.hookSpecificOutput === "object"
      ? (parsed.hookSpecificOutput as Record<string, unknown>)
      : parsed;

  const permissionDecision = String(
    nested.permissionDecision ?? nested.permission_decision ?? "",
  ).toLowerCase() as "deny" | "ask" | "allow" | "";

  const permissionReason = String(
    nested.permissionDecisionReason ??
      nested.permission_decision_reason ??
      nested.reason ??
      nested.additionalContext ??
      "",
  );

  const additionalContext =
    typeof nested.additionalContext === "string"
      ? nested.additionalContext
      : typeof parsed.additionalContext === "string"
        ? parsed.additionalContext
        : undefined;

  const stopDecisionRaw = String(nested.decision ?? parsed.decision ?? "").toLowerCase();
  const stopDecision =
    stopDecisionRaw === "block"
      ? "block"
      : stopDecisionRaw === "approve" || stopDecisionRaw === "continue"
        ? "continue"
        : undefined;

  const stopReason =
    typeof nested.reason === "string"
      ? nested.reason
      : typeof parsed.reason === "string"
        ? parsed.reason
        : undefined;

  return {
    ok: true,
    raw,
    parsed,
    permissionDecision:
      permissionDecision === "deny" ||
      permissionDecision === "ask" ||
      permissionDecision === "allow"
        ? permissionDecision
        : "allow",
    permissionReason: permissionReason || undefined,
    additionalContext,
    stopDecision,
    stopReason,
  };
}

/** PreToolUse chain used by Claude settings (order preserved). */
export const PRE_TOOL_HOOKS: Array<{ script: string; timeoutMs: number }> = [
  { script: "tools/copilot_hooks/pre_tool_guardrails.py", timeoutMs: 10_000 },
  { script: "tools/hooks/variable_registry_validate.py", timeoutMs: 10_000 },
  { script: "tools/hooks/table_registry_validate.py", timeoutMs: 10_000 },
  { script: "tools/hooks/api_registry_validate.py", timeoutMs: 10_000 },
  { script: "tools/hooks/record_stopped.py", timeoutMs: 5_000 },
];

export const POST_TOOL_HOOKS: Array<{ script: string; timeoutMs: number }> = [
  { script: "tools/copilot_hooks/post_edit_validate.py", timeoutMs: 10_000 },
  { script: "tools/copilot_hooks/ai_response_analyzer.py", timeoutMs: 10_000 },
];

export const MEMORY_HOOK = {
  script: "tools/copilot_hooks/inject_memory_context.py",
  timeoutMs: 5_000,
};

export const SIDEQUEST_HOOK = {
  script: "tools/hooks/sidequest_nonblocking.py",
  timeoutMs: 8_000,
};

export const WIKI_SESSION_HOOK = {
  script: "tools/copilot_hooks/inject_wiki_context.py",
  args: ["--mode=session"],
  timeoutMs: 15_000,
};

export const WIKI_BLOCK_HOOK = {
  script: "tools/copilot_hooks/inject_wiki_context.py",
  args: ["--mode=block"],
  timeoutMs: 15_000,
};

export const STOP_HOOKS: Array<{ script: string; timeoutMs: number }> = [
  { script: "tools/hooks/sidequest_nonblocking.py", timeoutMs: 8_000 },
  { script: "tools/hooks/block_incomplete_stop.py", timeoutMs: 30_000 },
  { script: "tools/hooks/restore_stopped.py", timeoutMs: 60_000 },
];
