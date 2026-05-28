/**
 * Auth context for Framekit web UI.
 * Stores JWT token in localStorage. Disabled when server has no users.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import type { AuthUser } from "@/lib/api/schemas";

const TOKEN_KEY = "framekit_token";

interface AuthContextValue {
  token: string | null;
  user: AuthUser | null;
  isLoading: boolean;
  login: (token: string, user: AuthUser) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  token: null,
  user: null,
  isLoading: false,
  login: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(!!localStorage.getItem(TOKEN_KEY));

  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setIsLoading(false);
      return;
    }
    import("@/lib/api/endpoints")
      .then(({ getAuthMe }) => getAuthMe(stored))
      .then((me) => {
        setToken(stored);
        setUser(me);
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setUser(null);
    };
    window.addEventListener("framekit:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("framekit:unauthorized", handleUnauthorized);
  }, []);

  const login = useCallback((newToken: string, newUser: AuthUser) => {
    localStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
    setUser(newUser);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
