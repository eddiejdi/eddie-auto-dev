/**
 * rpa4all-hooks — opencode plugin que importa os hooks do eddie-auto-dev.
 *
 * Ponte opencode ↔ tools/copilot_hooks + tools/hooks (fonte de verdade),
 * no mesmo espírito do bridge do Pi (`.pi/extensions/rpa4all-hooks`).
 *
 * Dependências: nenhuma além de Node builtins (spawn/fs/path/url).
 *
 * Contrato opencode (v1 SDK):
 *   - Plugin = named export de função que recebe PluginInput e devolve Hooks.
 *   - `tool.execute.before` → input.tool + output.args (+ sessionID em input)
 *   - `tool.execute.after`  → input.tool + input.args
 *   - `chat.message`        → input.sessionID, output.message/output.parts
 *   - `event`               → { event } (session.idle/status/error…)
 *
 * Mapeamento (espelha hooks.json):
 *   - UserPromptSubmit → tools/copilot_hooks/internet_preference_context.py
 *                        + tools/copilot_hooks/inject_memory_context.py
 *   - PreToolUse       → pre_tool_guardrails + registries + record_stopped
 *   - PostToolUse      → post_edit_validate + ai_response_analyzer
 *   - Stop             → block_incomplete_stop + restore_stopped
 *   - Web tools        → web_agent_live_log (pre/delta) + open_agent_log_terminal
 *
 * Fail-open: qualquer erro interno nunca quebra a sessão. Decisões válidas
 * (`deny`/`ask`) viram exceção no plugin (bloqueia a tool); `block` em Stop
 * vira contexto na próxima mensagem do agente.
 */

/**
 * Plugin opencode que ponteia os hooks do eddie-auto-dev.
 * Exportado como named (padrão opencode: `export const NomePlugin`), sem default.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const MODULE_DIR = dirname(fileURLToPath(import.meta.url));

export type HookDecision = {
  ok: boolean;
  raw: string;
  parsed: Record<string, unknown> | null;
  permissionDecision?: "deny" | "ask" | "allow";
  permissionReason?: string;
  additionalContext?: string;
  stopDecision?: "block" | "continue";
  stopReason?: string;
  systemMessage?: string;
  error?: string;
};

const TOOL_NAME_MAP: Record<string, string> = {
  bash: "Bash",
  read: "Read",
  write: "Write",
  edit: "Edit",
  grep: "Grep",
  glob: "Glob",
  list: "LS",
  find: "Find",
  ls: "LS",
  cat: "Read",
};

const PRE_TOOL_HOOKS: Array<{ script: string; timeoutMs: number }> = [
  { script: "tools/hooks/record_stopped.py", timeoutMs: 5_000 },
];

const GUARDRAIL_HOOKS: Array<{ script: string; timeoutMs: number }> = [
  { script: "tools/copilot_hooks/pre_tool_guardrails.py", timeoutMs: 10_000 },
  { script: "tools/hooks/api_registry_validate.py", timeoutMs: 10_000 },
  { script: "tools/hooks/variable_registry_validate.py", timeoutMs: 10_000 },
  { script: "tools/hooks/table_registry_validate.py", timeoutMs: 10_000 },
  { script: "tools/hooks/cmdb_validate.py", timeoutMs: 10_000 },
];

const POST_TOOL_HOOKS: Array<{ script: string; timeoutMs: number }> = [
  { script: "tools/copilot_hooks/post_edit_validate.py", timeoutMs: 10_000 },
  { script: "tools/copilot_hooks/ai_response_analyzer.py", timeoutMs: 10_000 },
];

const STOP_HOOKS: Array<{ script: string; timeoutMs: number }> = [
  { script: "tools/hooks/block_incomplete_stop.py", timeoutMs: 30_000 },
  { script: "tools/hooks/restore_stopped.py", timeoutMs: 60_000 },
];

const MEMORY_HOOK = { script: "tools/copilot_hooks/inject_memory_context.py", timeoutMs: 5_000 };
const INTERNET_HOOK = { script: "tools/copilot_hooks/internet_preference_context.py", timeoutMs: 5_000 };
const WEB_PRE = { script: "tools/hooks/web_agent_live_log.py", mode: "--mode=pre", timeoutMs: 5_000 };
const WEB_TERMINAL = { script: "tools/hooks/open_agent_log_terminal.py", timeoutMs: 8_000 };

function findRepoRoot(startDir: string): string {
  let dir = resolve(startDir);
  for (let i = 0; i < 14; i++) {
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
  const fallback = "/workspace/eddie-auto-dev";
  if (existsSync(join(fallback, "tools", "copilot_hooks"))) return fallback;
  return startDir;
}

function mapToolName(name: string): string {
  const base = name.toLowerCase().split("__").pop() ?? name;
  return TOOL_NAME_MAP[base] ?? TOOL_NAME_MAP[name] ?? name;
}

function safeStr(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function mapToolInput(name: string, input: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = { ...input };
  const path = safeStr(input.path) || safeStr(input.file_path) || safeStr(input.filePath);
  const base = name.toLowerCase().split("__").pop() ?? name;
  if (path) {
    out.path = path;
    out.file_path = path;
    out.filePath = path;
  }
  if (base === "bash") {
    const command = safeStr(input.command) || safeStr(input.cmd) || "";
    out.command = command;
  }
  if (base === "write" || base === "edit") {
    if (typeof input.content === "string") {
      out.content = input.content;
      out.new_string = input.content;
      out.newString = input.content;
    }
    if (typeof input.newString === "string") {
      out.content = input.newString;
      out.new_string = input.newString;
    }
    if (typeof input.oldString === "string") {
      out.old_string = input.oldString;
    }
  }
  return out;
}

function envelope(
  eventName: string,
  toolName: string,
  toolInput: Record<string, unknown>,
  cwd: string,
  sessionId: string,
): Record<string, unknown> {
  return {
    hook_event_name: eventName,
    hookEventName: eventName,
    tool_name: toolName,
    toolName,
    tool_input: toolInput,
    toolInput,
    cwd,
    working_directory: cwd,
    workingDirectory: cwd,
    session_id: sessionId,
    sessionId,
  };
}

function parseHookOutput(stdout: string, stderr: string): HookDecision {
  const raw = stdout.trim();
  if (!raw) {
    return { ok: false, raw: "", parsed: null, permissionDecision: "allow" };
  }
  let parsed: Record<string, unknown> | null = null;
  try {
    const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
    parsed = JSON.parse(lines[lines.length - 1] ?? raw) as Record<string, unknown>;
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
  ).toLowerCase();
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
  const systemMessage = typeof parsed.systemMessage === "string" ? parsed.systemMessage : undefined;
  const stopDecisionRaw = String(nested.decision ?? parsed.decision ?? "").toLowerCase();
  const stopDecision = stopDecisionRaw === "block" ? "block"
    : stopDecisionRaw === "approve" || stopDecisionRaw === "continue" ? "continue" : undefined;
  const stopReason = typeof nested.reason === "string" ? nested.reason
    : typeof parsed.reason === "string" ? parsed.reason : undefined;

  return {
    ok: true,
    raw,
    parsed,
    permissionDecision:
      permissionDecision === "deny" ||
      permissionDecision === "ask" ||
      permissionDecision === "allow"
        ? (permissionDecision as "deny" | "ask" | "allow")
        : "allow",
    permissionReason: permissionReason || undefined,
    additionalContext,
    stopDecision,
    stopReason,
    systemMessage,
  };
}

function runPythonHook(
  scriptRel: string,
  args: string[],
  payload: Record<string, unknown>,
  options: { repoRoot: string; timeoutMs: number },
): Promise<Readonly<HookDecision>> {
  const scriptPath = existsSync(join(options.repoRoot, scriptRel))
    ? join(options.repoRoot, scriptRel)
    : join(MODULE_DIR, "..", scriptRel);
  const stdinPayload = JSON.stringify(payload);
  const env = {
    ...process.env,
    CLAUDE_PROJECT_DIR: options.repoRoot,
    RPA4ALL_OPENCODE: "true",
  };

  return new Promise((resolveDecision) => {
    const child = spawn("python3", [scriptPath, ...args], {
      cwd: options.repoRoot,
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
      resolveDecision({ ok: false, raw: stdout, parsed: null, error: `spawn error: ${err.message}` });
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

function isWebTool(name: string): boolean {
  const n = (name || "").toLowerCase();
  return (
    n.startsWith("web-agent__") ||
    n.startsWith("web_agent__") ||
    n.includes("web-agent") ||
    n.includes("web_run_task") ||
    n.includes("web_fill_form") ||
    n.includes("web_scrape") ||
    n.includes("web_apply") ||
    n.includes("web_analyze")
  );
}

function isEditLike(name: string): boolean {
  const n = name.toLowerCase();
  const b = n.split("__").pop() ?? n;
  const tokens = ["edit", "create", "write", "replace", "patch", "file", "string"];
  return tokens.some((t) => b.includes(t) || n.includes(t));
}

function isCommandLike(name: string): boolean {
  const n = name.toLowerCase();
  const b = n.split("__").pop() ?? n;
  const tokens = ["terminal", "execute", "command", "run", "shell", "bash", "cmd"];
  return tokens.some((t) => b.includes(t) || n.includes(t));
}

function extractPrompt(message: unknown): string {
  if (!message) return "";
  if (typeof message === "string") return message;
  if (Array.isArray(message)) {
    return message.map((p) => {
      if (typeof p === "string") return p;
      if (p?.type === "text") return safeStr(p.text);
      if (p?.text) return safeStr(p.text);
      return "";
    }).join("\n");
  }
  if (typeof message === "object") {
    const m = message as Record<string, unknown>;
    const texts: string[] = [];
    if (typeof m.text === "string" && m.text.trim()) texts.push(m.text);
    for (const key of ["content", "parts"]) {
      const v = m[key];
      if (Array.isArray(v)) texts.push(extractPrompt(v));
    }
    return texts.join("\n");
  }
  return "";
}

export const rpa4allHooksPlugin = async ({ directory, project }: { directory: string; project: { directory?: string } }) => {
  const cwd = directory || project?.directory || process.cwd();
  let repoRoot = findRepoRoot(cwd);
  if (!existsSync(join(repoRoot, "tools", "hooks"))) repoRoot = findRepoRoot(MODULE_DIR);

  const pendingContext = new Map<string, string[]>();
  const pendingPromptContext = new Map<string, string>();

  function queueContext(sessionID: string, text: string | undefined): void {
    if (!text) return;
    const arr = pendingContext.get(sessionID) ?? [];
    arr.push(text);
    pendingContext.set(sessionID, arr);
  }

  async function runSingle(
    scriptRel: string,
    args: string[],
    payload: Record<string, unknown>,
  ): Promise<Readonly<HookDecision>> {
    return runPythonHook(scriptRel, args, payload, {
      repoRoot,
      timeoutMs: 10_000,
    });
  }

  async function runGuardrailChain(payload: Record<string, unknown>) {
    let deny: Readonly<HookDecision> | undefined;
    let ask: Readonly<HookDecision> | undefined;
    const contexts: string[] = [];
    for (const hook of [...PRE_TOOL_HOOKS, ...GUARDRAIL_HOOKS]) {
      const decision = await runSingle(hook.script, [], payload);
      if (decision.error && decision.parsed === null) continue;
      if (decision.permissionDecision === "deny" && !deny) deny = decision;
      else if (decision.permissionDecision === "ask" && !ask) ask = decision;
      if (decision.additionalContext) contexts.push(decision.additionalContext);
    }
    return {
      permissionDecision: deny ? "deny" : ask ? "ask" : "allow",
      permissionReason: deny?.permissionReason ?? ask?.permissionReason,
      additionalContext: contexts.join("\n\n") || undefined,
    };
  }

  return {
    "chat.message": async (input: any, output: any) => {
      const sessionID = input?.sessionID ?? input?.sessionId ?? "default";
      const text =
        extractPrompt(output?.message?.parts ?? output?.parts) ||
        extractPrompt(output?.message?.message) ||
        extractPrompt(output?.content) ||
        extractPrompt(output);
      if (!text) return;
      const base = { cwd: repoRoot, session_id: sessionID, sessionId: sessionID };
      const inter = await runSingle(INTERNET_HOOK.script, [], {
        hook_event_name: "UserPromptSubmit",
        prompt: text,
        user_prompt: text,
        text,
        ...base,
      });
      if (inter.additionalContext) {
        pendingPromptContext.set(sessionID, inter.additionalContext);
      }
      const mem = await runSingle(MEMORY_HOOK.script, [], {
        hook_event_name: "UserPromptSubmit",
        prompt: text,
        user_prompt: text,
        text,
        ...base,
      });
      if (mem.additionalContext) {
        pendingPromptContext.set(
          sessionID,
          [pendingPromptContext.get(sessionID), mem.additionalContext].filter(Boolean).join("\n\n"),
        );
      }
    },

    "experimental.chat.system.transform": async (input: { sessionID?: string }, output: { system: string[] }) => {
      const sessionID = input?.sessionID ?? "default";
      const extra = pendingPromptContext.get(sessionID);
      const flushed = pendingContext.get(sessionID);
      if (extra) {
        output.system.push(`\n\n${extra}`);
        pendingPromptContext.delete(sessionID);
      }
      if (flushed && flushed.length > 0) {
        output.system.push(`\n\n${flushed.join("\n\n")}`);
        pendingContext.delete(sessionID);
      }
    },

    "tool.execute.before": async (input: { tool?: string; sessionID?: string }, output: { args?: Record<string, unknown> }) => {
      const sessionID = input?.sessionID ?? "default";
      const rawTool = input.tool ?? "";
      const toolName = mapToolName(rawTool);
      const args = (output?.args ?? {}) as Record<string, unknown>;
      const toolInput = mapToolInput(rawTool, args);
      const payload = envelope("PreToolUse", toolName, toolInput, repoRoot, sessionID);

      const isWeb = isWebTool(rawTool);
      if (isWeb) {
        await runSingle(WEB_PRE.script, [WEB_PRE.mode], payload).then(() => {});
        const t = await runSingle(WEB_TERMINAL.script, [], payload);
        if (t.additionalContext) queueContext(sessionID, t.additionalContext);
      }

      const decision = await runGuardrailChain(payload);

      if (decision.permissionDecision === "deny" || decision.permissionDecision === "ask") {
        const reason = decision.permissionReason || "Política do workspace";
        const suffix =
          decision.permissionDecision === "ask"
            ? "\n\nObtive confirmação explícita do usuário antes de prosseguir."
            : "";
        throw new Error(
          `[rpa4all-hooks] ${decision.permissionDecision.toUpperCase()}: ${reason}${suffix}`,
        );
      }
      queueContext(sessionID, decision.additionalContext);
    },

    "tool.execute.after": async (input: any, _output: any) => {
      const sessionID = input?.sessionID ?? "default";
      const rawTool = input.tool ?? "";
      const toolName = mapToolName(rawTool);
      const args = (input.args ?? {}) as Record<string, unknown>;
      if (!isEditLike(toolName) && !isCommandLike(toolName)) return;
      const toolInput = mapToolInput(rawTool, args);
      const payload = {
        ...envelope("PostToolUse", toolName, toolInput, repoRoot, sessionID),
        tool_input: { ...toolInput, ...(args as object) },
      };
      for (const hook of POST_TOOL_HOOKS) {
        const d = await runSingle(hook.script, [], payload);
        if (d.additionalContext) queueContext(sessionID, d.additionalContext);
        if (d.systemMessage) queueContext(sessionID, d.systemMessage);
      }
    },

    event: async ({ event }: any) => {
      if (!event) return;
      const sessionID =
        event.properties?.sessionID ??
        event.properties?.info?.sessionID ??
        event.properties?.info?.id ??
        "default";
      const type = event.type;

      if (type?.startsWith("session.")) {
        const status = typeof event.properties?.status === "string"
          ? event.properties.status
          : event.properties?.status?.type;
        if (status && !(status === "idle" || status === "error" || type === "session.end")) return;

        const stopPayload = envelope("Stop", "Stop", {}, repoRoot, String(sessionID));
        for (const hook of STOP_HOOKS) {
          const d = await runSingle(hook.script, [], stopPayload);
          if (!d.error && d.parsed) {
            if (d.stopDecision === "block" && d.stopReason) {
              queueContext(String(sessionID), `⚠️ Encerramento com tarefa incompleta: ${d.stopReason}`);
            }
            if (d.systemMessage) queueContext(String(sessionID), d.systemMessage);
          }
        }
      }
    },
  };
};