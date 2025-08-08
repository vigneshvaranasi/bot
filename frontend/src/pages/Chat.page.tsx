import { useRef } from 'react'
import Navbar from '../components/Navbar'
import Sidebar from '../components/Sidebar'
import { Button } from '../components/ui/Button'
import { useSidebarContext } from '../hooks/useSidebarContext'
import { Outlet } from 'react-router-dom'

function ChatPage () {
  const { isSidebarOpen } = useSidebarContext();
  const promptInputRef = useRef<HTMLInputElement>(null);

  const handlePromptSend = ()=>{
    const prompt = promptInputRef.current?.value;
    if(prompt){
      console.log('Sent a Prompt:\n', prompt);
    }
  }

  return (
    <div className={`flex h-screen`}>
      <Sidebar />
      <div className={`flex-1 ${isSidebarOpen && 'hidden md:block'}`}>
        <div className='flex flex-col h-screen'>
          <Navbar />
          <Outlet />
          {/* Prompt Box */}
          <div
            className='flex p-5 gap-x-2 border-t border-gray-200 bg-gray-50 w-full'
          >
            <input
              type='text'
              placeholder='Type your message...'
              className={`w-full p-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500`}
              ref={promptInputRef}
            />
            <Button
              variant='secondary'
              onClick={handlePromptSend}
            >
              Send
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ChatPage
