import type { RouteObject } from 'react-router'
import Layout from './Layout'
import HomePage from '../pages/Home.page'
import ChatPage from '../pages/Chat.page'
const normalRoutes: RouteObject = {
  path: '/',
  element: <Layout />,
  children: [
    {
      path: '/home',
      element: <HomePage />
    },
    {
        path:'/',
        element: <ChatPage />
    }
  ]
}


const router: RouteObject[] = [normalRoutes]

export default router