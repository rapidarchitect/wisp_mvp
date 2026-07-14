import { Navigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { state } = useAuth();

  if (state.status === "loading") {
    return <div>Loading...</div>;
  }

  if (state.status === "unauthenticated") {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
