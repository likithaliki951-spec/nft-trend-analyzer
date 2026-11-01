"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearAuthToken, getAuthToken, setAuthToken } from "@/lib/api";

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string, confirm: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  useEffect(() => {
    const existingToken = getAuthToken();
    if (existingToken) {
      setToken(existingToken);
      api
        .getMe()
        .then((userData) => {
          setUser(userData);
        })
        .catch(() => {
          clearAuthToken();
          setUser(null);
          setToken(null);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const res = await api.login({ email, password });
    if (res.access_token && res.user) {
      setAuthToken(res.access_token);
      setToken(res.access_token);
      setUser(res.user);
      router.push("/dashboard");
    }
  };

  const register = async (email: string, name: string, password: string, confirm: string) => {
    const res = await api.register({
      email,
      name,
      password,
      password_confirm: confirm,
    });
    if (res.access_token && res.user) {
      setAuthToken(res.access_token);
      setToken(res.access_token);
      setUser(res.user);
      router.push("/dashboard");
    }
  };

  const logout = () => {
    clearAuthToken();
    setUser(null);
    setToken(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
