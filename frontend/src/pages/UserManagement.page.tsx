import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { ConfigurableTable } from '../components/ui/Table';
import SettingsNavbar from '../components/SettingsNavbar';
import ButtonGroup from '../components/ui/ButtonGroup';
import arrowLeftIcon from "../assets/arrow-left.svg";

interface UserRecord {
  id: string;
  email: string;
  role: string;
  permissions: string;
  lastUpdated: string;
}

const UserManagement: React.FC = () => {
  const navigate = useNavigate();
  
  const [users, setUsers] = useState<UserRecord[]>([
    { id: '1', email: 'emp1@gmail.com', role: 'L1 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
    { id: '2', email: 'emp1@gmail.com', role: 'L1 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
    { id: '3', email: 'emp1@gmail.com', role: 'L1 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
    { id: '4', email: 'emp1@gmail.com', role: 'L4 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
    { id: '5', email: 'emp1@gmail.com', role: 'L1 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
    { id: '6', email: 'emp1@gmail.com', role: 'L1 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
    { id: '7', email: 'emp1@gmail.com', role: 'L1 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
    { id: '8', email: 'emp1@gmail.com', role: 'L1 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
    { id: '9', email: 'emp1@gmail.com', role: 'L1 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
    { id: '10', email: 'emp1@gmail.com', role: 'L1 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
    { id: '11', email: 'emp1@gmail.com', role: 'L1 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
    { id: '12', email: 'emp1@gmail.com', role: 'L1 Support', permissions: 'Access Chat, Rating', lastUpdated: '27 July 2025' },
  ]);

  const [searchTerm, setSearchTerm] = useState('');

  const handleEditUser = (userId: string) => {
    console.log('Edit user:', userId);
    // Add edit functionality here
  };

  const handleDeleteUser = (userId: string) => {
    setUsers(users.filter(user => user.id !== userId));
  };

  const handleBackToSettings = () => {
    navigate('/settings');
  };

  const filteredUsers = users.filter(user =>
    user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.role.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.permissions.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const columns = [
    {
      header: 'Email',
      accessor: 'email' as keyof UserRecord,
      className: 'text-xs md:text-sm text-gray-900',
      headerClassName: 'text-xs md:text-sm font-medium text-gray-700'
    },
    {
      header: 'Role',
      accessor: 'role' as keyof UserRecord,
      className: 'text-xs md:text-sm text-gray-900',
      headerClassName: 'text-xs md:text-sm font-medium text-gray-700'
    },
    {
      header: 'Permissions',
      accessor: 'permissions' as keyof UserRecord,
      className: 'text-xs md:text-sm text-gray-900 sm:table-cell',
      headerClassName: 'text-xs md:text-sm font-medium text-gray-700 hidden sm:table-cell'
    },
    {
      header: 'Last Updated',
      accessor: 'lastUpdated' as keyof UserRecord,
      className: 'text-xs md:text-sm text-gray-900 lg:table-cell',
      headerClassName: 'text-xs md:text-sm font-medium text-gray-700 hidden lg:table-cell'
    },
    {
      header: 'Actions',
      render: (user: UserRecord) => (
        <div className="flex flex-row gap-1 sm:gap-2">
          <Button
            variant="secondary"
            className="bg-gray-400 text-white hover:bg-gray-500 text-xs md:text-sm px-2 py-1 w-full sm:w-auto"
            onClick={() => handleEditUser(user.id)}
          >
            EDIT
          </Button>
          <Button
            variant="secondary"
            className="bg-gray-400 text-white hover:bg-gray-500 text-xs md:text-sm px-2 py-1 w-full sm:w-auto"
            onClick={() => handleDeleteUser(user.id)}
          >
            DELETE
          </Button>
        </div>
      ),
      headerClassName: 'text-xs md:text-sm font-medium text-gray-700'
    }
  ];

  return (
    <div className="min-h-screen bg-gray-100">
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
                  // className="bg-white hover:bg-gray-100 text-gray-800 px-6 md:px-8 py-2 rounded-xl text-base md:text-lg font-low w-full sm:w-fit text-center border border-gray-200"
                  >
                    <img src={arrowLeftIcon}  alt="" />
                    Back
                </Button>
            </ButtonGroup>
            </div>
        </div>
      </div>
    </div>
  );
};

export default UserManagement;
