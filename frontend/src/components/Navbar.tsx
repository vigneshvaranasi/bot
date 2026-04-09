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
