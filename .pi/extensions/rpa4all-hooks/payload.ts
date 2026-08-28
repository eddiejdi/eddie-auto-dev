/**
 * Map Pi tool_call / tool_result events to Claude-compatible hook payloads
 * consumed by tools/copilot_hooks/* and tools/hooks/* (stdin JSON).
 */

export type ClaudeHookPayload = {
  hook_event_name: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  cwd: string;
  session_id: string;
  /** Common aliases some scripts accept */
  toolName?: string;
  toolInput?: Record<string, unknown>;
  sessionId?: string;
};

const TOOL_NAME_MAP: Record<string, string> = {
  bash: "Bash",
  read: "Read",
  write: "Write",
  edit: "Edit",
  grep: "Grep",
  find: "Find",
  ls: "LS",
};

function mapToolName(piName: string): string {
  return TOOL_NAME_MAP[piName] ?? piName;
}

function mapToolInput(
  piName: string,
  input: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...input };

  // Path aliases used by variable/table/api hooks and pre_tool_guardrails
  const path =
    (typeof input.path === "string" && input.path) ||
    (typeof input.file_path === "string" && input.file_path) ||
    (typeof input.filePath === "string" && input.filePath) ||
    undefined;
  if (path) {
    out.path = path;
    out.file_path = path;
    out.filePath = path;
  }

  if (piName === "bash") {
    const command =
      (typeof input.command === "string" && input.command) ||
      (typeof input.cmd === "string" && input.cmd) ||
      "";
    out.command = command;
  }

  if (piName === "write" || piName === "edit") {
    if (typeof input.content === "string") {
      out.content = input.content;
      out.new_string = input.content;
      out.newString = input.content;
    }
    if (typeof input.newText === "string") {
      out.content = input.newText;
      out.new_string = input.newText;
      out.newString = input.newText;
    }
    if (typeof input.oldText === "string") {
      out.old_string = input.oldText;
      out.oldString = input.oldText;
    }
  }

  return out;
}

export function buildPreToolPayload(
  toolName: string,
  input: Record<string, unknown>,
  cwd: string,
  sessionId: string,
): ClaudeHookPayload {
  const mappedName = mapToolName(toolName);
  const toolInput = mapToolInput(toolName, input);
  return {
    hook_event_name: "PreToolUse",
    tool_name: mappedName,
    toolName: mappedName,
    tool_input: toolInput,
    toolInput,
    cwd,
    session_id: sessionId,
    sessionId,
  };
}

export function buildPostToolPayload(
  toolName: string,
  input: Record<string, unknown>,
  cwd: string,
  sessionId: string,
  isError: boolean,
  resultPreview?: string,
): ClaudeHookPayload {
  const mappedName = mapToolName(toolName);
  const toolInput = mapToolInput(toolName, input);
  if (resultPreview) {
    toolInput.result = resultPreview;
  }
  toolInput.is_error = isError;
  return {
    hook_event_name: "PostToolUse",
    tool_name: mappedName,
    toolName: mappedName,
    tool_input: toolInput,
    toolInput,
    cwd,
    session_id: sessionId,
    sessionId,
  };
}

export function buildStopPayload(cwd: string, sessionId: string): ClaudeHookPayload {
  return {
    hook_event_name: "Stop",
    tool_name: "Stop",
    tool_input: {},
    cwd,
    session_id: sessionId,
    sessionId,
  };
}
