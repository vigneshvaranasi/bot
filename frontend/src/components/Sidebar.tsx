import gearIcon from '../assets/Settings.svg'
import { fuzzyMatch } from '../utils/search'
import { useSidebarContext } from '../hooks/useSidebarContext'
import sidebarImg from '../assets/sidebar.svg'
import searchIcon from '../assets/SearchIcon.svg'
import { Link } from 'react-router-dom'
import InputBox from './ui/InputBox'
import { useEffect, useState } from 'react'
import { useAuthContext } from '../hooks/useAuthContext'
import { getAllMyChats } from '../handlers/chatHandler'


function Sidebar () {
  const { isSidebarOpen, toggleSidebar, chats, setChats, currentChat } = useSidebarContext()
  const [searchInput, setSearchInput] = useState('')
  const { user } = useAuthContext();
  if(!user){
    return (
      <div className='flex justify-center items-center h-screen'>
        <p className='text-gray-500'>Please log in to view chats.</p>
      </div>
    )
  }

  // fetch chats
  useEffect(() => {
    const fetchChats = async () => {
      try {
        const allMyChats = await getAllMyChats(user?.token);
        console.log('allMyChats: ', allMyChats);
        if (allMyChats && Array.isArray(allMyChats.chats)) {
          setChats(
            allMyChats.chats.map((chat: any) => ({
              chatId: chat.id,
              chatTitle: chat.title,
              date: chat.created_at,
            }))
          );
        } else {
          setChats([]);
        }
      } catch (err) {
        console.error('Failed to fetch chats:', err);
        setChats([]);
      }
    };
    fetchChats();
  }, [user,currentChat]);


  const handleLinkClick = () => {
    if (window.innerWidth < 768) {
      toggleSidebar()
    }
  }

  const filteredChats = searchInput
    ? chats
        .filter(
          chat =>
            fuzzyMatch(chat.chatTitle, searchInput) ||
            fuzzyMatch(chat.date, searchInput)
        )
    : chats

  return (
    <div
      className={`left-0 top-0 z-[1000] h-screen bg-gray-50 flex flex-col transition-all duration-300 overflow-hidden ${
        isSidebarOpen ? 'w-full md:w-72' : 'w-0 md:w-12'
      }`}
    >
      {isSidebarOpen ? (
        <div className='flex flex-col h-full'>
          <div className='flex items-center justify-between pt-2 px-4 gap-2'>
            <div className='relative flex-1'>
              <InputBox
                placeholder='Search...'
                variant='primary'
                onChange={value => {
                  setSearchInput(value)
                }}
                value={searchInput}
                icon={searchIcon}
                backgroundColor='f9fafb'
              />
            </div>
            <button
              className='p-2 rounded-md hover:bg-gray-200'
              onClick={() => toggleSidebar()}
            >
              <img src={sidebarImg} alt='Close Sidebar' className='w-7 mt-3 md:mt-0 md:w-6' />
            </button>
          </div>
          <Link
            onClick={() => handleLinkClick()}
            to={'/'}
            className='mx-3 mt-2 flex items-center p-1.5 gap-2 rounded-lg hover:bg-gray-200'
          >
            <p className='pb-1 text-2xl'>+</p>
            <button className='font-medium ' onClick={() => handleLinkClick()}>
              New Chat
            </button>
          </Link>
          <div className='flex-1 overflow-y-auto p-4'>
            {filteredChats.length === 0 ? (
              <div className='text-gray-400 text-center mt-8'>
                No chats found.
              </div>
            ) : (
              <div className='space-y-1'>
                {filteredChats.map(chat => (
                  <Link
                    key={chat.chatId}
                    className='hover:bg-gray-200 block p-2 rounded-md'
                    to={`/${chat.chatId}`}
                    onClick={handleLinkClick}
                  >
                    <div className='text-xs text-[#5c5c5c]'>
                      {chat.date ? new Date(chat.date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : ''}
                    </div>
                    <div className='font-medium text-base'>{chat.chatTitle}</div>
                  </Link>
                ))}
              </div>
            )}
          </div>
          <div className='flex bg-[#eaedef] m-4 p-2 rounded-lg items-center justify-between'>
            <div className='flex items-center gap-2'>
              <img
                src='https://t3.ftcdn.net/jpg/08/05/28/22/360_F_805282248_LHUxw7t2pnQ7x8lFEsS2IZgK8IGFXePS.jpg'
                className='w-8 rounded-full'
                alt=''
              />
              <p>
                {
                  user?.email.split('@')[0] || 'Guest'
                }
              </p>
            </div>
            <img src={gearIcon} className='w-5 rounded-full' alt='' />
          </div>
        </div>
      ) : (
        <div className='flex flex-col justify-center items-center gap-2 pt-2'>
          <button
            className='p-2 rounded-md hover:bg-gray-200'
            onClick={() => toggleSidebar()}
          >
            <img src={sidebarImg} alt='Close Sidebar' className='w-6' />
          </button>
          <Link
            to={'/'}
            className='p-2 rounded-md hover:bg-gray-200'
            onClick={() => console.log('New chat clicked')}
          >
            <p className='text-3xl'>+</p>
          </Link>
        </div>
      )}
    </div>
  )
}

export default Sidebar
