/**
 * Lightweight path protection for sensitive files.
 * Complements pre_tool_guardrails.py (does not replace it).
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const PROTECTED: Array<{ re: RegExp; reason: string }> = [
  { re: /(^|\/)\.env(\.|$|\/)/i, reason: ".env files are protected" },
  { re: /(^|\/)\.git(\/|$)/i, reason: ".git/ is protected" },
  { re: /node_modules\//i, reason: "node_modules/ is protected" },
  { re: /(secret|credentials|token|passwd|password)/i, reason: "secret-like path is protected" },
  { re: /(^|\/)\.bitwarden/i, reason: "bitwarden config is protected" },
  { re: /auth\.json$/i, reason: "auth.json is protected" },
];

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "write" && event.toolName !== "edit") {
      return undefined;
    }
    const path = String((event.input as { path?: string }).path || "");
    if (!path) return undefined;

    for (const rule of PROTECTED) {
      if (rule.re.test(path)) {
        if (ctx.hasUI) {
          ctx.ui.notify(`Blocked write to protected path: ${path}`, "warning");
        }
        return { block: true, reason: `${rule.reason}: ${path}` };
      }
    }
    return undefined;
  });
}
