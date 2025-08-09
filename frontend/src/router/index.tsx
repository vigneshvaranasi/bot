import type { RouteObject } from 'react-router'
import Layout from './Layout'
import HomePage from '../pages/Home.page'
import ChatPage from '../pages/Chat.page'
import ChatView from '../view/ChatView'
import Login from '../pages/LogIn.page'
import Signup from '../pages/Signup.page'
import ProtectedRoute from './ProtectedRoute'
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