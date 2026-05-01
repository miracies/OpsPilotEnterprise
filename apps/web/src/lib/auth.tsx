"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { apiFetch, ApiError } from "./api";

export interface AuthUser {
  username: string;
  display_name: string;
  role: string;
  avatar: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<{ data: AuthUser }>("/api/v1/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await apiFetch<{ success: boolean; data: AuthUser & { token: string }; error?: string }>(
      "/api/v1/auth/login",
      { method: "POST", body: JSON.stringify({ username, password }) }
    );
    if (!res.success) throw new Error(res.error ?? "Login failed");
    setUser({ username: res.data.username, display_name: res.data.display_name, role: res.data.role, avatar: res.data.avatar });
  }, []);

  const logout = useCallback(async () => {
    await apiFetch("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
