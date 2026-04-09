import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "./ui/Button";
import Dropdown from "./ui/Dropdown";
import Toggle from "./ui/Toggle";
import InfoHint from "./ui/InfoHint";
import InputBox from "./ui/InputBox";
import { toast } from "react-hot-toast";
import { logger } from "../utils/logger";
import {
  fetchRoutingConfigs,
  bulkUpsertRoutingConfigs,
  deleteRoutingConfig,
  fetchTaskTypes,
  fetchRoutingMetadata,
} from "../handlers/modelRoutingHandlers";
import { updateAiMlSettings } from "../handlers/settingsHandlers";
import type { AvailableModel } from "../types/LlmProvider";
import type { ModelRoutingConfig, BulkUpsertItem, RoutingOption } from "../types/ModelRouting";

type RoutingRow = {
  id: string | null;
  provider_id: string;
  model_id: string;
  display_name: string;
  task_types: string[];
  prompt_sizes: string[];
  cost_tier: string;
  latency_tier: string;
  quality_tier: string;
  is_enabled: boolean;
  is_fallback: boolean;
};

type AutoRoutingSectionProps = {
  autoRoutingEnabled: boolean;
  routerProviderId: string | null;
  routerModelId: string | null;
  availableModels: AvailableModel[];
  canEdit: boolean;
  onSettingsChange: (settings: {
    auto_routing_enabled?: boolean;
    router_provider_id?: string | null;
    router_model_id?: string | null;
  }) => void;
};

export default function AutoRoutingSection({
  autoRoutingEnabled,
  routerProviderId,
  routerModelId,
  availableModels,
  canEdit,
  onSettingsChange,
}: AutoRoutingSectionProps) {
  const [enabled, setEnabled] = useState(autoRoutingEnabled);
  const [routerValue, setRouterValue] = useState<string>("");
  const [rows, setRows] = useState<RoutingRow[]>([]);
  const [allTaskTypes, setAllTaskTypes] = useState<string[]>([]);
  const [tierOptions, setTierOptions] = useState<RoutingOption[]>([]);
  const [latencyOptions, setLatencyOptions] = useState<RoutingOption[]>([]);
  const [promptSizeOptions, setPromptSizeOptions] = useState<RoutingOption[]>([]);
  const [newTaskType, setNewTaskType] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setEnabled(autoRoutingEnabled);
  }, [autoRoutingEnabled]);

  useEffect(() => {
    if (routerProviderId && routerModelId) {
      setRouterValue(`${routerProviderId}::${routerModelId}`);
    }
  }, [routerProviderId, routerModelId]);

  const modelOptions = useMemo(() => {
    return availableModels.map((m) => ({
      value: `${m.provider_id}::${m.model_id}`,
      label: m.display_name,
    }));
  }, [availableModels]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [configsRes, taskTypesRes, metadataRes] = await Promise.all([
        fetchRoutingConfigs(),
        fetchTaskTypes(),
        fetchRoutingMetadata(),
      ]);

      if (taskTypesRes) {
        setAllTaskTypes(taskTypesRes);
      }
      if (metadataRes) {
        setTierOptions(metadataRes.tier_options);
        setLatencyOptions(metadataRes.latency_options);
        setPromptSizeOptions(metadataRes.prompt_size_options);
      }

      const existingByKey = new Map<string, ModelRoutingConfig>();
      if (configsRes?.configs) {
        for (const cfg of configsRes.configs) {
          existingByKey.set(`${cfg.provider_id}::${cfg.model_id}`, cfg);
        }
      }

      const newRows: RoutingRow[] = availableModels.map((m) => {
        const key = `${m.provider_id}::${m.model_id}`;
        const existing = existingByKey.get(key);
        return {
          id: existing?.id ?? null,
          provider_id: m.provider_id,
          model_id: m.model_id,
          display_name: m.display_name,
          task_types: existing?.task_types ?? [],
          prompt_sizes: existing?.prompt_sizes ?? [],
          cost_tier: existing?.cost_tier ?? "medium",
          latency_tier: existing?.latency_tier ?? "medium",
          quality_tier: existing?.quality_tier ?? "medium",
          is_enabled: existing?.is_enabled ?? false,
          is_fallback: existing?.is_fallback ?? false,
        };
      });
      setRows(newRows);
    } catch (err) {
      logger.error("Error loading routing data", err);
    } finally {
      setLoading(false);
    }
  }, [availableModels]);

  useEffect(() => {
    if (availableModels.length > 0) {
      loadData();
    }
  }, [availableModels, loadData]);

  const updateRow = (index: number, field: keyof RoutingRow, value: unknown) => {
    setRows((prev) => {
      const next = [...prev];
      const row = { ...next[index] };

      if (field === "is_fallback" && value === true) {
        next.forEach((r, i) => {
          if (i !== index) next[i] = { ...r, is_fallback: false };
        });
      }

      (row as Record<string, unknown>)[field] = value;
      next[index] = row;
      return next;
    });
  };

  const toggleTaskType = (index: number, taskType: string) => {
    setRows((prev) => {
      const next = [...prev];
      const row = { ...next[index] };
      const types = [...row.task_types];
      const idx = types.indexOf(taskType);
      if (idx >= 0) {
        types.splice(idx, 1);
      } else {
        types.push(taskType);
      }
      row.task_types = types;
      next[index] = row;
      return next;
    });
  };

  const togglePromptSize = (index: number, size: string) => {
    setRows((prev) => {
      const next = [...prev];
      const row = { ...next[index] };
      const sizes = [...row.prompt_sizes];
      const idx = sizes.indexOf(size);
      if (idx >= 0) {
        sizes.splice(idx, 1);
      } else {
        sizes.push(size);
      }
      row.prompt_sizes = sizes;
      next[index] = row;
      return next;
    });
  };

  const handleAddTaskType = () => {
    const trimmed = newTaskType.trim().toLowerCase();
    if (trimmed && !allTaskTypes.includes(trimmed)) {
      setAllTaskTypes((prev) => [...prev, trimmed]);
    }
    setNewTaskType("");
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // 1. Save routing toggle + router model to settings
      const sep = routerValue.indexOf("::");
      const rProviderId = sep !== -1 ? routerValue.slice(0, sep) : null;
      const rModelId = sep !== -1 ? routerValue.slice(sep + 2) : null;

      await updateAiMlSettings({
        auto_routing_enabled: enabled,
        router_provider_id: rProviderId,
        router_model_id: rModelId,
      });

      onSettingsChange({
        auto_routing_enabled: enabled,
        router_provider_id: rProviderId,
        router_model_id: rModelId,
      });

      const configsToSave: BulkUpsertItem[] = rows
        .filter((r) => r.is_enabled || r.id)
        .map((r) => ({
          id: r.id,
          provider_id: r.provider_id,
          model_id: r.model_id,
          task_types: r.task_types,
          prompt_sizes: r.prompt_sizes,
          cost_tier: r.cost_tier,
          latency_tier: r.latency_tier,
          quality_tier: r.quality_tier,
          is_enabled: r.is_enabled,
          is_fallback: r.is_fallback,
        }));

      if (configsToSave.length > 0) {
        const result = await bulkUpsertRoutingConfigs(configsToSave);
        if (result?.configs) {
          const byKey = new Map<string, string>();
          for (const cfg of result.configs) {
            byKey.set(`${cfg.provider_id}::${cfg.model_id}`, cfg.id);
          }
          setRows((prev) =>
            prev.map((r) => ({
              ...r,
              id: byKey.get(`${r.provider_id}::${r.model_id}`) ?? r.id,
            }))
          );
        }
      }

      const toDelete = rows.filter((r) => !r.is_enabled && r.id);
      for (const r of toDelete) {
        if (r.id) await deleteRoutingConfig(r.id);
      }

      toast.success("Auto-routing configuration saved");
    } catch (err) {
      logger.error("Error saving routing config", err);
      toast.error("Failed to save routing configuration");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="border border-border-default rounded-lg p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">LLM Routing</h3>
          <p className="text-xs text-text-secondary">
            Automatically select the best model for each query based on model capabilities.
          </p>
        </div>
        {canEdit && (
          <Button variant="blue" size="sm" onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        )}
      </div>

      {/* Toggle */}
      <div className="flex items-center gap-3">
        <div className="flex flex-row items-center text-sm text-text-primary min-w-fit">
          <span>Enable LLM Routing</span>
          <InfoHint text="When enabled, a router LLM automatically picks the best model for each query based on the capabilities you configure below." />
        </div>
        <Toggle
          id="auto-routing-toggle"
          enabled={enabled}
          onChange={setEnabled}
          disabled={!canEdit}
        />
      </div>

      {enabled && (
        <div className="space-y-4 border-t border-border-subtle pt-3">
          {/* Router Model Selector */}
          <div className="space-y-1">
            <div className="flex items-center text-xs font-medium text-text-secondary">
              <span>Router Model</span>
              <InfoHint text="This model analyzes each query and picks the best model from the pool. Use a fast, cheap model (e.g., Haiku, GPT-4o-mini, Gemini Flash)." />
            </div>
            <Dropdown
              options={modelOptions}
              value={routerValue}
              onChange={(val) => setRouterValue(val || "")}
              placeholder="Select router model"
              disabled={!canEdit}
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-text-secondary">
              Available Task Types
            </label>
            <div className="flex flex-wrap gap-1 mb-1">
              {allTaskTypes.map((t) => (
                <span
                  key={t}
                  className="px-1.5 py-0.5 bg-surface-tertiary text-text-secondary border border-border-default rounded text-[11px]"
                >
                  {t}
                </span>
              ))}
            </div>
            <div className="flex gap-2 items-center">
              <InputBox
                value={newTaskType}
                placeholder="Add custom task type"
                type="text"
                variant="primary"
                onChange={setNewTaskType}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddTaskType();
                  }
                }}
              />
              <Button variant="ghost" size="sm" onClick={handleAddTaskType}>
                Add
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="text-sm text-text-secondary">Loading models...</div>
          ) : rows.length === 0 ? (
            <div className="text-sm text-text-secondary text-center py-4">
              No models available. Configure LLM providers above first.
            </div>
          ) : (
            <div className="overflow-x-auto border border-border-default rounded-lg">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-surface-secondary border-b border-border-default">
                    <th className="px-2 py-2 text-left font-medium text-text-secondary">Model</th>
                    <th className="px-2 py-2 text-left font-medium text-text-secondary">Task Types</th>
                    <th className="px-2 py-2 text-left font-medium text-text-secondary">Prompt Sizes</th>
                    <th className="px-2 py-2 text-left font-medium text-text-secondary">Cost</th>
                    <th className="px-2 py-2 text-left font-medium text-text-secondary">Latency</th>
                    <th className="px-2 py-2 text-left font-medium text-text-secondary">Quality</th>
                    <th className="px-2 py-2 text-center font-medium text-text-secondary">Enabled</th>
                    <th className="px-2 py-2 text-center font-medium text-text-secondary">Fallback</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, idx) => (
                    <tr
                      key={`${row.provider_id}::${row.model_id}`}
                      className={`border-b border-border-subtle ${
                        row.is_enabled ? "bg-surface-primary" : "bg-surface-secondary opacity-60"
                      }`}
                    >
                      <td className="px-2 py-2 font-medium text-text-primary whitespace-nowrap">
                        {row.display_name}
                      </td>

                      <td className="px-2 py-2">
                        <div className="flex flex-wrap gap-0.5">
                          {allTaskTypes.map((t) => {
                            const selected = row.task_types.includes(t);
                            return (
                              <button
                                key={t}
                                type="button"
                                onClick={() => canEdit && toggleTaskType(idx, t)}
                                disabled={!canEdit}
                                className={`px-1 py-0.5 rounded text-[10px] transition-colors ${
                                  selected
                                    ? "bg-accent-blue text-white"
                                    : "bg-surface-tertiary text-text-secondary hover:bg-surface-hover"
                                }`}
                              >
                                {t}
                              </button>
                            );
                          })}
                        </div>
                      </td>

                      <td className="px-2 py-2">
                        <div className="flex flex-wrap gap-0.5">
                          {promptSizeOptions.map((s) => {
                            const selected = row.prompt_sizes.includes(s.value);
                            return (
                              <button
                                key={s.value}
                                type="button"
                                onClick={() => canEdit && togglePromptSize(idx, s.value)}
                                disabled={!canEdit}
                                className={`px-1 py-0.5 rounded text-[10px] transition-colors ${
                                  selected
                                    ? "bg-accent-blue text-white"
                                    : "bg-surface-tertiary text-text-secondary hover:bg-surface-hover"
                                }`}
                              >
                                {s.label}
                              </button>
                            );
                          })}
                        </div>
                      </td>

                      <td className="px-2 py-2">
                        <select
                          value={row.cost_tier}
                          onChange={(e) => updateRow(idx, "cost_tier", e.target.value)}
                          disabled={!canEdit}
                          className="text-[11px] border border-border-default rounded px-1 py-0.5 bg-surface-primary text-text-primary"
                        >
                          {tierOptions.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </td>

                      <td className="px-2 py-2">
                        <select
                          value={row.latency_tier}
                          onChange={(e) => updateRow(idx, "latency_tier", e.target.value)}
                          disabled={!canEdit}
                          className="text-[11px] border border-border-default rounded px-1 py-0.5 bg-surface-primary text-text-primary"
                        >
                          {latencyOptions.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </td>

                      <td className="px-2 py-2">
                        <select
                          value={row.quality_tier}
                          onChange={(e) => updateRow(idx, "quality_tier", e.target.value)}
                          disabled={!canEdit}
                          className="text-[11px] border border-border-default rounded px-1 py-0.5 bg-surface-primary text-text-primary"
                        >
                          {tierOptions.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </td>

                      <td className="px-2 py-2 text-center">
                        <input
                          type="checkbox"
                          checked={row.is_enabled}
                          onChange={(e) => updateRow(idx, "is_enabled", e.target.checked)}
                          disabled={!canEdit}
                          className="w-3.5 h-3.5"
                        />
                      </td>

                      <td className="px-2 py-2 text-center">
                        <input
                          type="radio"
                          name="fallback-model"
                          checked={row.is_fallback}
                          onChange={() => updateRow(idx, "is_fallback", true)}
                          disabled={!canEdit}
                          className="w-3.5 h-3.5"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}