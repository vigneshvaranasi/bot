import type { RouteObject } from "react-router";
import { Navigate } from "react-router-dom";
import Layout from "./Layout";
import HomePage from "../pages/Home.page";
import ChatPage from "../pages/Chat.page";
import ChatView from "../view/ChatView";
import AuthPage from "../pages/Auth.page";
import UserManagementPage from "../pages/settings/UserManagement.page";
import ProtectedRoute from "./ProtectedRoute";
import OAuthCallback from "../pages/OAuthCallback.page";
import SettingsLayout from "../components/settings/SettingsLayout";
import MyAccountPage from "../pages/settings/MyAccount.page";
import AiMlConfigPage from "../pages/settings/AiMl.page";
import IntegrationsPage from "../pages/settings/Integrations.page";
import ConfigurationHistoryPage from "../pages/settings/ConfigurationHistory.page";
import RoleManagementPage from "../pages/settings/RoleManagement.page";
import PermissionSetsPage from "../pages/settings/PermissionSets.page";
import FeedbackDashboardPage from "../pages/settings/FeedbackDashboard.page";
import KnowledgeBasePage from "../pages/settings/KnowledgeBase.page";
import AdminRoute from "./AdminRoute";

const normalRoutes: RouteObject = {
  path: "/",
  element: <Layout />,
  children: [
    {
      path: "/auth",
      element: <AuthPage />,
    },
    {
      path: "/auth/callback/:provider",
      element: <OAuthCallback />,
    },
    {
      path: "/home",
      element: <HomePage />,
    },
    {
      path: "/settings",
      element: <ProtectedRoute />,
      children: [
        {
          element: <SettingsLayout />,
          children: [
            {
              index: true,
              element: <Navigate to="/settings/my-account" replace />,
            },
            { path: "my-account", element: <MyAccountPage /> },
            {
              path: "security",
              element: <Navigate to="/settings/my-account" replace />,
            },
            {
              element: <AdminRoute />,
              children: [
                { path: "ai-ml", element: <AiMlConfigPage /> },
                { path: "integrations", element: <IntegrationsPage /> },
                { path: "user-management", element: <UserManagementPage /> },
                { path: "roles", element: <RoleManagementPage /> },
                { path: "permission-sets", element: <PermissionSetsPage /> },
                { path: "feedback", element: <FeedbackDashboardPage /> },
                {
                  path: "config-history",
                  element: <ConfigurationHistoryPage />,
                },
                { path: "knowledge-base", element: <KnowledgeBasePage /> },
              ],
            },
          ],
        },
      ],
    },
    {
      path: "/",
      element: <ProtectedRoute />,
      children: [
        {
          element: <ChatPage />,
          children: [
            { index: true, element: <ChatView /> },
            { path: ":chatId", element: <ChatView /> },
          ],
        },
      ],
    },
  ],
};

const router: RouteObject[] = [normalRoutes];

export default router;
