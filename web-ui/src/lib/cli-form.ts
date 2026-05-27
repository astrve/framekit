import type { CliCommandSpec, CliParameterSpec } from "@/lib/api/schemas";

const HUMANIZE_OVERRIDES: Record<string, string> = {
  "seedbox.max_concurrent_uploads": "Seedbox Max Concurrent Uploads",
};

export function humanizeSettingKey(value: string): string {
  const override = HUMANIZE_OVERRIDES[value];
  if (override) {
    return override;
  }
  return value
    .replace(/[._-]+/g, " ")
    .trim()
    .split(/\s+/)
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(" ");
}

function quoteArg(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  if (/[\s"]/.test(trimmed)) {
    return `"${trimmed.replaceAll('"', '\\"')}"`;
  }
  return trimmed;
}

function firstAlias(param: CliParameterSpec): string {
  return param.aliases[0] ?? `--${param.name.replaceAll("_", "-")}`;
}

export function buildArgsFromState(command: CliCommandSpec, values: Record<string, unknown>): string {
  const args: string[] = [];
  const options = command.parameters.filter((item: CliParameterSpec) => item.kind === "option");
  const argumentsList = command.parameters.filter((item: CliParameterSpec) => item.kind === "argument");

  for (const arg of argumentsList) {
    const rawValue = values[arg.name];
    if (rawValue === undefined || rawValue === null || rawValue === "") {
      continue;
    }
    if (Array.isArray(rawValue)) {
      for (const value of rawValue) {
        const rendered = quoteArg(String(value));
        if (rendered) {
          args.push(rendered);
        }
      }
      continue;
    }
    const rendered = quoteArg(String(rawValue));
    if (rendered) {
      args.push(rendered);
    }
  }

  for (const option of options) {
    const rawValue = values[option.name];
    if (option.type === "bool" || option.is_bool_flag) {
      if (rawValue === true) {
        args.push(firstAlias(option));
      }
      continue;
    }
    if (rawValue === undefined || rawValue === null || rawValue === "") {
      continue;
    }
    if (Array.isArray(rawValue)) {
      const alias = firstAlias(option);
      for (const value of rawValue) {
        const rendered = quoteArg(String(value));
        if (rendered) {
          args.push(alias, rendered);
        }
      }
      continue;
    }
    const rendered = quoteArg(String(rawValue));
    if (!rendered) {
      continue;
    }
    args.push(firstAlias(option), rendered);
  }

  return args.join(" ").trim();
}

export function initValuesFromSpec(command: CliCommandSpec): Record<string, unknown> {
  const state: Record<string, unknown> = {};
  for (const param of command.parameters) {
    if (param.repeatable) {
      state[param.name] = Array.isArray(param.default) ? param.default : [];
      continue;
    }
    if (param.type === "bool" || param.is_bool_flag) {
      state[param.name] = Boolean(param.default);
      continue;
    }
    if (param.default !== undefined && param.default !== null) {
      state[param.name] = String(param.default);
    } else {
      state[param.name] = "";
    }
  }
  return state;
}
