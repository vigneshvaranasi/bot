import { useEffect, useState } from "react";
import SettingsHeader from "../../components/settings/SettingsHeader";
import { Button } from "../../components/ui/Button";
import { ConfigurableTable } from "../../components/ui/Table";
import { ConfirmModal } from "../../components/ui/Modal";
import {
  fetchRoles,
  deleteRole,
  createRole,
  updateRole,
  fetchPermissionSets,
} from "../../handlers/permissionHandlers";
import type {
  Role,
  RoleCreate,
  RoleUpdate,
  PermissionSet,
} from "../../types/Permission";
import { toast } from "react-hot-toast";
import { logger } from "../../utils/logger";
import { usePermissions } from "../../hooks/usePermissions";
import { PERMISSIONS } from "../../types/Permission";

// ==================== Role Edit Modal ====================

type RoleEditModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: RoleCreate | RoleUpdate, id?: string) => Promise<void>;
  role?: Role | null;
  allPermissionSets: PermissionSet[];
  isLoading: boolean;
};

const RoleEditModal = ({
  isOpen,
  onClose,
  onSave,
  role,
  allPermissionSets,
  isLoading,
}: RoleEditModalProps) => {
  const isEdit = !!role;
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPermissionSets, setSelectedPermissionSets] = useState<string[]>([]);

  useEffect(() => {
    if (role) {
      setName(role.name);
      setDescription(role.description || "");
      setSelectedPermissionSets(role.permission_sets.map((ps) => ps.code));
    } else {
      setName("");
      setDescription("");
      setSelectedPermissionSets([]);
    }
  }, [role, isOpen]);

  const handleTogglePermissionSet = (code: string) => {
    setSelectedPermissionSets((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error("Name is required");
      return;
    }
    if (selectedPermissionSets.length === 0) {
      toast.error("At least one permission set is required");
      return;
    }

    if (isEdit) {
      const data: RoleUpdate = {
        name: name.trim(),
        description: description.trim() || undefined,
        permission_set_codes: selectedPermissionSets,
      };
      await onSave(data, role.id);
    } else {
      const data: RoleCreate = {
        name: name.trim(),
        description: description.trim() || undefined,
        permission_set_codes: selectedPermissionSets,
      };
      await onSave(data);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEdit ? "Edit Role" : "Create Role"}
          </h2>
        </div>

        <div className="p-4 overflow-y-auto flex-1 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
              placeholder="e.g., Report Manager"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
              placeholder="Optional description of this role's purpose"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Permission Sets <span className="text-red-500">*</span>
              <span className="font-normal text-gray-500 ml-2">
                ({selectedPermissionSets.length} selected)
              </span>
            </label>
            <div className="border border-gray-200 rounded-lg max-h-64 overflow-y-auto">
              {allPermissionSets.length === 0 ? (
                <div className="p-4 text-sm text-gray-500 text-center">
                  No permission sets available
                </div>
              ) : (
                allPermissionSets.map((ps) => (
                  <label
                    key={ps.id}
                    className="flex items-start gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-b-0"
                  >
                    <input
                      type="checkbox"
                      checked={selectedPermissionSets.includes(ps.code)}
                      onChange={() => handleTogglePermissionSet(ps.code)}
                      className="w-4 h-4 mt-0.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900">
                        {ps.name}
                      </div>
                      {ps.description && (
                        <div className="text-xs text-gray-500">
                          {ps.description}
                        </div>
                      )}
                      <div className="flex flex-wrap gap-1 mt-1">
                        {ps.permissions.slice(0, 3).map((p) => (
                          <span
                            key={p.code}
                            className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs"
                          >
                            {p.code}
                          </span>
                        ))}
                        {ps.permissions.length > 3 && (
                          <span className="px-1.5 py-0.5 bg-gray-200 text-gray-600 rounded text-xs">
                            +{ps.permissions.length - 3} more
                          </span>
                        )}
                      </div>
                    </div>
                  </label>
                ))
              )}
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-gray-200 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSubmit} disabled={isLoading}>
            {isLoading ? "Saving..." : isEdit ? "Save Changes" : "Create"}
          </Button>
        </div>
      </div>
    </div>
  );
};

// ==================== Role Management Page ====================

const RoleManagement = () => {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissionSets, setPermissionSets] = useState<PermissionSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { hasPermission } = usePermissions();

  // Edit/Create modal state
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [saving, setSaving] = useState(false);

  // Delete confirmation modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [roleToDelete, setRoleToDelete] = useState<Role | null>(null);
  const [deleting, setDeleting] = useState(false);

  const canCreate = hasPermission(PERMISSIONS.ROLE_CREATE);
  const canEdit = hasPermission(PERMISSIONS.ROLE_EDIT);
  const canDelete = hasPermission(PERMISSIONS.ROLE_DELETE);
  const canViewPermissionSets = hasPermission(PERMISSIONS.PERMISSION_SET_VIEW);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Always fetch roles, conditionally fetch permission sets
      const rolesData = await fetchRoles();
      setRoles(rolesData);

      // Only fetch permission sets if user has permission
      if (canViewPermissionSets) {
        const permissionSetsData = await fetchPermissionSets();
        setPermissionSets(permissionSetsData);
      } else {
        setPermissionSets([]);
      }
    } catch (err) {
      logger.error("Error fetching roles", err);
      setError("Failed to load roles");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreateModal = () => {
    setEditingRole(null);
    setEditModalOpen(true);
  };

  const handleOpenEditModal = (role: Role) => {
    setEditingRole(role);
    setEditModalOpen(true);
  };

  const handleCloseModal = () => {
    setEditModalOpen(false);
    setEditingRole(null);
  };

  const handleSave = async (data: RoleCreate | RoleUpdate, id?: string) => {
    try {
      setSaving(true);
      if (id) {
        await updateRole(id, data as RoleUpdate);
        toast.success("Role updated successfully");
      } else {
        await createRole(data as RoleCreate);
        toast.success("Role created successfully");
      }
      await loadData();
      handleCloseModal();
    } catch (err: unknown) {
      logger.error("Error saving role", err);
      const msg = err instanceof Error ? err.message : null;
      toast.error(msg || (id ? "Failed to update role" : "Failed to create role"));
    } finally {
      setSaving(false);
    }
  };

  const openDeleteModal = (role: Role) => {
    setRoleToDelete(role);
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!roleToDelete) return;

    try {
      setDeleting(true);
      await deleteRole(roleToDelete.id);
      toast.success("Role deleted successfully");
      await loadData();
    } catch (err: unknown) {
      logger.error("Error deleting role", err);
      const msg = err instanceof Error ? err.message : null;
      toast.error(msg || "Failed to delete role");
    } finally {
      setDeleting(false);
      setDeleteModalOpen(false);
      setRoleToDelete(null);
    }
  };

  const columns = [
    {
      header: "Name",
      accessor: "name" as keyof Role,
      className: "text-sm text-gray-900 font-medium",
      headerClassName: "text-sm font-medium text-gray-700",
    },
    {
      header: "Description",
      accessor: "description" as keyof Role,
      className: "text-sm text-gray-600",
      headerClassName: "text-sm font-medium text-gray-700",
      render: (role: Role) => role.description || "-",
    },
    {
      header: "Permission Sets",
      headerClassName: "text-sm font-medium text-gray-700",
      className: "text-sm text-gray-600",
      render: (role: Role) => (
        <div className="flex flex-wrap gap-1">
          {role.permission_sets.slice(0, 3).map((ps) => (
            <span
              key={ps.id}
              className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs"
            >
              {ps.name}
            </span>
          ))}
          {role.permission_sets.length > 3 && (
            <span className="px-2 py-0.5 bg-gray-200 text-gray-600 rounded text-xs">
              +{role.permission_sets.length - 3} more
            </span>
          )}
          {role.permission_sets.length === 0 && "-"}
        </div>
      ),
    },
    ...((canEdit && canViewPermissionSets) || canDelete
      ? [
          {
            header: "Actions",
            headerClassName: "text-sm font-medium text-gray-700",
            render: (role: Role) => (
              <div className="flex gap-2">
                {canEdit && canViewPermissionSets && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleOpenEditModal(role)}
                  >
                    Edit
                  </Button>
                )}
                {canDelete && (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => openDeleteModal(role)}
                  >
                    Delete
                  </Button>
                )}
              </div>
            ),
          },
        ]
      : []),
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <SettingsHeader
          title="Roles & Permissions"
          description="Manage roles and their permission sets."
        />
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-gray-200 rounded w-1/4"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="Roles & Permissions"
        description="Manage roles and their permission sets."
      />

      {error && (
        <div className="p-3 bg-red-50 text-sm text-red-700 border border-red-200 rounded">
          {error}
        </div>
      )}

      {!canViewPermissionSets && (canCreate || canEdit) && (
        <div className="p-3 bg-yellow-50 text-sm text-yellow-800 border border-yellow-200 rounded">
          You have role management permissions but cannot view permission sets.
          Create/Edit functionality is limited. Contact an administrator to grant you the
          "permission_set.view" permission.
        </div>
      )}

      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Roles</h3>
            <p className="text-xs text-gray-600">
              {roles.length} role(s) configured
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button variant="secondary" size="sm" onClick={loadData} disabled={loading}>
              Refresh
            </Button>
            {canCreate && canViewPermissionSets && (
              <Button variant="primary" size="sm" onClick={handleOpenCreateModal}>
                Add Role
              </Button>
            )}
          </div>
        </div>

        {roles.length === 0 ? (
          <div className="p-6 text-center text-gray-500 text-sm rounded-lg bg-gray-50 border border-gray-200">
            No roles configured.
          </div>
        ) : (
          <div className="overflow-x-auto bg-white rounded-lg shadow-sm">
            <ConfigurableTable
              columns={columns}
              data={roles}
              keyExtractor={(role) => role.id}
              headerRowClassName="bg-gray-50"
              rowClassName="border-t border-gray-200 hover:bg-gray-50"
            />
          </div>
        )}
      </section>

      {/* <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">
            Permission Hierarchy
          </h3>
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-gray-600">
          <div className="flex items-center gap-2">
            <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">
              Permissions
            </span>
            <span>&rarr;</span>
            <span className="px-2 py-1 bg-green-100 text-green-700 rounded">
              Permission Sets
            </span>
            <span>&rarr;</span>
            <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded">
              Roles
            </span>
            <span>&rarr;</span>
            <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded">
              Users
            </span>
          </div>
        </div>
        <p className="text-xs text-gray-500">
          Users can have multiple roles. Their effective permissions are the
          union of all permissions from all assigned roles.
        </p>
      </section> */}

      {/* Edit/Create Modal */}
      <RoleEditModal
        isOpen={editModalOpen}
        onClose={handleCloseModal}
        onSave={handleSave}
        role={editingRole}
        allPermissionSets={permissionSets}
        isLoading={saving}
      />

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setRoleToDelete(null);
        }}
        onConfirm={handleConfirmDelete}
        title="Delete Role"
        message={`Are you sure you want to delete the role "${roleToDelete?.name}"? Users with this role will lose its permissions.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        confirmVariant="danger"
        isLoading={deleting}
      />
    </div>
  );
};

export default RoleManagement;
