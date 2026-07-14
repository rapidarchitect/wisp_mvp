import { Navigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function RoleGuard({
  children,
  roles,
}: {
  children: React.ReactNode;
  roles: string[];
}) {
  const { state } = useAuth();

  if (state.status !== "authenticated") {
    return <Navigate to="/login" replace />;
  }

  const hasRole = roles.some((role) => state.user.roles.includes(role));
  if (!hasRole) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
