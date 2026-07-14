import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { RoleGuard } from "./components/RoleGuard";
import { DashboardLayout } from "./layouts/DashboardLayout";
import { ActivatePage } from "./pages/ActivatePage";
import { AdminDomainsPage } from "./pages/AdminDomainsPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EnrollTotpPage } from "./pages/EnrollTotpPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { TotpChallengePage } from "./pages/TotpChallengePage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <LandingPage />,
  },
  {
    path: "/signup",
    element: <SignupPage />,
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/enroll-totp",
    element: <EnrollTotpPage />,
  },
  {
    path: "/totp",
    element: <TotpChallengePage />,
  },
  {
    path: "/activate",
    element: <ActivatePage />,
  },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <DashboardLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        path: "dashboard",
        element: <DashboardPage />,
      },
      {
        path: "admin/users",
        element: (
          <RoleGuard roles={["admin"]}>
            <AdminUsersPage />
          </RoleGuard>
        ),
      },
      {
        path: "admin/domains",
        element: (
          <RoleGuard roles={["admin"]}>
            <AdminDomainsPage />
          </RoleGuard>
        ),
      },
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
    ],
  },
]);

function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}

export default App;
