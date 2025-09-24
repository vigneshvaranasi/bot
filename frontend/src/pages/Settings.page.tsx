import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import InputBox from "../components/ui/InputBox";
import Dropdown from "../components/ui/Dropdown";
import UploadFiles from "../components/ui/UploadFiles";
import Checkbox from "../components/ui/Checkbox";
import Toggle from "../components/ui/Toggle";
import { ConfigurableTable } from "../components/ui/Table";
import ButtonGroup from "../components/ui/ButtonGroup";
import SettingsNavbar from "../components/SettingsNavbar";
import SettingsCard from "../components/ui/SettingsCard";
import arrowLeftIcon from "../assets/arrow-left.svg";
import { fetchSettings, updateSettings } from "../handlers/settingsHandlers";
import type { Model, DenyWordRecord, FileRecord } from "../types/Settings";
import { useAuthContext } from "../hooks/useAuthContext";
import InfoHint from "../components/ui/InfoHint";

const Settings: React.FC = () => {
  const navigate = useNavigate();
  const [uploadedFiles, setUploadedFiles] = useState<FileRecord[]>([
    {
      id: "1",
      fileName: "payUData.json",
      fileType: "JSON",
      size: "5.4MB",
      lastUpdated: "21 July 2025",
    },
    {
      id: "2",
      fileName: "payUData.json",
      fileType: "JSON",
      size: "5.4MB",
      lastUpdated: "21 July 2025",
    },
    {
      id: "3",
      fileName: "payUData.json",
      fileType: "JSON",
      size: "5.4MB",
      lastUpdated: "21 July 2025",
    },
    {
      id: "4",
      fileName: "payUData.json",
      fileType: "JSON",
      size: "5.4MB",
      lastUpdated: "21 July 2025",
    },
    {
      id: "5",
      fileName: "payUData.json",
      fileType: "JSON",
      size: "5.4MB",
      lastUpdated: "21 July 2025",
    },
  ]);
  const { user } = useAuthContext();

  const [selectedRole, setSelectedRole] = useState("Support");
  const [versionsTracked, setVersionsTracked] = useState("5");
  const [purgeDays, setPurgeDays] = useState("30");
  const [pidMaskingFields, setPidMaskingFields] = useState("");
  const [denyWordsArray, setDenyWordsArray] = useState<DenyWordRecord[]>([]);
  const [denyWords, setDenyWords] = useState("");
  const [showDenyWordsTable, setShowDenyWordsTable] = useState(false);
  const [model, setModel] = useState<Model>("gemma3:4b");
  const [temperature, setTemperature] = useState("");
  const [accessChat, setAccessChat] = useState(false);
  const [rating, setRating] = useState(false);
  const [requestPastIncidents, setRequestPastIncidents] = useState(false);
  const [versionControl, setVersionControl] = useState(true);
  const [purgeEnabled, setPurgeEnabled] = useState(true);

  // convert comma-separated string to array
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

  // convert array to comma-separated string
  const wordsArrayToString = useCallback(
    (wordsArray: DenyWordRecord[]): string => {
      return wordsArray.map((item) => item.word).join(",");
    },
    []
  );

  // add deny words
  const handleAddDenyWords = () => {
    if (!denyWords.trim()) return;

    const newWords = denyWords
      .split(",")
      .map((word) => word.trim())
      .filter((word) => word.length > 0);

    const existingWords = denyWordsArray.map((item) => item.word.toLowerCase());
    const wordsToAdd = newWords.filter(
      (word) => !existingWords.includes(word.toLowerCase())
    );

    if (wordsToAdd.length > 0) {
      const newWordRecords: DenyWordRecord[] = wordsToAdd.map(
        (word, index) => ({
          id: `word-${Date.now()}-${index}`,
          word: word,
        })
      );

      const updatedDenyWordsArray = [...denyWordsArray, ...newWordRecords];
      setDenyWordsArray(updatedDenyWordsArray);

      // auto show, dint like
      // if (!showDenyWordsTable) {
      //   setShowDenyWordsTable(true);
      // }
    }

    setDenyWords("");
  };

  // remove a deny word
  const handleRemoveDenyWord = (wordId: string) => {
    const updatedDenyWordsArray = denyWordsArray.filter(
      (item) => item.id !== wordId
    );
    setDenyWordsArray(updatedDenyWordsArray);
  };

  const roleOptions = [
    { value: "L1 Support", label: "L1 Support" },
    { value: "L2 Support", label: "L2 Support" },
    { value: "L3 Support", label: "L3 Support" },
    { value: "Senior Support", label: "Senior Support" },
    { value: "Support Manager", label: "Support Manager" },
    { value: "Technical Lead", label: "Technical Lead" },
    { value: "System Administrator", label: "System Administrator" },
    { value: "Operations Lead", label: "Operations Lead" },
  ];

  const modelOptions = [
    { value: "gemma3:1b", label: "Gemma3: 1B" },
    { value: "gemma3:4b", label: "Gemma3: 4B" },
    { value: "gemini-2.0-flash", label: "Gemini: 2.0 Flash" },
    { value: "gemini-2.5-flash", label: "Gemini: 2.5 Flash" },
    { value: "gemini-2.0-flash-lite-001", label: "Gemini: 2.0 Flash Lite" },
    { value: "gemini-2.5-pro", label: "Gemini: 2.5 Pro" },
  ];

  const onSave = async () => {
    try {
      let totalDenyWords = wordsArrayToString(denyWordsArray);
      const newSettings = {
        deny_words: totalDenyWords,
        model,
        temperature,
      };
      const token = user?.token || null;
      if (!token) {
        alert("User not authenticated");
        return;
      }
      const saveSettings = await updateSettings(newSettings, token);
      if (saveSettings) {
        alert("Settings saved successfully");
        setDenyWords("");
        if (saveSettings.deny_words !== undefined) {
          setDenyWordsArray(stringToWordsArray(saveSettings.deny_words));
        }
        setModel(saveSettings.model);
        setTemperature(saveSettings.temperature);
      } else {
        alert("Failed to save settings");
      }
    } catch (error) {
      console.error("Error saving settings:", error);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const settings = await fetchSettings();
        if (settings) {
          const denyWordsFromBackend = settings.deny_words || "";
          setDenyWordsArray(stringToWordsArray(denyWordsFromBackend));
          setModel(settings.model);
          setTemperature(settings.temperature);
        }
      } catch (error) {
        console.error("Error fetching settings:", error);
      }
    };
    fetchData();
  }, [stringToWordsArray]);

  const handleDeleteFile = (fileId: string) => {
    setUploadedFiles((files) => files.filter((file) => file.id !== fileId));
  };
  const handleRollbackFile = (fileId: string) =>
    console.log("Rollback file:", fileId);
  const handleGoToChat = () => navigate("/");
  const handleEditUsers = () => navigate("/user-management");

  return (
    <div className="min-h-screen h-full bg-gray-100">
      {/* Header */}
      <SettingsNavbar />

      {/* Main Content */}
      <div className="p-4 md:p-6 bg-gray-100">
        <div className="max-w-screen-2xl mx-auto">
          <div className="grid gap-6 md:gap-8 grid-cols-1 lg:grid-cols-[1.44fr_1.5fr]">
            {/* Left Column */}
            <div className="space-y-6 order-2 lg:order-1 hidden">
              {/* Upload Files */}
              <UploadFiles compact />

              {/* Role Management */}
              <SettingsCard
                title="Role Management"
                className="p-3 md:p-4"
                hidden={true}
              >
                <div className="mb-4 flex flex-col sm:flex-row items-start sm:items-center gap-3">
                  <label className="text-sm md:text-base text-gray-800 min-w-fit">
                    Role Permissions
                  </label>
                  <div className="w-full sm:w-auto">
                    <Dropdown
                      options={roleOptions}
                      value={selectedRole}
                      onChange={setSelectedRole}
                      placeholder="Select role"
                    />
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row flex-wrap gap-4 md:gap-6">
                  <Checkbox
                    id="perm-access-chat"
                    label="Access Chat"
                    checked={accessChat}
                    onChange={setAccessChat}
                  />
                  <Checkbox
                    id="perm-rating"
                    label="Rating"
                    checked={rating}
                    onChange={setRating}
                  />
                  <Checkbox
                    id="perm-request-past"
                    label="Request Past Incidents"
                    checked={requestPastIncidents}
                    onChange={setRequestPastIncidents}
                  />
                </div>
              </SettingsCard>
            </div>

            {/* Right Column */}
            <div className="space-y-6 order-1 lg:order-2">
              {/* Knowledge Base Management */}
              <SettingsCard title="Knowledge Base Management" hidden={true}>
                {/* Description + REFRESH */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4">
                  <span className="text-sm md:text-medium text-black flex-1">
                    Re-train the knowledge base &amp; put the app on maintenance
                  </span>
                  <Button
                    variant="secondary"
                    className="font-semibold text-xs px-4 py-1 transition-colors duration-200 bg-gray-500 hover:bg-gray-600 text-white rounded-md cursor-pointer w-full sm:w-auto"
                  >
                    REFRESH
                  </Button>
                </div>

                {/* Toggle row */}
                <div className="mb-4">
                  <label className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                    <span className="text-sm md:text-medium text-gray-900">
                      Version Control
                    </span>
                    <Toggle
                      id="kb-version-control"
                      enabled={versionControl}
                      onChange={setVersionControl}
                    />
                  </label>
                </div>

                {/* Number of versions */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                  <label className="text-sm md:text-medium text-gray-900 min-w-fit">
                    Number of versions tracked
                  </label>
                  <InputBox
                    value={versionsTracked}
                    onChange={setVersionsTracked}
                    variant="primary"
                    type="number"
                    className="
                      outline-none
                      border-b-1
                      border-gray-400 
                      rounded-[8px] 
                      px-0 py-0
                      text-medium 
                      text-gray-900
                      w-16
                      "
                  />
                </div>
              </SettingsCard>

              {/* Data & Privacy */}
              <SettingsCard title="Data & Privacy" hidden={true}>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 xl:gap-6">
                  {/* PID Masking Rules */}
                  <div className="space-y-3">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
                      <span className="text-sm md:text-medium text-black min-w-fit">
                        PID Masking Rules
                      </span>
                      <Button
                        variant="secondary"
                        className="font-semibold text-xs px-4 py-1 transition-colors duration-200 bg-gray-500 hover:bg-gray-600 text-white rounded-md cursor-pointer w-full sm:w-auto"
                      >
                        ADD RULE
                      </Button>
                    </div>

                    <InputBox
                      value={pidMaskingFields}
                      onChange={setPidMaskingFields}
                      placeholder="Add fields to ignore"
                      variant="primary"
                      className="
                        w-full
                        rounded-[5px]
                        border-gray-400
                        border-b-1
                      "
                    />
                  </div>

                  {/* Automatically Purge */}
                  <div className="space-y-3">
                    <label className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
                      <span className="text-sm md:text-medium text-black min-w-fit">
                        Automatically Purge Archived Clusters
                      </span>
                      <Toggle
                        enabled={purgeEnabled}
                        onChange={setPurgeEnabled}
                        id="purgeToggle"
                      />
                    </label>

                    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
                      <span className="text-sm md:text-medium text-black min-w-fit">
                        Choose Purge Trigger days
                      </span>
                      <InputBox
                        value={purgeDays}
                        onChange={setPurgeDays}
                        variant="primary"
                        type="number"
                        className="
                          outline-none
                          border-b-1
                          border-gray-400 
                          rounded-[8px] 
                          px-0 py-0
                          text-medium 
                          text-gray-900
                          w-16
                        "
                      />
                    </div>
                  </div>
                </div>
              </SettingsCard>

              {/* Configurations */}
              <SettingsCard title="Configurations" hidden={false}>
                <div className="grid grid-cols-1 xl:grid-cols-1 gap-4 xl:gap-6">
                  {/* Deny List Rules */}
                  <div className="space-y-3">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center sm:justify-between gap-2">
                      <span className="flex flex-row justify-between text-sm md:text-medium text-black w-full">
                        <div className="flex flex-row items-center gap-1">
                          <span>Deny List Words</span>
                          <InfoHint
                            text="Words added here will be filtered out from both user queries and model responses."
                            position="right"
                            gap={0.3}
                          />
                        </div>
                        <span className="text-xs text-gray-600 font-normal">
                          <button
                            onClick={() =>
                              setShowDenyWordsTable(!showDenyWordsTable)
                            }
                            className="ml-2 text-blue-600 hover:text-blue-800 underline cursor-pointer"
                          >
                            {showDenyWordsTable
                              ? "Hide All"
                              : `View All (${denyWordsArray.length})`}
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
                        className="
                        w-full
                        rounded-[5px]
                        border-gray-400
                        border-b-1
                      "
                      />
                      <Button
                        variant="secondary"
                        className="font-semibold text-xs px-4 py-1 transition-colors duration-200 bg-gray-500 hover:bg-gray-600 text-white rounded-md cursor-pointer w-full sm:w-auto"
                        onClick={handleAddDenyWords}
                      >
                        ADD WORD
                      </Button>
                    </div>
                  </div>
                </div>
                {/* Table for Deny Words */}
                {showDenyWordsTable && (
                  <div className="grid grid-cols-1 xl:grid-cols-1 gap-4 xl:gap-6 my-2">
                    <div className="overflow-x-auto bg-white rounded-lg border border-gray-300">
                      {denyWordsArray.length === 0 ? (
                        <div className="p-4 text-center text-gray-500 text-sm">
                          No deny words configured. Add words above to get
                          started.
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
                                className:
                                  "text-xs md:text-sm text-gray-900 py-3",
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
                                      className=" hover:text-red-500 text-xs px-2 md:px-3 py-1"
                                      onClick={() =>
                                        handleRemoveDenyWord(denyWord.id)
                                      }
                                    >
                                      &#x2715;
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
                )}
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 xl:gap-6">
                  {/* Select of Models (Gemma3:1b, Gemma3:4b) */}
                  <div className="flex flex-col justify-between space-y-3 h-full">
                    <div className="flex flex-row  items-center text-sm md:text-medium text-black min-w-fit">
                      <span>Select Model</span>
                      <InfoHint
                        text="Gemma Models are Locally run and Gemini are cloud-based, may incur costs."
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
                  {/*Temperature */}
                  <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mt-4">
                    <div className="flex flex-row items-center text-sm md:text-medium text-gray-900 min-w-fit">
                      <label>Temperature</label>
                      <InfoHint
                        text="Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic."
                        position="right"
                        gap={0.3}
                      />
                    </div>
                    <InputBox
                      value={temperature}
                      onChange={(val) => setTemperature(val)}
                      variant="primary"
                      type="number"
                      className="
                          outline-none
                          border-b-1
                          border-gray-400 
                          rounded-[8px] 
                          px-0 py-0
                          text-medium 
                          text-gray-900
                          w-16
                          "
                      step={0.1}
                      min={0}
                      max={1}
                    />
                  </div>
                </div>
              </SettingsCard>

              {/* User Management */}
              <SettingsCard title="User Management" hidden={true}>
                <Button
                  variant="secondary"
                  className="font-semibold text-xs px-4 py-1 transition-colors duration-200 bg-gray-500 hover:bg-gray-600 text-white rounded-md cursor-pointer w-full sm:w-auto"
                  onClick={handleEditUsers}
                >
                  EDIT USERS
                </Button>
              </SettingsCard>
            </div>
          </div>

          {/* Knowledge Base Version Control Table */}
          <div className="mt-6 md:mt-8 hidden">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 px-2">
              Knowledge Base Version Control
            </h2>
            <div className="overflow-x-auto bg-white rounded-lg shadow-lg border border-gray-300">
              <ConfigurableTable
                data={uploadedFiles}
                keyExtractor={(row) => row.id}
                columns={[
                  {
                    header: "File Name",
                    accessor: "fileName",
                    headerClassName:
                      "font-medium text-gray-700 text-xs md:text-sm",
                    className: "text-xs md:text-sm text-gray-900",
                  },
                  {
                    header: "File Type",
                    accessor: "fileType",
                    headerClassName:
                      "font-medium text-gray-700 text-xs md:text-sm",
                    className: "text-xs md:text-sm text-gray-900",
                  },
                  {
                    header: "Size",
                    accessor: "size",
                    headerClassName:
                      "font-medium text-gray-700 text-xs md:text-sm",
                    className: "text-xs md:text-sm text-gray-900",
                  },
                  {
                    header: "Last Updated",
                    accessor: "lastUpdated",
                    headerClassName:
                      "font-medium text-gray-700 text-xs md:text-sm hidden sm:table-cell",
                    className:
                      "text-xs md:text-sm text-gray-900 hidden sm:table-cell",
                  },
                  {
                    header: "Actions",
                    headerClassName:
                      "font-medium text-gray-700 text-xs md:text-sm",
                    render: (file) => (
                      <div className="flex flex-row gap-1 sm:gap-2">
                        <Button
                          variant="secondary"
                          className="bg-gray-400 text-white hover:bg-gray-500 text-xs px-2 md:px-3 py-1"
                          onClick={() => handleRollbackFile(file.id)}
                        >
                          ROLLBACK
                        </Button>
                        <Button
                          variant="secondary"
                          className="bg-gray-400 text-white hover:bg-gray-500 text-xs px-2 md:px-3 py-1"
                          onClick={() => handleDeleteFile(file.id)}
                        >
                          DELETE
                        </Button>
                      </div>
                    ),
                  },
                ]}
                headerRowClassName="bg-gray-50"
                rowClassName="bg-white border-t border-gray-200"
              />
            </div>
          </div>

          {/* Bottom Actions */}
          <div className="mt-6 flex items-center justify-center mb-4 px-4">
            <ButtonGroup className="border border-gray-300 bg-white rounded-full shadow-sm p-1 sm:w-auto">
              <Button
                title="Go to Chat"
                variant="default"
                onClick={handleGoToChat}
                className="bg-transparent hover:bg-gray-50 hover:rounded-full text-gray-900 px-4 md:px-6 py-2 rounded-full flex items-center justify-center gap-2 flex-1 sm:flex-none"
              >
                <img src={arrowLeftIcon} alt="arrow left" className="w-4 h-4" />
                <span className="hidden sm:inline">Go to Chat</span>
                <span className="sm:hidden">Back</span>
              </Button>

              <Button variant="primary" rounded="full" onClick={onSave} title="Save Settings">
                SAVE
              </Button>
            </ButtonGroup>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
