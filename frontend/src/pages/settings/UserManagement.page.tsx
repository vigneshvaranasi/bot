import React, { useEffect, useMemo, useState } from "react";
import { Button } from "../../components/ui/Button";
import { ConfigurableTable } from "../../components/ui/Table";
import SettingsHeader from "../../components/settings/SettingsHeader";
import {
  fetchUsers,
  fetchRoles,
  updateUser,
  deleteUser,
  type AdminUser,
  type Role,
} from "../../handlers/adminHandlers";
import Dropdown from "../../components/ui/Dropdown";
import { toast } from "react-hot-toast";
import Toggle from "../../components/ui/Toggle";
import { fetchSettings, updateSettings } from "../../handlers/settingsHandlers";
import type { Settings } from "../../types/Settings";
import { logger } from "../../utils/logger";

const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [authGoogleEnabled, setAuthGoogleEnabled] = useState(true);
  const [authGithubEnabled, setAuthGithubEnabled] = useState(true);
  const [authMicrosoftEnabled, setAuthMicrosoftEnabled] = useState(true);
  const [authLocalEnabled, setAuthLocalEnabled] = useState(true);
  const [authSaving, setAuthSaving] = useState(false);

  // Edit Modal State
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [selectedRoleId, setSelectedRoleId] = useState("");

  useEffect(() => {
    const loadData = async () => {
      try {
        const [usersData, rolesData, settings] = await Promise.all([
          fetchUsers(),
          fetchRoles(),
          fetchSettings(),
        ]);
        setUsers(usersData);
        setRoles(rolesData);
        if (settings) {
          setAuthGoogleEnabled(settings.auth_google_enabled ?? true);
          setAuthGithubEnabled(settings.auth_github_enabled ?? true);
          setAuthMicrosoftEnabled(settings.auth_microsoft_enabled ?? true);
          setAuthLocalEnabled(settings.auth_local_enabled ?? true);
        }
      } catch (error) {
        logger.error("Failed to load data", error);
        toast.error("Failed to load users");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const handleEditUser = (user: AdminUser) => {
    setEditingUser(user);
    setSelectedRoleId(user.role_id);
    setIsEditModalOpen(true);
  };

  const handleSaveUser = async () => {
    if (!editingUser) return;
    try {
      setSaving(true);
      await updateUser(editingUser.id, {
        is_active: editingUser.is_active,
        role_id: selectedRoleId,
      });

      // Refresh list
      const usersData = await fetchUsers();
      setUsers(usersData);
      setIsEditModalOpen(false);
      setEditingUser(null);
      toast.success("User updated");
    } catch (error) {
      logger.error("Failed to update user", error);
      toast.error("Failed to update user");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAuth = async () => {
    try {
      setAuthSaving(true);
      const authPayload: Partial<Settings> = {
        auth_google_enabled: authGoogleEnabled,
        auth_github_enabled: authGithubEnabled,
        auth_microsoft_enabled: authMicrosoftEnabled,
        auth_local_enabled: authLocalEnabled,
      };
      await updateSettings(authPayload);
      toast.success("Authentication methods updated");
    } catch (error) {
      logger.error("Failed to save authentication settings", error);
      toast.error("Failed to save authentication settings");
    } finally {
      setAuthSaving(false);
    }
  };

  const handleDeleteUser = async (user: AdminUser) => {
    if (!window.confirm(`Delete user ${user.email}?`)) return;
    try {
      await deleteUser(user.id);
      const usersData = await fetchUsers();
      setUsers(usersData);
      toast.success("User deleted");
    } catch (error) {
      logger.error("Failed to delete user", error);
      toast.error("Failed to delete user");
    }
  };

  const filteredUsers = useMemo(
    () =>
      users.filter(
        (user) =>
          user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
          user.role_name.toLowerCase().includes(searchTerm.toLowerCase())
      ),
    [users, searchTerm]
  );

  const columns = [
    {
      header: "Email",
      accessor: "email" as keyof AdminUser,
      className: "text-xs md:text-sm text-gray-900",
      headerClassName: "text-xs md:text-sm font-medium text-gray-700",
    },
    {
      header: "Role",
      accessor: "role_name" as keyof AdminUser,
      className: "text-xs md:text-sm text-gray-900",
      headerClassName: "text-xs md:text-sm font-medium text-gray-700",
    },
    {
      header: "Actions",
      searchable: false,
      render: (user: AdminUser) => (
        <div className="flex flex-row gap-1 sm:gap-2">
          <Button
            variant="secondary"
            className="bg-gray-400 text-white hover:bg-gray-500 text-xs md:text-sm px-2 py-1 w-full sm:w-auto"
            onClick={() => handleEditUser(user)}
          >
            EDIT
          </Button>
          <Button
            variant="secondary"
            className="bg-red-500 text-white hover:bg-red-600 text-xs md:text-sm px-2 py-1 w-full sm:w-auto"
            onClick={() => handleDeleteUser(user)}
          >
            DELETE
          </Button>
        </div>
      ),
      headerClassName: "text-xs md:text-sm font-medium text-gray-700",
    },
  ];

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="Authentication and User Management"
        description="Manage authentication methods, users, roles, and access."
        status={loading ? <span className="text-sm text-gray-500">Loading…</span> : null}
      />

      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Authentication Methods</h3>
            <p className="text-xs text-gray-600">Toggle available login providers for the org.</p>
          </div>
          <Button variant="primary" onClick={handleSaveAuth} disabled={authSaving}>
            {authSaving ? "Saving…" : "Save"}
          </Button>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-900">Basic Authentication</span>
            <Toggle
              enabled={authLocalEnabled}
              onChange={setAuthLocalEnabled}
              id="authLocalToggle"
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-900">Google Authentication</span>
            <Toggle
              enabled={authGoogleEnabled}
              onChange={setAuthGoogleEnabled}
              id="authGoogleToggle"
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-900">GitHub Authentication</span>
            <Toggle
              enabled={authGithubEnabled}
              onChange={setAuthGithubEnabled}
              id="authGithubToggle"
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-900">Microsoft Authentication</span>
            <Toggle
              enabled={authMicrosoftEnabled}
              onChange={setAuthMicrosoftEnabled}
              id="authMicrosoftToggle"
            />
          </div>
        </div>
      </section>

      <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
        <input
          type="search"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search by email or role"
          className="w-full sm:max-w-xs rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-gray-400 focus:outline-none focus:ring-0"
        />
        <div className="text-xs text-gray-500">{filteredUsers.length} users</div>
      </div>

      <div className="overflow-x-auto bg-white rounded-lg border border-gray-200 shadow-sm">
        {filteredUsers.length === 0 && !loading ? (
          <div className="p-4 text-sm text-gray-600">No users match this search.</div>
        ) : (
          <ConfigurableTable
            columns={columns}
            data={filteredUsers}
            keyExtractor={(user) => user.id}
            tableClassName="min-w-full"
            headerRowClassName="bg-gray-50 sticky top-0"
            rowClassName="bg-white border-t border-gray-200 hover:bg-gray-50"
          />
        )}
      </div>

      {isEditModalOpen && editingUser && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 px-4">
          <div className="bg-white p-6 rounded-lg shadow-xl w-full max-w-md border border-gray-200">
            <div className="flex items-start justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Edit User</h2>
              <Button
                variant="secondary"
                className="bg-gray-200 text-gray-800 hover:bg-gray-300 px-3 py-1"
                onClick={() => setIsEditModalOpen(false)}
              >
                Close
              </Button>
            </div>
            <p className="text-sm text-gray-600 mb-4 truncate">{editingUser.email}</p>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
              <Dropdown
                options={roles.map((r) => ({ label: r.name, value: r.id }))}
                value={selectedRoleId}
                onChange={setSelectedRoleId}
                placeholder="Select Role"
              />
            </div>

            <div className="flex justify-end gap-3">
              <Button
                variant="secondary"
                onClick={() => setIsEditModalOpen(false)}
                className="bg-gray-200 text-gray-800 hover:bg-gray-300"
              >
                Cancel
              </Button>
              <Button variant="primary" onClick={handleSaveUser} disabled={saving}>
                {saving ? "Saving…" : "Save Changes"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
