import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import InputBox from '../components/ui/InputBox';
import Dropdown from '../components/ui/Dropdown';
import UploadFiles from '../components/ui/UploadFiles';
import Checkbox from '../components/ui/Checkbox';
import Toggle from '../components/ui/Toggle';

interface FileRecord {
  fileName: string;
  fileType: string;
  size: string;
  lastUpdated: string;
  id: string;
}

const Settings: React.FC = () => {
  const navigate = useNavigate();
  const [uploadedFiles, setUploadedFiles] = useState<FileRecord[]>([
    { id: '1', fileName: 'payUData.json', fileType: 'JSON', size: '5.4MB', lastUpdated: '21 July 2025' },
    { id: '2', fileName: 'payUData.json', fileType: 'JSON', size: '5.4MB', lastUpdated: '21 July 2025' },
    { id: '3', fileName: 'payUData.json', fileType: 'JSON', size: '5.4MB', lastUpdated: '21 July 2025' },
    { id: '4', fileName: 'payUData.json', fileType: 'JSON', size: '5.4MB', lastUpdated: '21 July 2025' },
    { id: '5', fileName: 'payUData.json', fileType: 'JSON', size: '5.4MB', lastUpdated: '21 July 2025' }
  ]);

  const [selectedRole, setSelectedRole] = useState('Support');
  const [versionsTracked, setVersionsTracked] = useState('5');
  const [purgeDays, setPurgeDays] = useState('30');
  const [pidMaskingFields, setPidMaskingFields] = useState('');
  const [accessChat, setAccessChat] = useState(false);
  const [rating, setRating] = useState(false);
  const [requestPastIncidents, setRequestPastIncidents] = useState(false);
  const [versionControl, setVersionControl] = useState(true);
  const [purgeEnabled, setPurgeEnabled] = useState(true);


  const roleOptions = [
    { value: 'L1 Support', label: 'L1 Support' },
    { value: 'L2 Support', label: 'L2 Support' },
    { value: 'L3 Support', label: 'L3 Support' },
    { value: 'Senior Support', label: 'Senior Support' },
    { value: 'Support Manager', label: 'Support Manager' },
    { value: 'Technical Lead', label: 'Technical Lead' },
    { value: 'System Administrator', label: 'System Administrator' },
    { value: 'Operations Lead', label: 'Operations Lead' }
];

  const handleDeleteFile = (fileId: string) => {
    setUploadedFiles(files => files.filter(file => file.id !== fileId));
  };
  const handleRollbackFile = (fileId: string) => console.log('Rollback file:', fileId);
    const handleGoToChat = () => {
    navigate('/');
  };

  const handleGoToUserManagement = () => {
    navigate('/user-management');
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <div className="px-6 py-4">
        <div className="max-w-screen-2xl mx-auto grid grid-cols-[1.5fr_1.5fr] items-center">
          {/* Logo (unchanged) */}
          <div className="bg-white px-8 py-2 rounded-[10px] text-lg font-low text-gray-900 w-fit">Logo</div>

          {/* Right cell: full-width search + avatar (unchanged) */}
          <div className="flex items-center gap-4 justify-end w-full">
            {/* Full-width search with gray bottom and icon */}
            <div className="relative w-full">
              <input
                type="text"
                placeholder="Search"
                className="
                    w-full h-11 pr-12 pl-11
                    bg-white rounded-[5px]
                    border-0 border-b-2 border-gray-400
                    placeholder-gray-500
                    focus:outline-none focus:ring-0
                    hover:border-gray-400 focus:border-gray-400 active:border-gray-400
                    "
              />
              {/* Search icon */}
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-500 pointer-events-none"
                viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
              >
                <circle cx="11" cy="11" r="7" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              {/* Right padding icon spacer (optional) */}
              <div className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 opacity-0" />
            </div>

            <div className="w-10 h-10 bg-gray-400 rounded-full flex items-center justify-center relative left-4">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="text-white">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" strokeWidth="2"/>
                <circle cx="12" cy="7" r="4" stroke="currentColor" strokeWidth="2"/>
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-6">
        <div className="max-w-screen-2xl mx-auto">
          <div className="grid gap-8" style={{ gridTemplateColumns: '1.44fr 1.5fr' }}>
            {/* Left Column */}
            <div className="space-y-6">
              {/* Upload Files (compact to remove extra white space) */}
              <UploadFiles/>

              {/* Role Management */}
              <div className="bg-white rounded-lg shadow-lg border-2 border-gray-300 p-3">
                <h2 className="text-xl text-black mb-4">Role Management</h2>

                <div className="mb-4 flex items-center gap-3">
                  <label className="text-base text-gray-800">Role Permissions</label>
                  <Dropdown
                    options={roleOptions}
                    value={selectedRole}
                    onChange={setSelectedRole}
                    placeholder="Select role"
                  />
                </div>

                <div className="flex flex-wrap gap-6 mb-4">
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

                <Button
                  variant="secondary"
                  onClick={handleGoToUserManagement}
                  className="bg-gray-400 text-white hover:bg-gray-500 text-sm px-4 py-2"
                >
                  EDIT USERS
                </Button>
              </div>
            </div>

            {/* Right Column */}
            <div className="space-y-6 pr-13">
              {/* Knowledge Base Management — redesigned */}
              <div className="bg-white rounded-lg shadow-lg border-2 border-gray-300 p-5">
                {/* Big, clean title like the mock */}
                <h2 className="text-xl text-black mb-4">
                  Knowledge Base Management
                </h2>

                {/* Description + REFRESH on the same row */}
                <div className="flex items-center mb-2">
                  <span className="text-medium text-black">
                    Re-train the knowledge base &amp; put the app on maintenance
                  </span>
                  <Button
                    variant="secondary"
                    className="ml-4 font-semibold text-xs px-4 py-1 transition-colors duration-200 bg-gray-500 hover:bg-gray-600 text-white rounded-md cursor-pointer"
                  >
                    REFRESH
                  </Button>
                </div>

                {/* Toggle row (uses your Toggle component) */}
                <div className="mb-3">
                  <label className="flex items-center gap-4">
                    <span className="text-medium text-gray-900">Version Control</span>
                    {/* keep the Toggle exactly as your component defines it */}
                    <Toggle
                      id="kb-version-control"
                      enabled={versionControl}
                      onChange={setVersionControl}
                    />
                  </label>
                </div>

                {/* Number with underline treatment (like search/upload) */}
                 <div className="flex items-center gap-2">
                <label className="text-medium text-gray-900">
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
                w-10
                "
                />

              </div>
              </div>

             
             {/* Data & Privacy */}
              <div className="bg-white rounded-lg border border-gray-300 p-3">
  <h2 className="text-lg font-semibold text-gray-900 mb-4">Data & Privacy</h2>

  <div className="grid grid-cols-2 gap-4 items-center">
    {/* Left col - PID Masking Rules */}
    <div className="flex items-center gap-2">
      <span className="text-sm font-medium text-gray-700">PID Masking Rules</span>
      <Button
        variant="secondary"
        className="bg-gray-300 text-white hover:bg-gray-500 text-sm px-2 py-1"
      >
        ADD RULE
      </Button>
    </div>

    {/* Right col - Automatically Purge */}
    <label className="flex items-center gap-2">
      <span className="text-sm text-gray-700">
        Automatically Purge Archived Clusters
      </span>
      <Toggle
        enabled={purgeEnabled}
        onChange={setPurgeEnabled}
        id="purgeToggle"
      />
    </label>

    {/* Left col - Add fields */}
    <InputBox
      value={pidMaskingFields}
      onChange={setPidMaskingFields}
      placeholder="Add fields to ignore"
      variant="primary"
      className="w-full"
    />

    {/* Right col - Purge Trigger Days */}
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-700">Choose Purge Trigger days</span>
      <InputBox
        value={purgeDays}
        onChange={setPurgeDays}
        variant="primary"
        type="number"
        className="w-16"
      />
    </div>
  </div>
</div>



              {/* User Management */}
              <div className="mt-8 bg-white rounded-lg border border-gray-300 p-6">
                <h2 className="text-lg text-gray-900 mb-4">User Management</h2>
                <Button variant="secondary" className="ml-4 font-semibold text-xs px-4 py-1 transition-colors duration-200 bg-gray-500 hover:bg-gray-600 text-white rounded-md cursor-pointer">
                  EDIT USERS
                </Button>
              </div>
            </div>
          </div>

          {/* Knowledge Base Version Control Table */}
          <div className="mt-8 bg-white rounded-lg border border-gray-300 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Knowledge Base Version Control</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">File Name</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">File Type</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Size</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Last Updated</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Rollback</th>
                    <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Delete</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {uploadedFiles.map((file) => (
                    <tr key={file.id}>
                      <td className="px-4 py-3 text-sm text-gray-900">{file.fileName}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{file.fileType}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{file.size}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{file.lastUpdated}</td>
                      <td className="px-4 py-3">
                        <Button
                          variant="secondary"
                          className="bg-gray-400 text-white hover:bg-gray-500 text-xs px-3 py-1"
                          onClick={() => handleRollbackFile(file.id)}
                        >
                          ROLLBACK
                        </Button>
                      </td>
                      <td className="px-4 py-3">
                        <Button
                          variant="secondary"
                          className="bg-gray-400 text-white hover:bg-gray-500 text-xs px-3 py-1"
                          onClick={() => handleDeleteFile(file.id)}
                        >
                          DELETE
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Bottom Actions */}
          <div className="mt-6 flex items-center justify-between">
            <Button
              variant="secondary"
              onClick={handleGoToChat}
              className="bg-gray-300 text-gray-800 hover:bg-gray-400 rounded-full px-6 py-2"
            >
              ← Go to Chat
            </Button>
            <Button variant="primary" className="bg-blue-500 text-white hover:bg-blue-600 rounded-full px-8 py-2">
              SAVE
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;