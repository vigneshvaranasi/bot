import { useState,useRef } from 'react'
import Navbar from '../components/Navbar'
import Sidebar from '../components/Sidebar'
import InputBox from '../components/ui/InputBox'
import { Button } from '../components/ui/Button'
import { useSidebarContext } from '../hooks/useSidebarContext'
import { Outlet } from 'react-router-dom'

function ChatPage () {

  const { isSidebarOpen } = useSidebarContext()
  const [chatInput,setChatInput] = useState('')
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
            className='flex p-5 gap-x-2 bg-gray-50 w-full'
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
