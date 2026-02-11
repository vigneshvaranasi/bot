import SettingsHeader from "../../components/settings/SettingsHeader";
import InputBox from "../../components/ui/InputBox";
import Toggle from "../../components/ui/Toggle";
import { Button } from "../../components/ui/Button";
import { useState } from "react";
import { toast } from "react-hot-toast";
import InfoHint from "../../components/ui/InfoHint";

const SystemConfigPage = () => {
  const [purgeEnabled, setPurgeEnabled] = useState(true);
  const [purgeDays, setPurgeDays] = useState("30");
  const [pidMaskingFields, setPidMaskingFields] = useState("");

  const handleSave = () => {
    toast.success("System configuration saved (stub). Wire to backend when available.");
  };

  return (
    <div className="space-y-8">
      <SettingsHeader
        title="System Configuration"
        description="Org-wide defaults, retention, and masking rules."
      />

      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Data & Privacy</h3>
            <p className="text-xs text-gray-600">
              Retention and masking settings. Section-level save required.
            </p>
          </div>
          <Button variant="primary" onClick={handleSave}>
            Save
          </Button>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 xl:gap-6">
          <div className="space-y-3">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm md:text-medium text-black min-w-fit">PID Masking Rules</span>
                <InfoHint text="Defines which data fields are automatically redacted before being sent to the AI. Add field names like SSN or credit_card to protect sensitive information." />
              </div>
              <Button
                variant="secondary"
                className="font-semibold text-xs px-4 py-1 transition-colors duration-200 bg-gray-500 hover:bg-gray-600 text-white rounded-md cursor-pointer w-full sm:w-auto"
              >
                Add rule
              </Button>
            </div>
            <InputBox
              value={pidMaskingFields}
              onChange={setPidMaskingFields}
              placeholder="Add fields to ignore"
              variant="primary"
              className="w-full rounded-[5px] border-gray-400 border-b-1"
            />
          </div>
          <div className="space-y-3">
            <label className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm md:text-medium text-black min-w-fit">
                  Automatically purge archived clusters
                </span>
                <InfoHint text="When enabled, resolved incident clusters that have been archived will be permanently deleted after the trigger period to free up storage." />
              </div>
              <Toggle enabled={purgeEnabled} onChange={setPurgeEnabled} id="purgeToggle" />
            </label>
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
              <div className="flex items-center gap-1">
                <span className="text-sm md:text-medium text-black min-w-fit">
                  Choose purge trigger days
                </span>
                <InfoHint text="How many days to keep archived clusters before permanently deleting them. For example, 30 means clusters are kept for 30 days after archiving." />
              </div>
              <InputBox
                value={purgeDays}
                onChange={setPurgeDays}
                variant="primary"
                type="number"
                className="outline-none border-b-1 border-gray-400 rounded-[8px] px-0 py-0 text-medium text-gray-900 w-16"
              />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default SystemConfigPage;
