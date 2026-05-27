import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { CliCommandSpec, CliParameterSpec } from "@/lib/api/schemas";
import { humanizeSettingKey } from "@/lib/cli-form";

function parseCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function valueAsString(value: unknown): string {
  if (value === undefined || value === null) {
    return "";
  }
  if (Array.isArray(value)) {
    return value.join(",");
  }
  return String(value);
}

function ParamField(props: {
  param: CliParameterSpec;
  value: unknown;
  onChange: (next: unknown) => void;
}) {
  const { param, value, onChange } = props;
  const [search, setSearch] = useState("");
  const label = humanizeSettingKey(param.name);

  if (param.type === "bool" || param.is_bool_flag) {
    return (
      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />
        {label}
      </label>
    );
  }

  if (param.type === "choice") {
    return (
      <label className="space-y-1 text-sm">
        {label}
        <select
          className="h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
          value={valueAsString(value)}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">Select…</option>
          {param.choices.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (param.type === "multi-choice") {
    const selected = Array.isArray(value) ? value.map(String) : [];
    const filtered = param.choices.filter((item) => item.toLowerCase().includes(search.toLowerCase()));
    return (
      <div className="space-y-2 rounded-md border border-border p-3">
        <p className="text-sm font-medium">{label}</p>
        <Input placeholder="Search choice..." value={search} onChange={(event) => setSearch(event.target.value)} />
        <div className="max-h-44 space-y-1 overflow-auto">
          {filtered.map((item) => (
            <label key={item} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={selected.includes(item)}
                onChange={(event) => {
                  if (event.target.checked) {
                    onChange([...selected, item]);
                    return;
                  }
                  onChange(selected.filter((v) => v !== item));
                }}
              />
              {item}
            </label>
          ))}
        </div>
      </div>
    );
  }

  if (param.repeatable || param.type === "multi-value") {
    return (
      <label className="space-y-1 text-sm">
        {label}
        <Input
          value={valueAsString(value)}
          placeholder="value1,value2"
          onChange={(event) => onChange(parseCsv(event.target.value))}
        />
      </label>
    );
  }

  return (
    <label className="space-y-1 text-sm">
      {label}
      <Input
        value={valueAsString(value)}
        type={param.type === "int" || param.type === "float" ? "number" : "text"}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

export function CliCommandForm(props: {
  command: CliCommandSpec;
  values: Record<string, unknown>;
  onChange: (name: string, value: unknown) => void;
  onReset: () => void;
}) {
  const { command, values, onChange, onReset } = props;
  const requiredMissing = useMemo(
    () =>
      command.parameters
        .filter((param: CliParameterSpec) => param.required)
        .filter((param: CliParameterSpec) => {
          const value = values[param.name];
          if (param.type === "bool") {
            return value !== true;
          }
          if (Array.isArray(value)) {
            return value.length === 0;
          }
          return value === undefined || value === null || String(value).trim() === "";
        }),
    [command.parameters, values],
  );

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        {command.parameters.map((param: CliParameterSpec) => (
          <ParamField key={`${command.name}-${param.name}`} param={param} value={values[param.name]} onChange={(next) => onChange(param.name, next)} />
        ))}
      </div>
      {requiredMissing.length > 0 ? (
        <p className="rounded-md border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800">
          Missing Required: {requiredMissing.map((item: CliParameterSpec) => humanizeSettingKey(item.name)).join(", ")}
        </p>
      ) : null}
      <Button type="button" variant="ghost" size="sm" onClick={onReset}>
        Reset Command Options
      </Button>
    </div>
  );
}
