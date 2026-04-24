"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

// ─── Types ──────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  role: "patient" | "doctor";
  firstName: string;
  lastName: string;
}

interface RegisterData {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  role: "patient" | "doctor";
  specialty?: string;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
}

// ─── Context ─────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

// ─── Provider ────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // On mount, check if there is an active session
  useEffect(() => {
    async function fetchMe() {
      try {
        const res = await fetch("/api/auth/me", {
          credentials: "include",
        });
        if (res.ok) {
          const data = await res.json();
          setUser(data.user);
        } else {
          setUser(null);
        }
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    fetchMe();
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<User> => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || "Login failed");
    }

    const data = await res.json();
    const loggedInUser: User = {
      id: data.user?.id ?? "",
      email: data.user?.email ?? email,
      role: data.user?.role ?? "patient",
      firstName: data.user?.first_name ?? "",
      lastName: data.user?.last_name ?? "",
    };
    setUser(loggedInUser);
    return loggedInUser;
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // ignore network errors on logout
    }
    setUser(null);
    router.push("/login");
  }, [router]);

  const register = useCallback(async (data: RegisterData): Promise<void> => {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.detail || errorData.message || "Registration failed");
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register }}>
      {children}
    </AuthContext.Provider>
  );
}

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
