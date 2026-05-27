import { describe, expect, it } from "vitest";

import { buildArgsFromState, humanizeSettingKey, initValuesFromSpec } from "@/lib/cli-form";
import type { CliCommandSpec } from "@/lib/api/schemas";

const MOCK_COMMAND: CliCommandSpec = {
  name: "seedbox",
  label: "Seedbox",
  help: "",
  is_group: false,
  destructive: true,
  supports_dry_run: false,
  group: "module",
  parameters: [
    {
      kind: "argument",
      name: "path_parts",
      label: "Path Parts",
      help: "",
      required: false,
      repeatable: true,
      nargs: -1,
      type: "multi-value",
      choices: [],
      default: [],
      aliases: [],
      secondary_aliases: [],
      flag_value: null,
      is_flag: false,
      is_bool_flag: false,
      metavar: "",
    },
    {
      kind: "option",
      name: "dry_run",
      label: "Dry Run",
      help: "",
      required: false,
      repeatable: false,
      nargs: 1,
      type: "bool",
      choices: [],
      default: false,
      aliases: ["--dry-run"],
      secondary_aliases: [],
      flag_value: null,
      is_flag: true,
      is_bool_flag: true,
      metavar: "",
    },
    {
      kind: "option",
      name: "seedbox",
      label: "Seedbox",
      help: "",
      required: false,
      repeatable: false,
      nargs: 1,
      type: "string",
      choices: [],
      default: null,
      aliases: ["--seedbox"],
      secondary_aliases: [],
      flag_value: null,
      is_flag: false,
      is_bool_flag: false,
      metavar: "",
    },
  ],
  subcommands: undefined,
};

describe("cli-form", () => {
  it("humanizeSettingKey applies override", () => {
    expect(humanizeSettingKey("seedbox.max_concurrent_uploads")).toBe("Seedbox Max Concurrent Uploads");
  });

  it("buildArgsFromState serializes flags and values", () => {
    const args = buildArgsFromState(MOCK_COMMAND, {
      path_parts: ["C:/Rel One", "C:/Rel Two"],
      dry_run: true,
      seedbox: "main",
    });
    expect(args).toContain('"C:/Rel One"');
    expect(args).toContain("--dry-run");
    expect(args).toContain("--seedbox main");
  });

  it("initValuesFromSpec returns defaults", () => {
    const values = initValuesFromSpec(MOCK_COMMAND);
    expect(values.dry_run).toBe(false);
    expect(values.path_parts).toEqual([]);
  });
});
