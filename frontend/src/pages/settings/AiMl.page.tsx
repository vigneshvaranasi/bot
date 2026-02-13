import { useCallback, useEffect, useMemo, useState } from "react";
import SettingsHeader from "../../components/settings/SettingsHeader";
import Dropdown from "../../components/ui/Dropdown";
import InputBox from "../../components/ui/InputBox";
import Toggle from "../../components/ui/Toggle";
import { Button } from "../../components/ui/Button";
import { ConfigurableTable } from "../../components/ui/Table";
import InfoHint from "../../components/ui/InfoHint";
import LlmProviderControl from "../../components/LlmProviderControl";
import { fetchAiMlSettings, updateAiMlSettings } from "../../handlers/settingsHandlers";
import {
  fetchLlmProviders,
  createLlmProvider,
  updateLlmProvider,
  deleteLlmProvider,
  testLlmProviderConnection,
  fetchAvailableModels,
  discoverProviderModels,
  discoverModelsFromConfig,
} from "../../handlers/llmProviderHandlers";
import type { DenyWordRecord, Model, AiMlSettings } from "../../types/Settings";
import type {
  LlmProvider,
  LlmProviderCreate,
  LlmProviderUpdate,
  AvailableModel,
} from "../../types/LlmProvider";
import { toast } from "react-hot-toast";
import { logger } from "../../utils/logger";
import { SkeletonAiMlSettings } from "../../components/ui/Skeleton";
import { usePermissions } from "../../hooks/usePermissions";
import { PERMISSIONS } from "../../types/Permission";

const AiMlConfigPage = () => {
  const { hasPermission } = usePermissions();
  const canEditAiMl = hasPermission(PERMISSIONS.AIML_EDIT);
  const canCreateProvider = hasPermission(PERMISSIONS.LLM_PROVIDER_CREATE);
  const canEditProvider = hasPermission(PERMISSIONS.LLM_PROVIDER_EDIT);
  const canDeleteProvider = hasPermission(PERMISSIONS.LLM_PROVIDER_DELETE);
  const canTestProvider = hasPermission(PERMISSIONS.LLM_PROVIDER_TEST);

  const [model, setModel] = useState<Model>("gemma3:4b");
  const [providerId, setProviderId] = useState<string | null>(null);
  const [temperature, setTemperature] = useState("0.2");
  const [langfuseEnabled, setLangfuseEnabled] = useState<boolean | undefined>(undefined);
  const [allowUserModelSelection, setAllowUserModelSelection] = useState<boolean | undefined>(undefined);

  const [denyWordsArray, setDenyWordsArray] = useState<DenyWordRecord[]>([]);
  const [denyWords, setDenyWords] = useState("");
  const [showDenyWordsTable, setShowDenyWordsTable] = useState(false);

  // LLM Providers state
  const [providers, setProviders] = useState<LlmProvider[]>([]);
  const [availableModels, setAvailableModels] = useState<AvailableModel[]>([]);
  const [newProviderOpen, setNewProviderOpen] = useState(false);
  const [loadingProviders, setLoadingProviders] = useState(false);

  const [loading, setLoading] = useState(false);
  const [savingModel, setSavingModel] = useState(false);
  const [savingSafety, setSavingSafety] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stringToWordsArray = useCallback((str: string): DenyWordRecord[] => {
    if (!str.trim()) return [];
    return str
      .split(",")
      .map((word) => word.trim())
      .filter((word) => word.length > 0)
      .map((word, index) => ({
        id: `word-${Date.now()}-${index}`,
        word: word,
      }));
  }, []);

  const wordsArrayToString = useCallback((wordsArray: DenyWordRecord[]): string => {
    return wordsArray.map((item) => item.word).join(",");
  }, []);

  // Load providers and available models
  const loadProviders = useCallback(async () => {
    try {
      setLoadingProviders(true);
      const [providersResponse, modelsResponse] = await Promise.all([
        fetchLlmProviders(),
        fetchAvailableModels(),
      ]);

      if (providersResponse?.providers) {
        setProviders(providersResponse.providers);
      }
      if (modelsResponse?.models) {
        setAvailableModels(modelsResponse.models);
      }
    } catch (err) {
      logger.error("Error fetching LLM providers", err);
    } finally {
      setLoadingProviders(false);
    }
  }, []);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        setLoading(true);
        const response = await fetchAiMlSettings();
        if (response?.settings) {
          const settings = response.settings;
          const denyWordsFromBackend = settings.deny_words || "";
          setDenyWordsArray(stringToWordsArray(denyWordsFromBackend));
          setModel(settings.model);
          setProviderId(settings.provider_id ?? null);
          setTemperature(settings.temperature);
          setLangfuseEnabled(settings.langfuse_enabled ?? true);
          setAllowUserModelSelection(settings.allow_user_model_selection ?? false);
        }
      } catch (err) {
        logger.error("Error fetching AI/ML settings", err);
        setError("Unable to load AI/ML settings");
      } finally {
        setLoading(false);
      }
    };
    loadSettings();
    loadProviders();
  }, [stringToWordsArray, loadProviders]);

  // Generate model options from available models (from providers) plus fallback static options
  // Uses composite "provider_id::model_id" values to distinguish same-named models across providers
  const modelOptions = useMemo(() => {
    if (availableModels.length > 0) {
      return availableModels.map((m) => ({
        value: `${m.provider_id}::${m.model_id}`,
        label: m.display_name,
      }));
    }
    // Fallback to static options if no providers configured
    return [
      { value: "gpt-oss:20b", label: "GPT-OSS: 20B (Default)" },
      { value: "gemma3:1b", label: "Gemma3: 1B" },
      { value: "gemma3:4b", label: "Gemma3: 4B" },
    ];
  }, [availableModels]);

  // The composite value currently selected in the dropdown
  const selectedCompositeValue = useMemo(() => {
    if (providerId && availableModels.length > 0) {
      return `${providerId}::${model}`;
    }
    // Fallback: find model by model_id alone (legacy or no provider_id saved)
    const match = availableModels.find((m) => m.model_id === model);
    return match ? `${match.provider_id}::${match.model_id}` : model;
  }, [providerId, model, availableModels]);

  // Provider handlers
  const handleSaveProvider = async (
    payload: LlmProviderCreate | (LlmProviderUpdate & { id: string })
  ) => {
    try {
      if ("id" in payload && payload.id) {
        // Update existing provider
        const { id, ...updateData } = payload;
        const result = await updateLlmProvider(id, updateData);
        if (result) {
          toast.success("Provider updated successfully");
          await loadProviders();
        } else {
          toast.error("Failed to update provider");
        }
      } else {
        // Create new provider
        const result = await createLlmProvider(payload as LlmProviderCreate);
        if (result) {
          toast.success("Provider created successfully");
          setNewProviderOpen(false);
          await loadProviders();
        } else {
          toast.error("Failed to create provider");
        }
      }
    } catch (err) {
      logger.error("Error saving provider", err);
      toast.error("Failed to save provider");
    }
  };

  const handleDeleteProvider = async (id?: string) => {
    if (!id) return;
    try {
      const success = await deleteLlmProvider(id);
      if (success) {
        toast.success("Provider deleted successfully");
        await loadProviders();
      } else {
        toast.error("Failed to delete provider");
      }
    } catch (err) {
      logger.error("Error deleting provider", err);
      toast.error("Failed to delete provider");
    }
  };

  const handleTestProvider = async (id: string) => {
    try {
      const result = await testLlmProviderConnection(id);
      if (result) {
        if (result.success) {
          toast.success(`Connection successful (${result.response_time_ms?.toFixed(0)}ms)`);
        } else {
          toast.error(`Connection failed: ${result.message}`);
        }
        // Refresh providers to update health status
        await loadProviders();
      }
      return result;
    } catch (err) {
      logger.error("Error testing provider", err);
      toast.error("Failed to test connection");
      return null;
    }
  };

  const handleDiscoverModels = async (id: string) => {
    try {
      const result = await discoverProviderModels(id);
      if (result) {
        if (result.success) {
          toast.success(`Discovered ${result.models.length} models`);
        } else if (result.models.length === 0) {
          toast.error(result.message || "No models found");
        }
      }
      return result;
    } catch (err) {
      logger.error("Error discovering models", err);
      toast.error("Failed to discover models");
      return null;
    }
  };

  const handleDiscoverModelsFromConfig = async (config: LlmProviderCreate) => {
    try {
      const result = await discoverModelsFromConfig(config);
      if (result) {
        if (result.success) {
          toast.success(`Discovered ${result.models.length} models`);
        } else if (result.models.length === 0) {
          toast.error(result.message || "No models found");
        }
      }
      return result;
    } catch (err) {
      logger.error("Error discovering models from config", err);
      toast.error("Failed to discover models");
      return null;
    }
  };

  const handleAddDenyWords = () => {
    if (!denyWords.trim()) return;
    const newWords = denyWords
      .split(",")
      .map((word) => word.trim())
      .filter((word) => word.length > 0);

    const existingWords = denyWordsArray.map((item) => item.word.toLowerCase());
    const wordsToAdd = newWords.filter((word) => !existingWords.includes(word.toLowerCase()));

    if (wordsToAdd.length > 0) {
      const newWordRecords: DenyWordRecord[] = wordsToAdd.map((word, index) => ({
        id: `word-${Date.now()}-${index}`,
        word: word,
      }));

      const updatedDenyWordsArray = [...denyWordsArray, ...newWordRecords];
      setDenyWordsArray(updatedDenyWordsArray);
    }

    setDenyWords("");
  };

  const handleRemoveDenyWord = (wordId: string) => {
    const updatedDenyWordsArray = denyWordsArray.filter((item) => item.id !== wordId);
    setDenyWordsArray(updatedDenyWordsArray);
  };

  const handleSaveModel = async () => {
    try {
      setSavingModel(true);
      setError(null);
      const modelPayload: Partial<AiMlSettings> = {
        model,
        temperature,
        provider_id: providerId,
        allow_user_model_selection: allowUserModelSelection ?? false,
      };
      await updateAiMlSettings(modelPayload);
      toast.success("Model configuration saved");
    } catch (err) {
      logger.error("Error saving model settings", err);
      setError("Failed to save model configuration");
      toast.error("Failed to save model configuration");
    } finally {
      setSavingModel(false);
    }
  };

  const handleSaveSafety = async () => {
    try {
      setSavingSafety(true);
      setError(null);
      const safetyPayload: Partial<AiMlSettings> = {
        deny_words: wordsArrayToString(denyWordsArray),
        langfuse_enabled: langfuseEnabled ?? true,
      };
      await updateAiMlSettings(safetyPayload);
      toast.success("Safety settings saved");
    } catch (err) {
      logger.error("Error saving safety settings", err);
      setError("Failed to save safety settings");
      toast.error("Failed to save safety settings");
    } finally {
      setSavingSafety(false);
    }
  };

  const denyWordsCount = useMemo(() => denyWordsArray.length, [denyWordsArray]);

  if (loading) {
    return (
      <div className="space-y-8">
        <SettingsHeader
          title="AI / ML Configuration"
          description="Configure model selection, generation controls, safety filters, and observability."
        />
        <SkeletonAiMlSettings />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <SettingsHeader
        title="AI / ML Configuration"
        description="Configure model selection, generation controls, safety filters, and observability."
      />

      {error ? (
        <div className="p-3 bg-red-50 text-sm text-red-700 border border-red-200 rounded">
          {error}
        </div>
      ) : null}

      {/* LLM Providers Section */}
      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">LLM Providers</h3>
            <p className="text-xs text-gray-600">
              Configure API keys and endpoints for AI model providers.
            </p>
          </div>
          {canCreateProvider && (
            <Button
              variant="blue"
              size="sm"
              onClick={() => setNewProviderOpen(true)}
              disabled={newProviderOpen}
            >
              Add Provider
            </Button>
          )}
        </div>

        {loadingProviders ? (
          <div className="text-sm text-gray-500">Loading providers...</div>
        ) : (
          <div className="space-y-4">
            {/* New Provider Form */}
            {newProviderOpen && canCreateProvider && (
              <div className="border-2 border-dashed border-blue-300 rounded-lg p-2">
                <LlmProviderControl
                  isNew={true}
                  onSave={handleSaveProvider}
                  onDelete={() => setNewProviderOpen(false)}
                  onDiscoverModelsFromConfig={handleDiscoverModelsFromConfig}
                  canEdit={true}
                  canDelete={true}
                  canTest={canTestProvider}
                />
              </div>
            )}

            {/* Existing Providers */}
            {providers.length === 0 && !newProviderOpen ? (
              <div className="text-sm text-gray-500 text-center py-4">
                No providers configured.{canCreateProvider ? " Click \"Add Provider\" to get started." : ""}
              </div>
            ) : (
              providers.map((provider) => (
                <LlmProviderControl
                  key={provider.id}
                  provider={provider}
                  onSave={canEditProvider ? handleSaveProvider : undefined}
                  onDelete={canDeleteProvider ? handleDeleteProvider : undefined}
                  onTest={canTestProvider ? handleTestProvider : undefined}
                  onDiscoverModels={canEditProvider ? handleDiscoverModels : undefined}
                  onDiscoverModelsFromConfig={canEditProvider ? handleDiscoverModelsFromConfig : undefined}
                  canEdit={canEditProvider}
                  canDelete={canDeleteProvider}
                  canTest={canTestProvider}
                />
              ))
            )}
          </div>
        )}
      </section>

      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Model & Generation</h3>
            <p className="text-xs text-gray-600">Select model and configure generation parameters.</p>
          </div>
          {canEditAiMl && (
            <Button variant="blue" size="sm" onClick={handleSaveModel} disabled={savingModel}>
              {savingModel ? "Saving…" : "Save"}
            </Button>
          )}
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="space-y-3">
            <div className="flex flex-row items-center text-sm md:text-medium text-black min-w-fit">
              <span>Select Model</span>
              <InfoHint text="Available models come from the providers you've configured above. To see more options, add another provider." />
            </div>
            <Dropdown
              options={modelOptions}
              value={selectedCompositeValue}
              onChange={(val) => {
                const str = val as string;
                const sep = str.indexOf("::");
                if (sep !== -1) {
                  setProviderId(str.slice(0, sep));
                  setModel(str.slice(sep + 2));
                } else {
                  // Fallback static options (no provider)
                  setProviderId(null);
                  setModel(str as Model);
                }
              }}
              placeholder="Select model"
              disabled={!canEditAiMl}
            />
            {availableModels.length === 0 && (
              <p className="text-xs text-amber-600">
                No providers configured. Using default models.
              </p>
            )}
          </div>
          <div className="shrink-0 space-y-1">
            <div className="flex items-center text-xs font-medium text-gray-700">
              <label>Temperature</label>
              <InfoHint text="Controls how creative the AI responses are. Lower values (closer to 0) give more focused, consistent answers. Higher values (closer to 1) give more varied responses." />
            </div>
            <InputBox
              value={temperature}
              onChange={(val) => setTemperature(val)}
              variant="primary"
              type="number"
              className="outline-none rounded-md px-2 py-1.5 text-sm text-gray-900 w-24"
              step={0.1}
              min={0}
              max={1}
              disabled={!canEditAiMl}
            />
          </div>
        </div>

        <div className="mt-2 flex items-center gap-3">
          <div className="flex flex-row items-center text-sm md:text-medium text-gray-900 min-w-fit">
            <span>Let Users Choose Model</span>
            <InfoHint text="When enabled, users can pick a different model in the chat. When disabled, all chats use the model selected above." />
          </div>
          {allowUserModelSelection !== undefined ? (
            <Toggle id="user-model-selection-toggle" enabled={allowUserModelSelection} onChange={setAllowUserModelSelection} disabled={!canEditAiMl} />
          ) : (
            <div className="w-11 h-6 bg-gray-200 rounded-full animate-pulse" />
          )}
        </div>
      </section>

      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Safety & Observability</h3>
            <p className="text-xs text-gray-600"> Configure safety filters and tracing options.</p>
          </div>
          {canEditAiMl && (
            <Button variant="blue" size="sm" onClick={handleSaveSafety} disabled={savingSafety}>
              {savingSafety ? "Saving…" : "Save"}
            </Button>
          )}
        </div>

        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row items-start sm:items-center sm:justify-between gap-2">
            <span className="flex flex-row justify-between text-sm md:text-medium text-black w-full">
              <div className="flex flex-row items-center gap-1">
                <span>Deny List Words</span>
                <InfoHint text="Any word on this list will be automatically blocked from both user prompts and AI responses." />
              </div>
              <span className="text-xs text-gray-600 font-normal">
                <button
                  onClick={() => setShowDenyWordsTable(!showDenyWordsTable)}
                  className="ml-2 text-blue-600 hover:text-blue-800 underline cursor-pointer"
                >
                  {showDenyWordsTable ? "Hide All" : `View All (${denyWordsCount})`}
                </button>
              </span>
            </span>
          </div>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
            <InputBox
              value={denyWords}
              onChange={setDenyWords}
              placeholder="Add words to deny"
              variant="primary"
              className="w-full rounded-[5px] border-gray-400 border-b-1"
              disabled={!canEditAiMl}
            />
            <Button
              variant="secondary"
              size="sm"
              onClick={handleAddDenyWords}
              disabled={!canEditAiMl}
              className="w-full sm:w-auto"
            >
              Add word
            </Button>
          </div>
        </div>

        {showDenyWordsTable ? (
          <div className="grid grid-cols-1 xl:grid-cols-1 gap-4 xl:gap-6 my-2">
            <div className="overflow-x-auto bg-white rounded-lg border border-gray-300">
              {denyWordsArray.length === 0 ? (
                <div className="p-4 text-center text-gray-500 text-sm">
                  No deny words configured. Add words above to get started.
                </div>
              ) : (
                <div className="max-h-60 overflow-y-auto border-t border-gray-200">
                  <ConfigurableTable
                    data={denyWordsArray}
                    keyExtractor={(row) => row.id}
                    columns={[
                      {
                        header: "Deny Word",
                        accessor: "word",
                        headerClassName:
                          "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200",
                        className: "text-xs md:text-sm text-gray-900 py-3",
                        searchable: true,
                      },
                      ...(canEditAiMl ? [{
                        header: "Action",
                        headerClassName:
                          "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200 w-20",
                        render: (denyWord: DenyWordRecord) => (
                          <div className="flex flex-row gap-1 sm:gap-2">
                            <Button
                              variant="default"
                              size="sm"
                              className="hover:text-red-500"
                              onClick={() => handleRemoveDenyWord(denyWord.id)}
                            >
                              ✕
                            </Button>
                          </div>
                        ),
                        searchable: false,
                      }] : []),
                    ]}
                    headerRowClassName="bg-gray-50 sticky top-0 z-10"
                    rowClassName="bg-white border-t border-gray-200 hover:bg-gray-50"
                  />
                </div>
              )}
            </div>
          </div>
        ) : null}

        <div className="mt-2 flex items-center gap-3">
          <div className="flex flex-row items-center text-sm md:text-medium text-gray-900 min-w-fit">
            <span>Enable Langfuse Tracing</span>
            <InfoHint text="When enabled, all AI interactions are logged to Langfuse for monitoring response quality and debugging." />
          </div>
          {langfuseEnabled !== undefined ? (
            <Toggle id="langfuse-toggle" enabled={langfuseEnabled} onChange={setLangfuseEnabled} disabled={!canEditAiMl} />
          ) : (
            <div className="w-11 h-6 bg-gray-200 rounded-full animate-pulse" />
          )}
        </div>
      </section>
    </div>
  );
};

export default AiMlConfigPage;
