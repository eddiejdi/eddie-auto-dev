/**
 * rpa4all-hooks — bridge Pi lifecycle events to existing Claude Python hooks.
 *
 * Source of truth remains tools/copilot_hooks/* and tools/hooks/*.
 * This extension only maps I/O and translates deny/ask/allow.
 */

import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import {
  MEMORY_HOOK,
  POST_TOOL_HOOKS,
  PRE_TOOL_HOOKS,
  STOP_HOOKS,
  runPythonHook,
  type HookDecision,
} from "./bridge.ts";
import {
  buildPostToolPayload,
  buildPreToolPayload,
  buildStopPayload,
} from "./payload.ts";

function sessionIdOf(ctx: ExtensionContext): string {
  try {
    return ctx.sessionManager.getSessionId() || "default";
  } catch {
    return "default";
  }
}

function notify(ctx: ExtensionContext, message: string, level: "info" | "warning" | "error" = "info") {
  try {
    if (ctx.hasUI) {
      ctx.ui.notify(message, level);
    } else if (level !== "info") {
      console.error(`[rpa4all-hooks] ${level}: ${message}`);
    }
  } catch {
    /* ignore UI errors in headless */
  }
}

async function confirmOrBlock(
  ctx: ExtensionContext,
  reason: string,
): Promise<{ block: true; reason: string } | undefined> {
  const title = "⚠️ Guardrail RPA4All — confirmação necessária";
  if (!ctx.hasUI) {
    return {
      block: true,
      reason: `${reason}\n(headless: ask→block)`,
    };
  }
  try {
    const ok = await ctx.ui.confirm(title, reason.slice(0, 1800));
    if (!ok) {
      return { block: true, reason: reason || "Bloqueado pelo usuário" };
    }
  } catch {
    return { block: true, reason: reason || "Confirmação indisponível" };
  }
  return undefined;
}

function decisionToBlock(
  d: HookDecision,
  script: string,
): { block: true; reason: string } | "ask" | undefined {
  if (!d.ok) {
    // fail-open with log
    console.error(`[rpa4all-hooks] fail-open ${script}: ${d.error || "unknown"}`);
    return undefined;
  }
  if (d.permissionDecision === "deny") {
    return {
      block: true,
      reason: d.permissionReason || `Negado por ${script}`,
    };
  }
  if (d.permissionDecision === "ask") {
    return "ask";
  }
  return undefined;
}

export default function (pi: ExtensionAPI) {
  pi.on("session_start", async (_event, ctx) => {
    notify(ctx, "rpa4all-hooks loaded (bridge → tools/hooks + copilot_hooks)", "info");
  });

  // Inject a SHORT MEMORY.md snippet into the system prompt (local 7–8B models choke on full MEMORY).
  pi.on("before_agent_start", async (event, ctx) => {
    const decision = await runPythonHook(MEMORY_HOOK.script, {}, {
      cwd: ctx.cwd,
      timeoutMs: MEMORY_HOOK.timeoutMs,
    });
    if (!decision.additionalContext) {
      return undefined;
    }
    const maxChars = Number(process.env.PI_MEMORY_MAX_CHARS || 1200);
    let mem = decision.additionalContext.trim();
    if (mem.length > maxChars) {
      mem = `${mem.slice(0, maxChars)}\n... (MEMORY truncada para Pi local; ver MEMORY.md completo no Claude)`;
    }
    return {
      systemPrompt: `${event.systemPrompt}\n\n# Project memory (truncated)\n${mem}`,
    };
  });

  pi.on("tool_call", async (event, ctx) => {
    const sid = sessionIdOf(ctx);
    const payload = buildPreToolPayload(
      event.toolName,
      (event.input ?? {}) as Record<string, unknown>,
      ctx.cwd,
      sid,
    );

    for (const hook of PRE_TOOL_HOOKS) {
      const decision = await runPythonHook(hook.script, payload, {
        cwd: ctx.cwd,
        timeoutMs: hook.timeoutMs,
      });

      const mapped = decisionToBlock(decision, hook.script);
      if (mapped === "ask") {
        const blocked = await confirmOrBlock(
          ctx,
          decision.permissionReason || `Confirmar ação (${hook.script})`,
        );
        if (blocked) return blocked;
        continue;
      }
      if (mapped) {
        notify(ctx, `⛔ ${mapped.reason.slice(0, 240)}`, "warning");
        return mapped;
      }
    }
    return undefined;
  });

  pi.on("tool_result", async (event, ctx) => {
    // Only run post hooks for write/edit-like tools (cheap + matches Claude intent)
    if (event.toolName !== "write" && event.toolName !== "edit" && event.toolName !== "bash") {
      return undefined;
    }
    const sid = sessionIdOf(ctx);
    let preview = "";
    try {
      const parts = (event.content || [])
        .map((c) => ("text" in c ? String((c as { text?: string }).text || "") : ""))
        .filter(Boolean);
      preview = parts.join("\n").slice(0, 4000);
    } catch {
      preview = "";
    }

    const payload = buildPostToolPayload(
      event.toolName,
      (event.input ?? {}) as Record<string, unknown>,
      ctx.cwd,
      sid,
      Boolean(event.isError),
      preview,
    );

    for (const hook of POST_TOOL_HOOKS) {
      const decision = await runPythonHook(hook.script, payload, {
        cwd: ctx.cwd,
        timeoutMs: hook.timeoutMs,
      });
      if (!decision.ok && decision.error) {
        console.error(`[rpa4all-hooks] post fail-open ${hook.script}: ${decision.error}`);
        continue;
      }
      if (decision.permissionDecision === "deny") {
        notify(
          ctx,
          `Post-hook: ${decision.permissionReason || hook.script}`,
          "warning",
        );
      } else if (decision.additionalContext) {
        notify(ctx, decision.additionalContext.slice(0, 300), "info");
      } else if (decision.permissionReason) {
        // warn-style messages from registries sometimes only set reason
        if (/warn|⚠️|📋|❌/i.test(decision.raw)) {
          notify(ctx, decision.permissionReason.slice(0, 300), "warning");
        }
      }
    }
    return undefined;
  });

  pi.on("agent_settled", async (_event, ctx) => {
    const sid = sessionIdOf(ctx);
    const payload = buildStopPayload(ctx.cwd, sid);

    for (const hook of STOP_HOOKS) {
      const decision = await runPythonHook(hook.script, payload, {
        cwd: ctx.cwd,
        timeoutMs: hook.timeoutMs,
      });
      if (!decision.ok) {
        console.error(`[rpa4all-hooks] stop fail-open ${hook.script}: ${decision.error}`);
        continue;
      }
      if (decision.stopDecision === "block") {
        notify(
          ctx,
          `Stop bloqueado (incompleto): ${(decision.stopReason || "").slice(0, 400)}\n` +
            "Nota: no Pi o loop forçado do Claude não é idêntico; complete stubs e continue a sessão.",
          "warning",
        );
      }
    }
  });
}
