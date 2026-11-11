"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearAuthToken, getAuthToken, setAuthToken } from "@/lib/api";

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  account_status?: string;
  email_verified?: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  adminLogin: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string, confirm: string) => Promise<void>;
  setSession: (token: string, user: User, redirectPath?: string) => void;
  logout: (portal?: "user" | "admin") => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  const refreshUser = async () => {
    const existingToken = getAuthToken();
    if (!existingToken) {
      setUser(null);
      setToken(null);
      setIsLoading(false);
      return;
    }

    try {
      const userData = await api.getMe();
      setUser(userData);
      setToken(existingToken);
    } catch {
      clearAuthToken();
      setUser(null);
      setToken(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const login = async (email: string, password: string) => {
    const res = await api.userLogin({ email, password });
    if (res.access_token && res.user) {
      setAuthToken(res.access_token);
      setToken(res.access_token);
      setUser(res.user);
      router.push("/user/dashboard");
    }
  };

  const adminLogin = async (email: string, password: string) => {
    const res = await api.adminLogin({ email, password });
    if (res.access_token && res.user) {
      setAuthToken(res.access_token);
      setToken(res.access_token);
      setUser(res.user);
      router.push("/admin/dashboard");
    }
  };

  const register = async (email: string, name: string, password: string, confirm: string) => {
    const res = await api.userRegister({
      email,
      name,
      password,
      password_confirm: confirm,
    });
    if (res.access_token && res.user) {
      setAuthToken(res.access_token);
      setToken(res.access_token);
      setUser(res.user);
      router.push("/user/dashboard");
    }
  };

  const setSession = (newToken: string, newUser: User, redirectPath?: string) => {
    setAuthToken(newToken);
    setToken(newToken);
    setUser(newUser);
    if (redirectPath) {
      router.push(redirectPath);
    }
  };

  const logout = (portal: "user" | "admin" = "user") => {
    clearAuthToken();
    setUser(null);
    setToken(null);
    if (portal === "admin") {
      router.push("/admin/login");
    } else {
      router.push("/user/login");
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        adminLogin,
        register,
        setSession,
        logout,
        refreshUser,
      }}
    >
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
