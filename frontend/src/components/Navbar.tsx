import { Link } from 'react-router-dom'
import hamburger from '../assets/hamburger.svg'
import { useSidebarContext } from '../hooks/useSidebarContext'
const Navbar = () => {
  const { isSidebarOpen, toggleSidebar } = useSidebarContext()
  return (
    <div className='relative flex items-center justify-between p-3 md:justify-start md:gap-4 border-b border-border-default'>
      <img
        src={hamburger}
        className={`icon-adaptive ${isSidebarOpen ? 'hidden' : 'w-6 md:hidden'}`}
        alt='menu'
        onClick={() => toggleSidebar()}
      />
      <div className='absolute left-1/2 -translate-x-1/2 md:static md:translate-x-0'>
        <div className='flex items-center gap-2'>
          <span className='text-lg '>Support Bot</span>
        </div>
      </div>
      <button
        type='button'
        onClick={() => window.dispatchEvent(new Event('supportbot:start-chat-tour'))}
        title='Take a quick tour'
        aria-label='Take a quick tour'
        className='hidden md:inline-flex md:ml-auto items-center justify-center p-1.5 rounded-md hover:bg-surface-tertiary transition-colors text-text-secondary'
      >
        <svg className='w-5 h-5' viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth={2} strokeLinecap='round' strokeLinejoin='round'>
          <circle cx='12' cy='12' r='10' />
          <path d='M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3' />
          <line x1='12' y1='17' x2='12.01' y2='17' />
        </svg>
      </button>
      <Link
        to={'/'}
        className='md:hidden flex items-center px-2 gap-1.5 rounded-lg hover:bg-surface-tertiary transition-colors'
      >
        <svg className="w-4 h-4 text-text-secondary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        <span className='font-medium'>New</span>
      </Link>
    </div>
  )
}

export default Navbar
