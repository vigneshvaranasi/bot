import { Link } from 'react-router-dom'
import hamburger from '../assets/hamburger.svg'
import { useSidebarContext } from '../hooks/useSidebarContext'
const Navbar = () => {
  const { isSidebarOpen, setSidebarOpen } = useSidebarContext()
  return (
    <div className='relative flex items-center justify-between p-3 bg-gray-50 md:justify-start md:gap-4'>
      <img
        src={hamburger}
        className={`${isSidebarOpen ? 'hidden' : 'w-6 md:hidden'}`}
        alt='menu'
        onClick={() => setSidebarOpen(!isSidebarOpen)}
      />
      <div className='absolute left-1/2 -translate-x-1/2 md:static md:translate-x-0'>
        <div className='text-lg'>Logo</div>
      </div>
      <Link
        to={'/'}
        className='md:hidden flex items-center px-2 gap-2 rounded-lg hover:bg-gray-200'
      >
        <p className='pb-1 text-2xl'>+</p>
        <button
          className='font-medium'
          onClick={() => console.log('New chat clicked')}
        >
          New
        </button>
      </Link>
    </div>
  )
}

export default Navbar
