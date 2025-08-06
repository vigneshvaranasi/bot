import { Outlet } from 'react-router'

function Layout () {

  return (
      <div className={`flex flex-col justify-start max-h-screen`}>
        <Outlet />
      </div>
  )
}

export default Layout