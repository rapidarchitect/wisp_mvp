import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { apiFetch, ApiResponseError } from "../api/client";

export type User = {
  id: number;
  email: string;
  roles: string[];
  status: string;
};

export type LoginStep =
  | { kind: "session"; token: string }
  | { kind: "enrollment_required"; secret: string; provisioning_uri: string }
  | { kind: "totp_required" };

type AuthState =
  | { status: "loading" }
  | { status: "authenticated"; user: User }
  | { status: "unauthenticated" };

type AuthContextValue = {
  state: AuthState;
  login: (email: string, password: string) => Promise<LoginStep>;
  verifyTotp: (code: string) => Promise<void>;
  completeEnrollment: (code: string) => Promise<void>;
  logout: () => Promise<void>;
  error: string | null;
  clearError: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const AUTH_TOKEN_KEY = "wispgen_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const [error, setError] = useState<string | null>(null);
  const pendingRef = useRef<{ email: string; password: string; uri?: string } | null>(null);


  const clearError = useCallback(() => setError(null), []);

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    if (!token) {
      setState({ status: "unauthenticated" });
      return;
    }
    try {
      const user = await apiFetch<User>("/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setState({ status: "authenticated", user });
    } catch (err) {
      localStorage.removeItem(AUTH_TOKEN_KEY);
      setState({ status: "unauthenticated" });
    }
  }, []);

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  const setToken = useCallback((token: string) => {
    localStorage.setItem(AUTH_TOKEN_KEY, token);
  }, []);

  const finishWithToken = useCallback(
    async (token: string) => {
      setToken(token);
      pendingRef.current = null;
      localStorage.removeItem("wispgen_pending_email");
      localStorage.removeItem("wispgen_pending_uri");
      await loadUser();
    },
    [loadUser, setToken],
  );

  const login = useCallback(
    async (email: string, password: string, totpCode?: string): Promise<LoginStep> => {
      clearError();
      try {
        const result = await apiFetch<{
          token?: string;
          enrollment_required?: boolean;
          secret?: string;
          provisioning_uri?: string;
        }>("/auth/login", {
          method: "POST",
          body: { email, password, totp_code: totpCode },
        });

        if (result.enrollment_required) {
          pendingRef.current = { email, password, uri: result.provisioning_uri };
          localStorage.setItem("wispgen_pending_email", email);
          localStorage.setItem("wispgen_pending_uri", result.provisioning_uri ?? "");
          return {
            kind: "enrollment_required",
            secret: result.secret ?? "",
            provisioning_uri: result.provisioning_uri ?? "",
          };
        }

        if (result.token) {
          await finishWithToken(result.token);
          return { kind: "session", token: result.token };
        }

        pendingRef.current = { email, password };
        localStorage.setItem("wispgen_pending_email", email);
        return { kind: "totp_required" };
      } catch (err) {
        if (err instanceof ApiResponseError && err.status === 401 && !totpCode) {
          // The backend requires a TOTP code for enrolled users and returns 401
          // for password-only attempts. Store credentials and prompt for TOTP.
          pendingRef.current = { email, password };
          localStorage.setItem("wispgen_pending_email", email);
          return { kind: "totp_required" };
        }
        const message =
          err instanceof ApiResponseError ? err.error.message : "Login failed";
        setError(message);
        throw err;
      }
    },
    [clearError, finishWithToken],
  );

  const verifyTotp = useCallback(
    async (code: string): Promise<void> => {
      clearError();
      const email = pendingRef.current?.email ?? localStorage.getItem("wispgen_pending_email");
      const password = pendingRef.current?.password;
      if (!email || !password) {
        setError("Session expired; please log in again.");
        throw new Error("No pending login");
      }
      try {
        const result = await apiFetch<{ token: string }>("/auth/login", {
          method: "POST",
          body: { email, password, totp_code: code },
        });
        await finishWithToken(result.token);
      } catch (err) {
        const message =
          err instanceof ApiResponseError ? err.error.message : "Verification failed";
        setError(message);
        throw err;
      }
    },
    [clearError, finishWithToken],
  );

  const completeEnrollment = useCallback(
    async (code: string): Promise<void> => {
      clearError();
      const email = pendingRef.current?.email ?? localStorage.getItem("wispgen_pending_email");
      const password = pendingRef.current?.password;
      if (!email || !password) {
        setError("Session expired; please log in again.");
        throw new Error("No pending login");
      }
      try {
        const result = await apiFetch<{ token: string }>("/auth/login", {
          method: "POST",
          body: { email, password, totp_code: code },
        });
        await finishWithToken(result.token);
      } catch (err) {
        const message =
          err instanceof ApiResponseError ? err.error.message : "Enrollment failed";
        setError(message);
        throw err;
      }
    },
    [clearError, finishWithToken],
  );

  const logout = useCallback(async (): Promise<void> => {
    clearError();
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem("wispgen_pending_email");
    localStorage.removeItem("wispgen_pending_uri");
    pendingRef.current = null;
    setState({ status: "unauthenticated" });
  }, [clearError]);

  const value = useMemo(
    () => ({
      state,
      login,
      verifyTotp,
      completeEnrollment,
      logout,
      error,
      clearError,
    }),
    [state, login, verifyTotp, completeEnrollment, logout, error, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
