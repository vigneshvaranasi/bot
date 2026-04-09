import React, { useEffect, useState, useCallback, useMemo } from "react";
import { Button } from "../../components/ui/Button";
import { ConfigurableTable } from "../../components/ui/Table";
import SettingsHeader from "../../components/settings/SettingsHeader";
import {
  fetchUsers,
  deleteUser,
  updateUserRoles,
  type AdminUser,
  type Role,
} from "../../handlers/adminHandlers";
import { toast } from "react-hot-toast";
import Toggle from "../../components/ui/Toggle";
import { fetchAuthSettings, updateAuthSettings } from "../../handlers/settingsHandlers";
import type { AuthSettings } from "../../types/Settings";
import { logger } from "../../utils/logger";
import { SkeletonUserManagement, SkeletonToggle } from "../../components/ui/Skeleton";
import { ConfirmModal } from "../../components/ui/Modal";
import InfoHint from "../../components/ui/InfoHint";
import { Pagination, DEFAULT_PAGE_SIZE_OPTIONS } from "../../components/ui/Pagination";
import { useDelayedLoading } from "../../hooks/useDelayedLoading";
import { usePermissions } from "../../hooks/usePermissions";
import { useAuthContext } from "../../hooks/useAuthContext";
import {
  PERMISSIONS,
  PERMISSION_CATEGORIES,
  type Permission,
  type PermissionSet,
  type PermissionCategory,
} from "../../types/Permission";
import {
  fetchPermissions,
  fetchPermissionSets,
  fetchRoles,
  fetchUserDirectPermissions,
  fetchUserDirectPermissionSets,
  updateUserDirectPermissions,
  updateUserDirectPermissionSets,
} from "../../handlers/permissionHandlers";

const DEFAULT_PAGE_SIZE = 10;

const UserManagement: React.FC = () => {
  const { hasPermission, refreshPermissions } = usePermissions();
  const { user: currentUser } = useAuthContext();
  const canEditUser = hasPermission(PERMISSIONS.USER_EDIT);
  const canDeleteUser = hasPermission(PERMISSIONS.USER_DELETE);
  const canEditAuth = hasPermission(PERMISSIONS.AUTH_EDIT);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [totalUsers, setTotalUsers] = useState(0);
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Delayed loading - only show skeleton after 150ms
  const showInitialLoading = useDelayedLoading(loading);
  const showUsersLoading = useDelayedLoading(loadingUsers);

  const [authGoogleEnabled, setAuthGoogleEnabled] = useState<boolean | undefined>(undefined);
  const [authGithubEnabled, setAuthGithubEnabled] = useState<boolean | undefined>(undefined);
  const [authMicrosoftEnabled, setAuthMicrosoftEnabled] = useState<boolean | undefined>(undefined);
  const [authLocalEnabled, setAuthLocalEnabled] = useState<boolean | undefined>(undefined);
  const [authSaving, setAuthSaving] = useState(false);

  // Delete user modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<AdminUser | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Check if auth settings have loaded (to avoid toggle flickering)
  const authSettingsLoaded = authGoogleEnabled !== undefined;

  // Edit Modal State
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<"roles" | "permissionSets" | "permissions">("roles");

  // Direct permissions state
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  const [allPermissionSets, setAllPermissionSets] = useState<PermissionSet[]>([]);
  const [selectedDirectPermissionIds, setSelectedDirectPermissionIds] = useState<string[]>([]);
  const [selectedDirectPermissionSetIds, setSelectedDirectPermissionSetIds] = useState<string[]>([]);
  const [loadingDirectPerms, setLoadingDirectPerms] = useState(false);

  const loadUsers = useCallback(async (page: number, size: number, search?: string) => {
    setLoadingUsers(true);
    try {
      const offset = (page - 1) * size;
      const response = await fetchUsers(size, offset, search);
      setUsers(response.users);
      setTotalUsers(response.total);
    } catch (error) {
      logger.error("Failed to load users", error);
      toast.error("Failed to load users");
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [rolesData, authResponse] = await Promise.all([
          fetchRoles(),
          fetchAuthSettings(),
        ]);
        setRoles(rolesData);
        // Set auth settings with defaults - even if no settings in DB yet
        const authSettings = authResponse?.settings;
        setAuthGoogleEnabled(authSettings?.auth_google_enabled ?? true);
        setAuthGithubEnabled(authSettings?.auth_github_enabled ?? true);
        setAuthMicrosoftEnabled(authSettings?.auth_microsoft_enabled ?? true);
        setAuthLocalEnabled(authSettings?.auth_local_enabled ?? true);
        // Load initial users
        await loadUsers(1, pageSize);
      } catch (error) {
        logger.error("Failed to load data", error);
        toast.error("Failed to load users");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [loadUsers, pageSize]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      setCurrentPage(1);
      loadUsers(1, pageSize, searchTerm || undefined);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchTerm, loadUsers, pageSize]);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    loadUsers(page, pageSize, searchTerm || undefined);
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    setCurrentPage(1); // Reset to page 1 when changing page size
  };

  const handleEditUser = async (user: AdminUser) => {
    setEditingUser(user);
    // Initialize with current roles
    const roleIds = user.roles.map((r) => r.role_id);
    setSelectedRoleIds(roleIds);
    setActiveTab("roles");
    setIsEditModalOpen(true);

    // Load permissions data for the modal
    setLoadingDirectPerms(true);
    try {
      const [permsData, permSetsData, userDirectPerms, userDirectSets] = await Promise.all([
        allPermissions.length === 0 ? fetchPermissions() : Promise.resolve(allPermissions),
        allPermissionSets.length === 0 ? fetchPermissionSets() : Promise.resolve(allPermissionSets),
        fetchUserDirectPermissions(user.id),
        fetchUserDirectPermissionSets(user.id),
      ]);

      if (allPermissions.length === 0) setAllPermissions(permsData);
      if (allPermissionSets.length === 0) setAllPermissionSets(permSetsData);

      setSelectedDirectPermissionIds(userDirectPerms.direct_permissions.map((p) => p.permission_id));
      setSelectedDirectPermissionSetIds(userDirectSets.direct_permission_sets.map((s) => s.permission_set_id));
    } catch (error) {
      logger.error("Failed to load permission data", error);
      toast.error("Failed to load permission data");
    } finally {
      setLoadingDirectPerms(false);
    }
  };

  const handleToggleRole = (roleId: string) => {
    setSelectedRoleIds((prev) =>
      prev.includes(roleId)
        ? prev.filter((id) => id !== roleId)
        : [...prev, roleId]
    );
  };

  const handleToggleDirectPermissionSet = (setId: string) => {
    setSelectedDirectPermissionSetIds((prev) =>
      prev.includes(setId)
        ? prev.filter((id) => id !== setId)
        : [...prev, setId]
    );
  };

  const handleToggleDirectPermission = (permId: string) => {
    setSelectedDirectPermissionIds((prev) =>
      prev.includes(permId)
        ? prev.filter((id) => id !== permId)
        : [...prev, permId]
    );
  };

  // Group permissions by category for the UI
  const permissionsByCategory = useMemo(() => {
    const grouped: Record<string, Permission[]> = {};
    for (const perm of allPermissions) {
      if (!grouped[perm.category]) {
        grouped[perm.category] = [];
      }
      grouped[perm.category].push(perm);
    }
    return grouped;
  }, [allPermissions]);

  // Handle toggling all permissions in a category
  const handleToggleCategory = (category: string) => {
    const categoryPerms = permissionsByCategory[category] || [];
    const categoryPermIds = categoryPerms.map((p) => p.id);
    const allSelected = categoryPermIds.every((id) => selectedDirectPermissionIds.includes(id));

    if (allSelected) {
      // Deselect all in this category
      setSelectedDirectPermissionIds((prev) =>
        prev.filter((id) => !categoryPermIds.includes(id))
      );
    } else {
      // Select all in this category
      setSelectedDirectPermissionIds((prev) => {
        const newIds = new Set(prev);
        categoryPermIds.forEach((id) => newIds.add(id));
        return Array.from(newIds);
      });
    }
  };

  // Check if all permissions in a category are selected
  const isCategoryFullySelected = (category: string) => {
    const categoryPerms = permissionsByCategory[category] || [];
    return categoryPerms.length > 0 && categoryPerms.every((p) => selectedDirectPermissionIds.includes(p.id));
  };

  // Check if some but not all permissions in a category are selected
  const isCategoryPartiallySelected = (category: string) => {
    const categoryPerms = permissionsByCategory[category] || [];
    const selectedCount = categoryPerms.filter((p) => selectedDirectPermissionIds.includes(p.id)).length;
    return selectedCount > 0 && selectedCount < categoryPerms.length;
  };

  const handleSaveUser = async () => {
    if (!editingUser) return;
    if (selectedRoleIds.length === 0) {
      toast.error("User must have at least one role");
      return;
    }
    try {
      setSaving(true);
      // Save roles, direct permission sets, and direct permissions in parallel
      await Promise.all([
        updateUserRoles(editingUser.id, selectedRoleIds),
        updateUserDirectPermissionSets(editingUser.id, selectedDirectPermissionSetIds),
        updateUserDirectPermissions(editingUser.id, selectedDirectPermissionIds),
      ]);

      // If editing the current user, refresh their permissions
      if (currentUser && editingUser.id === currentUser.id) {
        await refreshPermissions();
      }

      // Refresh list - stay on current page
      await loadUsers(currentPage, pageSize, searchTerm || undefined);
      setIsEditModalOpen(false);
      setEditingUser(null);
      toast.success("User permissions updated");
    } catch (error) {
      logger.error("Failed to update user permissions", error);
      toast.error("Failed to update user permissions");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAuth = async () => {
    try {
      setAuthSaving(true);
      const authPayload: Partial<AuthSettings> = {
        auth_google_enabled: authGoogleEnabled ?? true,
        auth_github_enabled: authGithubEnabled ?? true,
        auth_microsoft_enabled: authMicrosoftEnabled ?? true,
        auth_local_enabled: authLocalEnabled ?? true,
      };
      await updateAuthSettings(authPayload);
      toast.success("Authentication methods updated");
    } catch (error) {
      logger.error("Failed to save authentication settings", error);
      toast.error("Failed to save authentication settings");
    } finally {
      setAuthSaving(false);
    }
  };

  const openDeleteModal = (user: AdminUser) => {
    setUserToDelete(user);
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!userToDelete) return;
    setDeleting(true);
    try {
      await deleteUser(userToDelete.id);
      // Refresh list - go back to page 1 if current page would be empty
      const newPage = users.length === 1 && currentPage > 1 ? currentPage - 1 : currentPage;
      setCurrentPage(newPage);
      await loadUsers(newPage, pageSize, searchTerm || undefined);
      toast.success("User deleted");
    } catch (error) {
      logger.error("Failed to delete user", error);
      toast.error("Failed to delete user");
    } finally {
      setDeleting(false);
      setDeleteModalOpen(false);
      setUserToDelete(null);
    }
  };

  const totalPages = Math.ceil(totalUsers / pageSize);

  const columns = [
    {
      header: "Email",
      accessor: "email" as keyof AdminUser,
      className: "text-xs md:text-sm text-text-primary",
      headerClassName: "text-xs md:text-sm font-medium text-text-secondary",
    },
    {
      header: "Roles",
      headerClassName: "text-xs md:text-sm font-medium text-text-secondary",
      className: "text-xs md:text-sm text-text-primary",
      render: (user: AdminUser) => (
        <div className="flex flex-wrap gap-1">
          {user.roles.length > 0 ? (
            user.roles.map((role) => (
              <span
                key={role.role_id}
                className="px-2 py-0.5 bg-info-subtle text-info-text rounded text-xs"
              >
                {role.role_name}
              </span>
            ))
          ) : (
            <span className="text-text-tertiary text-xs">No roles</span>
          )}
        </div>
      ),
    },
    {
      header: "Actions",
      searchable: false,
      render: (user: AdminUser) => (
        <div className="flex flex-row gap-1 sm:gap-2">
          {canEditUser && (
            <Button
              variant="ghost"
              size="sm"
              className="w-full sm:w-auto"
              onClick={() => handleEditUser(user)}
            >
              EDIT
            </Button>
          )}
          {canDeleteUser && (
            <Button
              variant="danger"
              size="sm"
              className="w-full sm:w-auto"
              onClick={() => openDeleteModal(user)}
            >
              DELETE
            </Button>
          )}
          {!canEditUser && !canDeleteUser && (
            <span className="text-xs text-text-tertiary">View only</span>
          )}
        </div>
      ),
      headerClassName: "text-xs md:text-sm font-medium text-text-secondary",
    },
  ];

  // Show skeleton only when initial load takes longer than threshold
  if (showInitialLoading) {
    return (
      <div className="space-y-6">
        <SettingsHeader
          title="Authentication and User Management"
          description="Manage authentication methods, users, roles, and access."
        />
        <SkeletonUserManagement />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="Authentication and User Management"
        description="Manage authentication methods, users, roles, and access."
      />

      <section className="border border-border-default rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-1">
              <h3 className="text-sm font-semibold text-text-primary">Authentication Methods</h3>
              <InfoHint text="Toggling a provider off prevents all users from creating new login sessions with that method. Existing sessions aren't affected." />
            </div>
            <p className="text-xs text-text-secondary">Toggle available login providers for the org.</p>
          </div>
          {canEditAuth && (
            <Button variant="blue" size="sm" onClick={handleSaveAuth} disabled={authSaving}>
              {authSaving ? "Saving…" : "Save"}
            </Button>
          )}
        </div>
        <div className="space-y-3">
          {authSettingsLoaded ? (
            <>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-primary">Basic Authentication</span>
                <Toggle
                  enabled={authLocalEnabled}
                  onChange={canEditAuth ? setAuthLocalEnabled : undefined}
                  id="authLocalToggle"
                  disabled={!canEditAuth}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-primary">Google Authentication</span>
                <Toggle
                  enabled={authGoogleEnabled}
                  onChange={canEditAuth ? setAuthGoogleEnabled : undefined}
                  id="authGoogleToggle"
                  disabled={!canEditAuth}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-primary">GitHub Authentication</span>
                <Toggle
                  enabled={authGithubEnabled}
                  onChange={canEditAuth ? setAuthGithubEnabled : undefined}
                  id="authGithubToggle"
                  disabled={!canEditAuth}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-text-primary">Microsoft Authentication</span>
                <Toggle
                  enabled={authMicrosoftEnabled}
                  onChange={canEditAuth ? setAuthMicrosoftEnabled : undefined}
                  id="authMicrosoftToggle"
                  disabled={!canEditAuth}
                />
              </div>
            </>
          ) : (
            <>
              <SkeletonToggle labelWidth={150} />
              <SkeletonToggle labelWidth={170} />
              <SkeletonToggle labelWidth={160} />
              <SkeletonToggle labelWidth={180} />
            </>
          )}
        </div>
      </section>

      <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
        <input
          type="search"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search by email"
          className="w-full sm:max-w-xs rounded-md border border-border-default px-3 py-2 text-sm focus:border-border-strong focus:outline-none focus:ring-0"
        />
        <div className="text-xs text-text-secondary">
          {showUsersLoading ? "Loading..." : `${totalUsers} users`}
        </div>
      </div>

      <div className="overflow-x-auto bg-surface-primary rounded-lg border border-border-default shadow-sm">
        {users.length === 0 && !loading && !loadingUsers ? (
          <div className="p-4 text-sm text-text-secondary">No users match this search.</div>
        ) : showUsersLoading && users.length === 0 ? (
          <div className="p-4 text-sm text-text-tertiary text-center">Loading users...</div>
        ) : (
          <ConfigurableTable
            columns={columns}
            data={users}
            keyExtractor={(user) => user.id}
            tableClassName="min-w-full"
            headerRowClassName="bg-surface-secondary sticky top-0"
            rowClassName="bg-surface-primary border-t border-border-default hover:bg-surface-secondary"
          />
        )}
      </div>

      {/* Pagination */}
      <Pagination
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={handlePageChange}
        totalItems={totalUsers}
        pageSize={pageSize}
        onPageSizeChange={handlePageSizeChange}
        pageSizeOptions={DEFAULT_PAGE_SIZE_OPTIONS}
        disabled={loadingUsers}
      />

      {isEditModalOpen && editingUser && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 px-4">
          <div className="bg-surface-primary p-6 rounded-lg shadow-xl w-full max-w-2xl border border-border-default max-h-[90vh] flex flex-col">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-text-primary">Edit User Permissions</h2>
                <p className="text-sm text-text-secondary truncate">{editingUser.email}</p>
              </div>
              <Button
                variant="secondary"
                className="bg-surface-hover text-text-primary hover:bg-surface-tertiary px-3 py-1"
                onClick={() => setIsEditModalOpen(false)}
              >
                Close
              </Button>
            </div>

            {/* Tabs */}
            <div className="flex overflow-x-auto border-b border-border-default mb-4">
              <button
                onClick={() => setActiveTab("roles")}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === "roles"
                    ? "border-accent-blue text-accent-blue"
                    : "border-transparent text-text-secondary hover:text-text-secondary"
                }`}
              >
                Roles ({selectedRoleIds.length})
              </button>
              <button
                onClick={() => setActiveTab("permissionSets")}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === "permissionSets"
                    ? "border-accent-blue text-accent-blue"
                    : "border-transparent text-text-secondary hover:text-text-secondary"
                }`}
              >
                Direct Sets ({selectedDirectPermissionSetIds.length})
              </button>
              <button
                onClick={() => setActiveTab("permissions")}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === "permissions"
                    ? "border-accent-blue text-accent-blue"
                    : "border-transparent text-text-secondary hover:text-text-secondary"
                }`}
              >
                Direct Perms ({selectedDirectPermissionIds.length})
              </button>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto min-h-0">
              {loadingDirectPerms ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-accent-blue"></div>
                  <span className="ml-2 text-sm text-text-secondary">Loading permissions...</span>
                </div>
              ) : (
                <>
                  {/* Roles Tab */}
                  {activeTab === "roles" && (
                    <div>
                      <p className="text-xs text-text-secondary mb-2">
                        Assign roles to this user. Roles grant permission sets.
                      </p>
                      <div className="border border-border-default rounded-lg max-h-72 overflow-y-auto">
                        {roles.map((role) => (
                          <label
                            key={role.id}
                            className="flex items-center gap-3 px-3 py-2 hover:bg-surface-secondary cursor-pointer border-b border-border-subtle last:border-b-0"
                          >
                            <input
                              type="checkbox"
                              checked={selectedRoleIds.includes(role.id)}
                              onChange={() => handleToggleRole(role.id)}
                              className="w-4 h-4 rounded border-border-strong text-accent-blue focus:ring-accent-blue"
                            />
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-medium text-text-primary">{role.name}</div>
                              {role.description && (
                                <div className="text-xs text-text-secondary truncate">{role.description}</div>
                              )}
                            </div>
                          </label>
                        ))}
                      </div>
                      {selectedRoleIds.length === 0 && (
                        <p className="text-xs text-danger-text mt-1">At least one role is required</p>
                      )}
                    </div>
                  )}

                  {/* Permission Sets Tab */}
                  {activeTab === "permissionSets" && (
                    <div>
                      <p className="text-xs text-text-secondary mb-2">
                        Assign permission sets directly (bypasses roles).
                      </p>
                      <div className="border border-border-default rounded-lg max-h-72 overflow-y-auto">
                        {allPermissionSets.length === 0 ? (
                          <div className="px-3 py-4 text-sm text-text-secondary text-center">
                            No permission sets available
                          </div>
                        ) : (
                          allPermissionSets.map((permSet) => (
                            <label
                              key={permSet.id}
                              className="flex items-center gap-3 px-3 py-2 hover:bg-surface-secondary cursor-pointer border-b border-border-subtle last:border-b-0"
                            >
                              <input
                                type="checkbox"
                                checked={selectedDirectPermissionSetIds.includes(permSet.id)}
                                onChange={() => handleToggleDirectPermissionSet(permSet.id)}
                                className="w-4 h-4 rounded border-border-strong text-accent-blue focus:ring-accent-blue"
                              />
                              <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-text-primary">{permSet.name}</div>
                                {permSet.description && (
                                  <div className="text-xs text-text-secondary truncate">{permSet.description}</div>
                                )}
                                <div className="text-xs text-text-tertiary mt-0.5">
                                  {permSet.permissions.length} permission{permSet.permissions.length !== 1 ? "s" : ""}
                                </div>
                              </div>
                            </label>
                          ))
                        )}
                      </div>
                    </div>
                  )}

                  {/* Permissions Tab */}
                  {activeTab === "permissions" && (
                    <div>
                      <p className="text-xs text-text-secondary mb-2">
                        Assign individual permissions directly (bypasses roles and sets).
                      </p>
                      <div className="border border-border-default rounded-lg max-h-72 overflow-y-auto">
                        {Object.keys(permissionsByCategory).length === 0 ? (
                          <div className="px-3 py-4 text-sm text-text-secondary text-center">
                            No permissions available
                          </div>
                        ) : (
                          Object.entries(permissionsByCategory).map(([category, perms]) => (
                            <div key={category} className="border-b border-border-subtle last:border-b-0">
                              {/* Category Header */}
                              <label className="flex items-center gap-3 px-3 py-2 bg-surface-secondary cursor-pointer hover:bg-surface-tertiary">
                                <input
                                  type="checkbox"
                                  checked={isCategoryFullySelected(category)}
                                  ref={(el) => {
                                    if (el) el.indeterminate = isCategoryPartiallySelected(category);
                                  }}
                                  onChange={() => handleToggleCategory(category)}
                                  className="w-4 h-4 rounded border-border-strong text-success-text focus:ring-accent-blue"
                                />
                                <span className="text-sm font-medium text-text-secondary">
                                  {PERMISSION_CATEGORIES[category as PermissionCategory] || category}
                                </span>
                                <span className="text-xs text-text-tertiary">
                                  ({perms.filter((p) => selectedDirectPermissionIds.includes(p.id)).length}/{perms.length})
                                </span>
                              </label>
                              {/* Permissions in Category */}
                              <div className="pl-6">
                                {perms.map((perm) => (
                                  <label
                                    key={perm.id}
                                    className="flex items-center gap-3 px-3 py-1.5 hover:bg-surface-secondary cursor-pointer"
                                  >
                                    <input
                                      type="checkbox"
                                      checked={selectedDirectPermissionIds.includes(perm.id)}
                                      onChange={() => handleToggleDirectPermission(perm.id)}
                                      className="w-3.5 h-3.5 rounded border-border-strong text-success-text focus:ring-accent-blue"
                                    />
                                    <div className="flex-1 min-w-0">
                                      <div className="text-xs font-medium text-text-primary">{perm.name}</div>
                                      {perm.description && (
                                        <div className="text-xs text-text-tertiary truncate">{perm.description}</div>
                                      )}
                                    </div>
                                    <code className="text-xs text-text-tertiary bg-surface-tertiary px-1 rounded shrink-0 hidden sm:inline">
                                      {perm.code}
                                    </code>
                                  </label>
                                ))}
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-3 mt-4 pt-4 border-t border-border-default">
              <Button
                variant="secondary"
                onClick={() => setIsEditModalOpen(false)}
                className="bg-surface-hover text-text-primary hover:bg-surface-tertiary"
              >
                Cancel
              </Button>
              <Button
                variant="blue"
                onClick={handleSaveUser}
                disabled={saving || selectedRoleIds.length === 0 || loadingDirectPerms}
              >
                {saving ? "Saving…" : "Save Changes"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete User Confirmation Modal */}
      <ConfirmModal
        isOpen={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setUserToDelete(null);
        }}
        onConfirm={handleConfirmDelete}
        title="Delete User"
        message={`Are you sure you want to delete user ${userToDelete?.email}? This action cannot be undone.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        confirmVariant="danger"
        isLoading={deleting}
      />
    </div>
  );
};

export default UserManagement;
