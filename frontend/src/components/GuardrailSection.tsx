import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "./ui/Button";
import Dropdown from "./ui/Dropdown";
import Toggle from "./ui/Toggle";
import InfoHint from "./ui/InfoHint";
import InputBox from "./ui/InputBox";
import { ConfigurableTable } from "./ui/Table";
import { toast } from "react-hot-toast";
import { logger } from "../utils/logger";
import { updateAiMlSettings } from "../handlers/settingsHandlers";
import type { AvailableModel } from "../types/LlmProvider";
import type { DenyWordRecord } from "../types/Settings";

type GuardrailSectionProps = {
  guardrailEnabled: boolean;
  guardrailProviderId: string | null;
  guardrailModelId: string | null;
  guardrailHistoryTurns: number;
  denyWords: string;
  availableModels: AvailableModel[];
  canEdit: boolean;
  onSettingsChange: (settings: {
    guardrail_enabled?: boolean;
    guardrail_provider_id?: string | null;
    guardrail_model_id?: string | null;
    guardrail_history_turns?: number;
    deny_words?: string;
  }) => void;
};

const stringToWordsArray = (str: string): DenyWordRecord[] => {
  if (!str.trim()) return [];
  return str
    .split(",")
    .map((word) => word.trim())
    .filter((word) => word.length > 0)
    .map((word, index) => ({
      id: `word-${Date.now()}-${index}`,
      word,
    }));
};

const wordsArrayToString = (arr: DenyWordRecord[]): string =>
  arr.map((item) => item.word).join(",");

export default function GuardrailSection({
  guardrailEnabled,
  guardrailProviderId,
  guardrailModelId,
  guardrailHistoryTurns,
  denyWords: initialDenyWords,
  availableModels,
  canEdit,
  onSettingsChange,
}: GuardrailSectionProps) {
  const [enabled, setEnabled] = useState(guardrailEnabled);
  const [modelValue, setModelValue] = useState<string>("");
  const [historyTurns, setHistoryTurns] = useState<string>(
    String(guardrailHistoryTurns ?? 3)
  );
  const [denyWordsArray, setDenyWordsArray] = useState<DenyWordRecord[]>(
    stringToWordsArray(initialDenyWords || "")
  );
  const [denyWordsInput, setDenyWordsInput] = useState("");
  const [showDenyWordsTable, setShowDenyWordsTable] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setEnabled(guardrailEnabled);
  }, [guardrailEnabled]);

  useEffect(() => {
    if (guardrailProviderId && guardrailModelId) {
      setModelValue(`${guardrailProviderId}::${guardrailModelId}`);
    } else {
      setModelValue("");
    }
  }, [guardrailProviderId, guardrailModelId]);

  useEffect(() => {
    setHistoryTurns(String(guardrailHistoryTurns ?? 3));
  }, [guardrailHistoryTurns]);

  useEffect(() => {
    setDenyWordsArray(stringToWordsArray(initialDenyWords || ""));
  }, [initialDenyWords]);

  const modelOptions = useMemo(
    () =>
      availableModels.map((m) => ({
        value: `${m.provider_id}::${m.model_id}`,
        label: m.display_name,
      })),
    [availableModels]
  );

  const handleAddDenyWords = useCallback(() => {
    if (!denyWordsInput.trim()) return;
    const newWords = denyWordsInput
      .split(",")
      .map((w) => w.trim())
      .filter((w) => w.length > 0);
    const existing = denyWordsArray.map((item) => item.word.toLowerCase());
    const toAdd = newWords.filter((w) => !existing.includes(w.toLowerCase()));
    if (toAdd.length > 0) {
      setDenyWordsArray((prev) => [
        ...prev,
        ...toAdd.map((word, idx) => ({
          id: `word-${Date.now()}-${idx}`,
          word,
        })),
      ]);
    }
    setDenyWordsInput("");
  }, [denyWordsInput, denyWordsArray]);

  const handleRemoveDenyWord = useCallback((wordId: string) => {
    setDenyWordsArray((prev) => prev.filter((item) => item.id !== wordId));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const sep = modelValue.indexOf("::");
      const providerId = sep !== -1 ? modelValue.slice(0, sep) : null;
      const modelId = sep !== -1 ? modelValue.slice(sep + 2) : null;

      if (enabled && (!providerId || !modelId)) {
        toast.error("Pick a guardrail model before enabling");
        setSaving(false);
        return;
      }

      const turnsNum = Math.max(0, Math.min(10, parseInt(historyTurns || "3", 10) || 3));
      const denyWordsCsv = wordsArrayToString(denyWordsArray);

      await updateAiMlSettings({
        guardrail_enabled: enabled,
        guardrail_provider_id: providerId,
        guardrail_model_id: modelId,
        guardrail_history_turns: turnsNum,
        deny_words: denyWordsCsv,
      });

      onSettingsChange({
        guardrail_enabled: enabled,
        guardrail_provider_id: providerId,
        guardrail_model_id: modelId,
        guardrail_history_turns: turnsNum,
        deny_words: denyWordsCsv,
      });

      toast.success("Guardrails saved");
    } catch (err) {
      logger.error("Error saving guardrails", err);
      toast.error("Failed to save guardrails");
    } finally {
      setSaving(false);
    }
  };

  const denyWordsCount = denyWordsArray.length;

  return (
    <section className="border border-border-default rounded-lg p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">Guardrails</h3>
          <p className="text-xs text-text-secondary">
            A deny list blocks exact words via regex. The guardrail uses a small LLM to catch
            indirect off-topic queries the regex can't, using the deny list as additional context.
          </p>
        </div>
        {canEdit && (
          <Button variant="blue" size="sm" onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        )}
      </div>

      {/* Deny list */}
      <div className="space-y-3 border-t border-border-subtle pt-3">
        <div className="flex flex-col sm:flex-row items-start sm:items-center sm:justify-between gap-2">
          <span className="flex flex-row justify-between text-sm md:text-medium text-text-primary w-full">
            <div className="flex flex-row items-center gap-1">
              <span>Deny List Words</span>
              <InfoHint text="Any word on this list is blocked from user prompts via case-insensitive regex. Also passed to the guardrail model as off-topic context." />
            </div>
            <span className="text-xs text-text-secondary font-normal">
              <button
                onClick={() => setShowDenyWordsTable(!showDenyWordsTable)}
                className="ml-2 text-accent-blue hover:text-accent-blue underline cursor-pointer"
              >
                {showDenyWordsTable ? "Hide All" : `View All (${denyWordsCount})`}
              </button>
            </span>
          </span>
        </div>

        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
          <InputBox
            value={denyWordsInput}
            onChange={setDenyWordsInput}
            placeholder="Add words to deny (comma-separated)"
            variant="primary"
            className="w-full rounded-[5px] border-border-strong border-b-1"
            disabled={!canEdit}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleAddDenyWords();
              }
            }}
          />
          <Button
            variant="secondary"
            size="sm"
            onClick={handleAddDenyWords}
            disabled={!canEdit}
            className="w-full sm:w-auto"
          >
            Add word
          </Button>
        </div>

        {showDenyWordsTable && (
          <div className="grid grid-cols-1 xl:grid-cols-1 gap-4 xl:gap-6 my-2">
            <div className="overflow-x-auto bg-surface-primary rounded-lg border border-border-strong">
              {denyWordsArray.length === 0 ? (
                <div className="p-4 text-center text-text-secondary text-sm">
                  No deny words configured. Add words above to get started.
                </div>
              ) : (
                <div className="max-h-60 overflow-y-auto border-t border-border-default">
                  <ConfigurableTable
                    data={denyWordsArray}
                    keyExtractor={(row) => row.id}
                    columns={[
                      {
                        header: "Deny Word",
                        accessor: "word",
                        headerClassName:
                          "font-medium text-text-secondary text-xs md:text-sm sticky top-0 bg-surface-secondary z-10 border-b border-border-default",
                        className: "text-xs md:text-sm text-text-primary py-3",
                        searchable: true,
                      },
                      ...(canEdit
                        ? [
                            {
                              header: "Action",
                              headerClassName:
                                "font-medium text-text-secondary text-xs md:text-sm sticky top-0 bg-surface-secondary z-10 border-b border-border-default w-20",
                              render: (denyWord: DenyWordRecord) => (
                                <div className="flex flex-row gap-1 sm:gap-2">
                                  <Button
                                    variant="default"
                                    size="sm"
                                    className="hover:text-danger-text"
                                    onClick={() => handleRemoveDenyWord(denyWord.id)}
                                  >
                                    ✕
                                  </Button>
                                </div>
                              ),
                              searchable: false,
                            },
                          ]
                        : []),
                    ]}
                    headerRowClassName="bg-surface-secondary sticky top-0 z-10"
                    rowClassName="bg-surface-primary border-t border-border-default hover:bg-surface-secondary"
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Guardrail (LLM) */}
      <div className="flex items-center gap-3 border-t border-border-subtle pt-3">
        <div className="flex flex-row items-center text-sm text-text-primary min-w-fit">
          <span>Enable Guardrail</span>
          <InfoHint text="When enabled, every user message that passes the deny list is classified by the guardrail model. Messages that match a deny topic are blocked before reaching the main bot." />
        </div>
        <Toggle
          id="guardrail-toggle"
          enabled={enabled}
          onChange={setEnabled}
          disabled={!canEdit}
        />
      </div>

      {enabled && (
        <div className="space-y-4">
          <div className="space-y-1">
            <div className="flex items-center text-xs font-medium text-text-secondary">
              <span>Guardrail Model</span>
              <InfoHint text="Pick a small, fast, cheap model with good world knowledge (e.g., GPT-4o-mini, Claude Haiku, Gemini Flash). This model classifies every message, so latency and cost matter." />
            </div>
            <Dropdown
              options={modelOptions}
              value={modelValue}
              onChange={(val) => setModelValue(val || "")}
              placeholder="Select guardrail model"
              disabled={!canEdit}
            />
            {modelOptions.length === 0 && (
              <p className="text-xs text-warning-text">
                No providers configured. Add an LLM provider above first.
              </p>
            )}
          </div>

          <div className="space-y-1">
            <div className="flex items-center text-xs font-medium text-text-secondary">
              <span>Conversation History Turns</span>
              <InfoHint text="How many prior messages to include as context when classifying. Helps resolve follow-ups like 'tell me more about that'. Higher values cost more tokens per call." />
            </div>
            <InputBox
              value={historyTurns}
              onChange={setHistoryTurns}
              variant="primary"
              type="number"
              className="w-24 text-sm"
              min={0}
              max={10}
              step={1}
              disabled={!canEdit}
            />
          </div>
        </div>
      )}
    </section>
  );
}