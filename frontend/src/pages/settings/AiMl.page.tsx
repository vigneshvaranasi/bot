import { useCallback, useEffect, useMemo, useState } from "react";
import SettingsHeader from "../../components/settings/SettingsHeader";
import Dropdown from "../../components/ui/Dropdown";
import InputBox from "../../components/ui/InputBox";
import Toggle from "../../components/ui/Toggle";
import { Button } from "../../components/ui/Button";
import { ConfigurableTable } from "../../components/ui/Table";
import InfoHint from "../../components/ui/InfoHint";
import { fetchSettings, updateSettings } from "../../handlers/settingsHandlers";
import type { DenyWordRecord, Model, Settings } from "../../types/Settings";
import { toast } from "react-hot-toast";
import { logger } from "../../utils/logger";

const modelOptions = [
  { value: "gpt-oss:20b", label: "GPT-OSS: 20B" },
  { value: "gemma3:1b", label: "Gemma3: 1B" },
  { value: "gemma3:4b", label: "Gemma3: 4B" },
  { value: "gemini-2.0-flash", label: "Gemini: 2.0 Flash" },
  { value: "gemini-2.5-flash", label: "Gemini: 2.5 Flash" },
  { value: "gemini-2.0-flash-lite-001", label: "Gemini: 2.0 Flash Lite" },
  { value: "gemini-2.5-pro", label: "Gemini: 2.5 Pro" },
];

const AiMlConfigPage = () => {
  const [model, setModel] = useState<Model>("gemma3:4b");
  const [temperature, setTemperature] = useState("0.2");
  const [langfuseEnabled, setLangfuseEnabled] = useState(true);

  const [denyWordsArray, setDenyWordsArray] = useState<DenyWordRecord[]>([]);
  const [denyWords, setDenyWords] = useState("");
  const [showDenyWordsTable, setShowDenyWordsTable] = useState(false);

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

  useEffect(() => {
    const loadSettings = async () => {
      try {
        setLoading(true);
        const settings = await fetchSettings();
        if (settings) {
          const denyWordsFromBackend = settings.deny_words || "";
          setDenyWordsArray(stringToWordsArray(denyWordsFromBackend));
          setModel(settings.model);
          setTemperature(settings.temperature);
          setLangfuseEnabled(settings.langfuse_enabled ?? true);
        }
      } catch (err) {
        logger.error("Error fetching AI/ML settings", err);
        setError("Unable to load AI/ML settings");
      } finally {
        setLoading(false);
      }
    };
    loadSettings();
  }, [stringToWordsArray]);

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
      const modelPayload: Partial<Settings> = {
        model,
        temperature,
      };
      await updateSettings(modelPayload);
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
      const safetyPayload: Partial<Settings> = {
        deny_words: wordsArrayToString(denyWordsArray),
        langfuse_enabled: langfuseEnabled,
      };
      await updateSettings(safetyPayload);
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

  return (
    <div className="space-y-8">
      <SettingsHeader
        title="AI / ML Configuration"
        description="Configure model selection, generation controls, safety filters, and observability."
        status={loading ? <span className="text-sm text-gray-500">Loading…</span> : null}
      />

      {error ? (
        <div className="p-3 bg-red-50 text-sm text-red-700 border border-red-200 rounded">
          {error}
        </div>
      ) : null}

      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Model & Generation</h3>
            <p className="text-xs text-gray-600">Select model and configure generation parameters.</p>
          </div>
          <Button variant="primary" onClick={handleSaveModel} disabled={savingModel}>
            {savingModel ? "Saving…" : "Save"}
          </Button>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="space-y-3">
            <div className="flex flex-row items-center text-sm md:text-medium text-black min-w-fit">
              <span>Select Model</span>
              <InfoHint
                text="Gemma models are local; Gemini are cloud-based and may incur costs."
                position="right"
                gap={0.3}
              />
            </div>
            <Dropdown
              options={modelOptions}
              value={model}
              onChange={(val) => setModel(val as Model)}
              placeholder="Select model"
            />
          </div>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mt-4">
            <div className="flex flex-row items-center text-sm md:text-medium text-gray-900 min-w-fit">
              <label>Temperature</label>
              <InfoHint
                text="Higher values increase randomness; lower values increase determinism."
                position="right"
                gap={0.3}
              />
            </div>
            <InputBox
              value={temperature}
              onChange={(val) => setTemperature(val)}
              variant="primary"
              type="number"
              className="outline-none border-b-1 border-gray-400 rounded-[8px] px-0 py-0 text-medium text-gray-900 w-20"
              step={0.1}
              min={0}
              max={1}
            />
          </div>
        </div>
      </section>

      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Safety & Observability</h3>
            <p className="text-xs text-gray-600"> Configure safety filters and tracing options.</p>
          </div>
          <Button variant="primary" onClick={handleSaveSafety} disabled={savingSafety}>
            {savingSafety ? "Saving…" : "Save"}
          </Button>
        </div>

        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row items-start sm:items-center sm:justify-between gap-2">
            <span className="flex flex-row justify-between text-sm md:text-medium text-black w-full">
              <div className="flex flex-row items-center gap-1">
                <span>Deny List Words</span>
                <InfoHint
                  text="Words added here will be filtered from prompts and responses."
                  position="right"
                  gap={0.3}
                />
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
            />
            <Button
              variant="secondary"
              className="font-semibold text-xs px-4 py-1 transition-colors duration-200 bg-gray-500 hover:bg-gray-600 text-white rounded-md cursor-pointer w-full sm:w-auto"
              onClick={handleAddDenyWords}
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
                      {
                        header: "Action",
                        headerClassName:
                          "font-medium text-gray-700 text-xs md:text-sm sticky top-0 bg-gray-50 z-10 border-b border-gray-200 w-20",
                        render: (denyWord) => (
                          <div className="flex flex-row gap-1 sm:gap-2">
                            <Button
                              variant="default"
                              className="hover:text-red-500 text-xs px-2 md:px-3 py-1"
                              onClick={() => handleRemoveDenyWord(denyWord.id)}
                            >
                              ✕
                            </Button>
                          </div>
                        ),
                        searchable: false,
                      },
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
            <InfoHint text="Toggle Langfuse tracing for observability." position="top" gap={2} />
          </div>
          <Toggle id="langfuse-toggle" enabled={langfuseEnabled} onChange={setLangfuseEnabled} />
        </div>
      </section>
    </div>
  );
};

export default AiMlConfigPage;
