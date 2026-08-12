"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import * as api from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<User>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}

/**
 * Session state for the SPA.
 *
 * The session itself lives in an httpOnly cookie the browser sends on its own;
 * this only mirrors *who* that cookie belongs to, for rendering. Nothing here
 * is a credential, and every protected action is re-checked server-side.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setUser(await api.me());
    } catch {
      setUser(null); // 403 simply means nobody is signed in
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const signIn = useCallback(async (email: string, password: string) => {
    const signedIn = await api.login({ email, password });
    setUser(signedIn);
    return signedIn;
  }, []);

  const signOut = useCallback(async () => {
    await api.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, refresh, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
