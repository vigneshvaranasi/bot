import { useState } from 'react'
import Navbar from '../components/Navbar'
import Sidebar from '../components/Sidebar'
import InputBox from '../components/ui/InputBox'
import { useSidebarContext } from '../hooks/useSidebarContext'
import { Outlet } from 'react-router-dom'

function ChatPage () {
  const { isSidebarOpen } = useSidebarContext()
  const [chatInput,setChatInput] = useState('')
  return (
    <div className={`flex h-screen`}>
      <Sidebar />
      <div className={`flex-1 ${isSidebarOpen && 'hidden md:block'}`}>
        <div className='flex flex-col h-screen'>
          <Navbar />
          <Outlet />
          {/* Input Box */}
          <div
            className='flex p-5 border-t border-gray-200 bg-gray-50 w-full'
          >
            <InputBox
              onChange={(value) => {setChatInput(value);
                console.log('value: ', value);

              }}
              value={chatInput}
              placeholder='Type your message...'
              variant='primary'
              backgroundColor='f9fafb'
            />
            <button
              className={`ml-2 px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500`}
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ChatPage
