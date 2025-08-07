import type { RouteObject } from 'react-router'
import Layout from './Layout'
import HomePage from '../pages/Home.page'
import ChatPage from '../pages/Chat.page'
import ChatView from '../view/ChatView'
const normalRoutes: RouteObject = {
  path: '/',
  element: <Layout />,
  children: [
    {
      path: '/home',
      element: <HomePage />
    },
    {
        path: '/',
        element: <ChatPage />,
        children: [{
          index: true,
          element: <ChatView />
        }, {
          path: ':chatId',
          element: <ChatView />
        }]
    }
  ]
}


const router: RouteObject[] = [normalRoutes]

export default router