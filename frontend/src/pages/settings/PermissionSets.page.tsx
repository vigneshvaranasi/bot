import { useEffect, useState, useMemo } from "react";
import SettingsHeader from "../../components/settings/SettingsHeader";
import { Button } from "../../components/ui/Button";
import { ConfigurableTable } from "../../components/ui/Table";
import { ConfirmModal } from "../../components/ui/Modal";
import {
  fetchPermissionSets,
  fetchPermissions,
  createPermissionSet,
  updatePermissionSet,
  deletePermissionSet,
} from "../../handlers/permissionHandlers";
import type {
  Permission,
  PermissionSet,
  PermissionSetCreate,
  PermissionSetUpdate,
} from "../../types/Permission";
import { PERMISSION_CATEGORIES, PERMISSIONS } from "../../types/Permission";
import { toast } from "react-hot-toast";
import { logger } from "../../utils/logger";
import { usePermissions } from "../../hooks/usePermissions";

type PermissionSetEditModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: PermissionSetCreate | PermissionSetUpdate, id?: string) => Promise<void>;
  permissionSet?: PermissionSet | null;
  allPermissions: Permission[];
  isLoading: boolean;
};

const PermissionSetEditModal = ({
  isOpen,
  onClose,
  onSave,
  permissionSet,
  allPermissions,
  isLoading,
}: PermissionSetEditModalProps) => {
  const isEdit = !!permissionSet;
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);

  useEffect(() => {
    if (permissionSet) {
      setName(permissionSet.name);
      setCode(permissionSet.code);
      setDescription(permissionSet.description || "");
      setSelectedPermissions(permissionSet.permissions.map((p) => p.code));
    } else {
      setName("");
      setCode("");
      setDescription("");
      setSelectedPermissions([]);
    }
  }, [permissionSet, isOpen]);

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

  const handleTogglePermission = (code: string) => {
    setSelectedPermissions((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const handleToggleCategory = (category: string) => {
    const categoryPerms = permissionsByCategory[category]?.map((p) => p.code) || [];
    const allSelected = categoryPerms.every((c) => selectedPermissions.includes(c));

    if (allSelected) {
      setSelectedPermissions((prev) => prev.filter((c) => !categoryPerms.includes(c)));
    } else {
      setSelectedPermissions((prev) => [...new Set([...prev, ...categoryPerms])]);
    }
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      toast.error("Name is required");
      return;
    }
    if (!isEdit && !code.trim()) {
      toast.error("Code is required");
      return;
    }
    if (selectedPermissions.length === 0) {
      toast.error("At least one permission is required");
      return;
    }

    if (isEdit) {
      const data: PermissionSetUpdate = {
        name: name.trim(),
        description: description.trim() || undefined,
        permission_codes: selectedPermissions,
      };
      await onSave(data, permissionSet.id);
    } else {
      const data: PermissionSetCreate = {
        code: code.trim(),
        name: name.trim(),
        description: description.trim() || undefined,
        permission_codes: selectedPermissions,
      };
      await onSave(data);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEdit ? "Edit Permission Set" : "Create Permission Set"}
          </h2>
        </div>

        <div className="p-4 overflow-y-auto flex-1 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
                placeholder="e.g., Report Viewer"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Code {!isEdit && <span className="text-red-500">*</span>}
              </label>
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                disabled={isEdit}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-gray-400 disabled:bg-gray-100 disabled:text-gray-500"
                placeholder="e.g., report_viewer"
              />
              {isEdit && (
                <p className="text-xs text-gray-500 mt-1">Code cannot be changed</p>
              )}
            </div>
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
              placeholder="Optional description"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Permissions <span className="text-red-500">*</span>
              <span className="font-normal text-gray-500 ml-2">
                ({selectedPermissions.length} selected)
              </span>
            </label>
            <div className="border border-gray-200 rounded-lg max-h-64 overflow-y-auto">
              {Object.entries(permissionsByCategory).map(([category, perms]) => {
                const categorySelected = perms.filter((p) =>
                  selectedPermissions.includes(p.code)
                ).length;
                const allSelected = categorySelected === perms.length;
                const someSelected = categorySelected > 0 && !allSelected;

                return (
                  <div key={category} className="border-b border-gray-100 last:border-b-0">
                    <div
                      className="flex items-center gap-2 px-3 py-2 bg-gray-50 cursor-pointer hover:bg-gray-100"
                      onClick={() => handleToggleCategory(category)}
                    >
                      <input
                        type="checkbox"
                        checked={allSelected}
                        ref={(el) => {
                          if (el) el.indeterminate = someSelected;
                        }}
                        onChange={() => handleToggleCategory(category)}
                        className="w-4 h-4 rounded border-gray-300"
                      />
                      <span className="font-medium text-sm text-gray-800">
                        {PERMISSION_CATEGORIES[category as keyof typeof PERMISSION_CATEGORIES] ||
                          category}
                      </span>
                      <span className="text-xs text-gray-500">
                        ({categorySelected}/{perms.length})
                      </span>
                    </div>
                    <div className="pl-8 pr-3 py-1 space-y-1">
                      {perms.map((perm) => (
                        <label
                          key={perm.code}
                          className="flex items-start gap-2 py-1 cursor-pointer hover:bg-gray-50 rounded"
                        >
                          <input
                            type="checkbox"
                            checked={selectedPermissions.includes(perm.code)}
                            onChange={() => handleTogglePermission(perm.code)}
                            className="w-4 h-4 mt-0.5 rounded border-gray-300"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm text-gray-800">{perm.name}</div>
                            {perm.description && (
                              <div className="text-xs text-gray-500 truncate">
                                {perm.description}
                              </div>
                            )}
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                );
              })}
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

const PermissionSetsPage = () => {
  const [permissionSets, setPermissionSets] = useState<PermissionSet[]>([]);
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { hasPermission } = usePermissions();

  // Modal state
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingSet, setEditingSet] = useState<PermissionSet | null>(null);
  const [saving, setSaving] = useState(false);

  // Delete confirmation modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [setToDelete, setSetToDelete] = useState<PermissionSet | null>(null);
  const [deleting, setDeleting] = useState(false);

  const canCreate = hasPermission(PERMISSIONS.PERMISSION_SET_CREATE);
  const canEdit = hasPermission(PERMISSIONS.PERMISSION_SET_EDIT);
  const canDelete = hasPermission(PERMISSIONS.PERMISSION_SET_DELETE);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [setsData, permsData] = await Promise.all([
        fetchPermissionSets(),
        fetchPermissions(),
      ]);
      setPermissionSets(setsData);
      setAllPermissions(permsData);
    } catch (err) {
      logger.error("Error fetching permission sets", err);
      setError("Failed to load permission sets");
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCreateModal = () => {
    setEditingSet(null);
    setEditModalOpen(true);
  };

  const handleOpenEditModal = (ps: PermissionSet) => {
    setEditingSet(ps);
    setEditModalOpen(true);
  };

  const handleCloseModal = () => {
    setEditModalOpen(false);
    setEditingSet(null);
  };

  const handleSave = async (
    data: PermissionSetCreate | PermissionSetUpdate,
    id?: string
  ) => {
    try {
      setSaving(true);
      if (id) {
        await updatePermissionSet(id, data as PermissionSetUpdate);
        toast.success("Permission set updated successfully");
      } else {
        await createPermissionSet(data as PermissionSetCreate);
        toast.success("Permission set created successfully");
      }
      await loadData();
      handleCloseModal();
    } catch (err) {
      logger.error("Error saving permission set", err);
      toast.error(id ? "Failed to update permission set" : "Failed to create permission set");
    } finally {
      setSaving(false);
    }
  };

  const openDeleteModal = (ps: PermissionSet) => {
    setSetToDelete(ps);
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!setToDelete) return;

    try {
      setDeleting(true);
      await deletePermissionSet(setToDelete.id);
      toast.success("Permission set deleted successfully");
      await loadData();
    } catch (err) {
      logger.error("Error deleting permission set", err);
      toast.error("Failed to delete permission set");
    } finally {
      setDeleting(false);
      setDeleteModalOpen(false);
      setSetToDelete(null);
    }
  };

  const columns = [
    {
      header: "Name",
      accessor: "name" as keyof PermissionSet,
      className: "text-sm text-gray-900 font-medium",
      headerClassName: "text-sm font-medium text-gray-700",
    },
    {
      header: "Code",
      accessor: "code" as keyof PermissionSet,
      className: "text-sm text-gray-600 font-mono",
      headerClassName: "text-sm font-medium text-gray-700",
    },
    {
      header: "Permissions",
      headerClassName: "text-sm font-medium text-gray-700",
      className: "text-sm text-gray-600",
      render: (ps: PermissionSet) => (
        <div className="flex flex-wrap gap-1">
          {ps.permissions.slice(0, 3).map((p) => (
            <span
              key={p.code}
              className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs"
              title={p.name}
            >
              {p.code}
            </span>
          ))}
          {ps.permissions.length > 3 && (
            <span className="px-2 py-0.5 bg-gray-200 text-gray-600 rounded text-xs">
              +{ps.permissions.length - 3} more
            </span>
          )}
          {ps.permissions.length === 0 && "-"}
        </div>
      ),
    },
    ...(canEdit || canDelete
      ? [
          {
            header: "Actions",
            headerClassName: "text-sm font-medium text-gray-700",
            render: (ps: PermissionSet) => (
              <div className="flex gap-2">
                {canEdit && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleOpenEditModal(ps)}
                  >
                    Edit
                  </Button>
                )}
                {canDelete && (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => openDeleteModal(ps)}
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
          title="Permission Sets"
          description="Manage permission sets that group related permissions."
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
        title="Permission Sets"
        description="Permission sets group related permissions together."
      />

      {error && (
        <div className="p-3 bg-red-50 text-sm text-red-700 border border-red-200 rounded">
          {error}
        </div>
      )}

      <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Permission Sets</h3>
            <p className="text-xs text-gray-600">
              {permissionSets.length} set(s) configured
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button variant="secondary" size="sm" onClick={loadData} disabled={loading}>
              Refresh
            </Button>
            {canCreate && (
              <Button variant="primary" size="sm" onClick={handleOpenCreateModal}>
                Add Permission Set
              </Button>
            )}
          </div>
        </div>

        {permissionSets.length === 0 ? (
          <div className="p-6 text-center text-gray-500 text-sm border border-dashed border-gray-300 rounded-lg bg-gray-50">
            No permission sets configured.
          </div>
        ) : (
          <div className="overflow-x-auto bg-white rounded-lg">
            <ConfigurableTable
              columns={columns}
              data={permissionSets}
              keyExtractor={(ps) => ps.id}
              headerRowClassName="bg-gray-50"
              rowClassName="border-t border-gray-200 hover:bg-gray-50"
            />
          </div>
        )}
      </section>

      {/* <section className="border border-gray-200 rounded-lg p-4 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">
            About Permission Sets
          </h3>
          <p className="text-xs text-gray-600 mt-1">
            Permission sets are groups of permissions that can be assigned to roles.
          </p>
        </div>
        <div className="text-xs text-gray-600 space-y-2">
          <p>
            Permission sets can be created, modified, and deleted to define specific
            permission combinations for your organization's needs.
          </p>
        </div>
      </section> */}

      {/* Edit/Create Modal */}
      <PermissionSetEditModal
        isOpen={editModalOpen}
        onClose={handleCloseModal}
        onSave={handleSave}
        permissionSet={editingSet}
        allPermissions={allPermissions}
        isLoading={saving}
      />

      {/* Delete Confirmation Modal */}
      <ConfirmModal
        isOpen={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setSetToDelete(null);
        }}
        onConfirm={handleConfirmDelete}
        title="Delete Permission Set"
        message={`Are you sure you want to delete the permission set "${setToDelete?.name}"? Roles using this set will lose these permissions.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        confirmVariant="danger"
        isLoading={deleting}
      />
    </div>
  );
};

export default PermissionSetsPage;
