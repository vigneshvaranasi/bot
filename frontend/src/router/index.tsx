import type { RouteObject } from 'react-router'
import Layout from './Layout'
import HomePage from '../pages/Home.page'
import ChatPage from '../pages/Chat.page'
import ChatView from '../view/ChatView'
import Login from '../pages/LogIn.page'
import Signup from '../pages/Signup.page'
import ProtectedRoute from './ProtectedRoute'
import Settings from '../pages/Settings.page'
import UserManagement from '../pages/UserManagement.page'
const normalRoutes: RouteObject = {
  path: '/',
  element: <Layout />,
  children: [
    {
      path: '/home',
      element: <HomePage />
    },
    {
      path:'/login',
      element:<Login/>
    },
    {
      path:'/signup',
      element:<Signup/>
    },
    {
      path: '/settings',
      element: <Settings />
    },
    {
      path: '/user-management',
      element: <UserManagement />
    },
    // Protected Chat Route
    {
      path: '/',
      element: <ProtectedRoute/>,
      children: [
        {
          element: <ChatPage />,
          children: [
            { index: true, element: <ChatView /> },
            { path: ':chatId', element: <ChatView /> }
          ]
        }
      ]
    },
  ]
}

const router: RouteObject[] = [normalRoutes]

export default router