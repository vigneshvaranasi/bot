import type { RouteObject } from 'react-router'
import Layout from './Layout'
import HomePage from '../pages/Home.page'
const normalRoutes: RouteObject = {
  path: '/',
  element: <Layout />,
  children: [
    {
      path: '/',
      element: <HomePage />
    }
  ]

}


const router: RouteObject[] = [normalRoutes]

export default router