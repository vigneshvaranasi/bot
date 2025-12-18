import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { ConfigurableTable } from '../components/ui/Table';
import SettingsNavbar from '../components/SettingsNavbar';
import ButtonGroup from '../components/ui/ButtonGroup';
import arrowLeftIcon from "../assets/arrow-left.svg";
import { fetchUsers, fetchRoles, updateUser, deleteUser, type AdminUser, type Role } from '../handlers/adminHandlers';
import Dropdown from '../components/ui/Dropdown';

const UserManagement: React.FC = () => {
  const navigate = useNavigate();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  
  // Edit Modal State
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [selectedRoleId, setSelectedRoleId] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        const [usersData, rolesData] = await Promise.all([fetchUsers(), fetchRoles()]);
        setUsers(usersData);
        setRoles(rolesData);
      } catch (error) {
        console.error("Failed to load data", error);
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
      await updateUser(editingUser.id, {
        is_active: editingUser.is_active,
        role_id: selectedRoleId
      });
      
      // Refresh list
      const usersData = await fetchUsers();
      setUsers(usersData);
      setIsEditModalOpen(false);
      setEditingUser(null);
    } catch (error) {
      console.error("Failed to update user", error);
      alert("Failed to update user");
    }
  };

  const handleDeleteUser = async (user: AdminUser) => {
    if (window.confirm(`Are you sure you want to delete user ${user.email}?`)) {
      try {
        await deleteUser(user.id);
        const usersData = await fetchUsers();
        setUsers(usersData);
      } catch (error) {
        console.error("Failed to delete user", error);
        alert("Failed to delete user");
      }
    }
  };

  const handleBackToSettings = () => {
    navigate('/settings');
  };

  const filteredUsers = users.filter(user =>
    user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.role_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const columns = [
    {
      header: 'Email',
      accessor: 'email' as keyof AdminUser,
      className: 'text-xs md:text-sm text-gray-900',
      headerClassName: 'text-xs md:text-sm font-medium text-gray-700'
    },
    {
      header: 'Role',
      accessor: 'role_name' as keyof AdminUser,
      className: 'text-xs md:text-sm text-gray-900',
      headerClassName: 'text-xs md:text-sm font-medium text-gray-700'
    },
    {
      header: 'Actions',
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
      headerClassName: 'text-xs md:text-sm font-medium text-gray-700'
    }
  ];

  return (
    <div className="min-h-screen bg-gray-100 relative">
      <SettingsNavbar 
        searchValue={searchTerm}
        onSearchChange={setSearchTerm}
        searchPlaceholder="Search users..."
      />


      <div className="p-4 md:p-6">
        <div className="max-w-screen-2xl mx-auto">
          
          <div className="mb-6">
            <h1 className="text-xl md:text-2xl font-semibold text-gray-900 px-2">USER MANAGEMENT TABLE</h1>
          </div>


          <div className="overflow-x-auto bg-white rounded-lg shadow-lg border border-gray-300">
            <ConfigurableTable
              columns={columns}
              data={filteredUsers}
              keyExtractor={(user) => user.id}
              tableClassName="min-w-full"
              headerRowClassName="bg-gray-50"
              rowClassName="bg-white border-t border-gray-200 hover:bg-gray-50"
            />
          </div>
          {/* Bottom Actions */}
            <div className="flex items-center justify-center mt-6 px-4">
              <ButtonGroup>
                <Button
                  variant="default"
                  onClick={handleBackToSettings}
                  className='flex gap-4'
                  >
                    <img src={arrowLeftIcon}  alt="" />
                    Back
                </Button>
            </ButtonGroup>
            </div>
        </div>
      </div>

      {/* Edit Modal */}
      {isEditModalOpen && editingUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white p-6 rounded-lg shadow-xl w-full max-w-md">
                <h2 className="text-xl font-semibold mb-4">Edit User: {editingUser.email}</h2>
                
                <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
                    <Dropdown 
                        options={roles.map(r => ({ label: r.name, value: r.id }))}
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
                    <Button 
                        variant="primary" 
                        onClick={handleSaveUser}
                    >
                        Save Changes
                    </Button>
                </div>
            </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
