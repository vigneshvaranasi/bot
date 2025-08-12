import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { ConfigurableTable } from '../components/ui/Table';

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
      className: 'text-sm text-gray-900',
      headerClassName: 'text-sm font-medium text-gray-700'
    },
    {
      header: 'Role',
      accessor: 'role' as keyof UserRecord,
      className: 'text-sm text-gray-900',
      headerClassName: 'text-sm font-medium text-gray-700'
    },
    {
      header: 'Permissions',
      accessor: 'permissions' as keyof UserRecord,
      className: 'text-sm text-gray-900',
      headerClassName: 'text-sm font-medium text-gray-700'
    },
    {
      header: 'Last Updated',
      accessor: 'lastUpdated' as keyof UserRecord,
      className: 'text-sm text-gray-900',
      headerClassName: 'text-sm font-medium text-gray-700'
    },
    {
      header: 'Actions',
      render: (user: UserRecord) => (
        <div className="flex gap-20">
          <Button
            variant="secondary"
            className="bg-gray-400 text-white hover:bg-gray-500 text-sm px-2 py-2 w-auto"
            onClick={() => handleEditUser(user.id)}
          >
            EDIT
          </Button>
          <Button
            variant="secondary"
            className="bg-gray-400 text-white hover:bg-gray-500 text-sm px-2 py-2 w-auto"
            onClick={() => handleDeleteUser(user.id)}
          >
            DELETE
          </Button>
        </div>
      ),
      headerClassName: 'text-sm font-medium text-gray-700'
    }
  ];

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="bg-gray-100">
        <div className="p-4">
          <div className="max-w-screen-2xl mx-auto grid grid-cols-[1.5fr_1.5fr] items-center">
            <div className="bg-white px-8 py-2 rounded-[10px] text-lg font-low text-gray-900 w-fit">Logo</div>

            <div className="flex items-center gap-4 justify-end w-full">
              
              <div className="relative w-full">
                <input
                  type="text"
                  placeholder="Search"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="
                      w-full h-11 pr-12 pl-11
                      bg-white rounded-[5px]
                      border-0 border-b-2 border-gray-400
                      placeholder-gray-500
                      focus:outline-none focus:ring-0
                      hover:border-gray-400 focus:border-gray-400 active:border-gray-400
                      "
                />
                
                <svg
                  className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-500 pointer-events-none"
                  viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                >
                  <circle cx="11" cy="11" r="7" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                
                <div className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 opacity-0 " />
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
      </div>

      
      <div className="p-6">
        <div className="max-w-screen-2xl mx-auto">
          
          <div className="mb-6">
            <h1 className="text-2xl font-semibold text-gray-900">USER MANAGEMENT TABLE</h1>
          </div>

          
          <div className="overflow-x-auto bg-gray-100">
            <ConfigurableTable
              columns={columns}
              data={filteredUsers}
              keyExtractor={(user) => user.id}
              tableClassName="min-w-full border-2 border-gray-300 rounded-lg overflow-hidden"
              headerRowClassName="bg-gray-50"
              rowClassName="bg-white border-t border-gray-200 hover:bg-gray-50"
            />
          </div>
          {/* Bottom Actions */}
            <div className="flex items-center justify-center mt-6">
            <div 
              onClick={handleBackToSettings}
              className="bg-white px-8 py-2 rounded-xl text-lg font-low text-gray-800 w-fit cursor-pointer hover:bg-gray-100"
            >
              ← Back
            </div>
            </div>
        </div>
      </div>
    </div>
  );
};

export default UserManagement;
