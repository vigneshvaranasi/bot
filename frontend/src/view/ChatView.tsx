import Bubble from '../components/ui/Bubble'
import { useParams } from 'react-router-dom'

const ChatView = () => {
  const { chatId } = useParams<{ chatId: string }>()

  return (
    <div className={`flex-1 space-y-4 overflow-y-auto px-3`}>
      {chatId ? (
        <>
            <p>{chatId}</p>
            <Bubble variant='bot' content='Hello, how can I help you today?' />
            <Bubble
              variant='user'
              content='I am getting a status code 499 when connecting to PayU Service, how to solve it?
              I am getting a status code 499 when connecting to PayU Service, how to solve it?
              I am getting a status code 499 when connecting to PayU Service, how to solve it?
              I am getting a status code 499 when connecting to PayU Service, how to solve it?
              I am getting a status code 499 when connecting to PayU Service, how to solve it?'
            />
            <Bubble variant='bot' content='## INCIDENT ANALYSIS REPORT' />
            <Bubble variant='bot' content='## INCIDENT ANALYSIS REPORT' />
            <Bubble variant='bot' content='## INCIDENT ANALYSIS REPORT' />
            <Bubble variant='bot' content='## INCIDENT ANALYSIS REPORT' />
            <Bubble variant='bot' content='## INCIDENT ANALYSIS REPORT' />
            <Bubble variant='bot' content='## INCIDENT ANALYSIS REPORT' />
            <Bubble variant='bot' content='## INCIDENT ANALYSIS REPORT' />
            <Bubble variant='bot' content='## INCIDENT ANALYSIS REPORT' />
            <Bubble variant='bot' content='## INCIDENT ANALYSIS REPORT' />
            <Bubble variant='bot' content='## INCIDENT ANALYSIS REPORT' />
            <Bubble variant='bot' content='## INCIDENT ANALYSIS REPORT' />
          </>
      ) : (
        <div className='flex flex-col items-center justify-center h-full'>
            <p className='text-lg md:text-2xl'>
                Welcome, How can I assist you today?
            </p>
        </div>
      )}
    </div>
  )
}

export default ChatView
