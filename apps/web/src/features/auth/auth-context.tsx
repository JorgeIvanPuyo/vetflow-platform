"use client";

import {
  User,
  onAuthStateChanged,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signOut,
} from "firebase/auth";
import {
  ReactNode,
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { getFirebaseAuth } from "@/lib/firebase";
import { setAuthTokenProvider } from "@/lib/api";
import { setStoredActingTenantId } from "@/lib/acting-tenant";

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  isTokenLoading: boolean;
  isReady: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  getIdToken: () => Promise<string | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const isTokenLoading = false;

  useEffect(() => {
    let isMounted = true;
    const firebaseAuth = getFirebaseAuth();

    setAuthTokenProvider(async () =>
      getFirebaseAuth().currentUser?.getIdToken() ?? null,
    );

    const unsubscribe = onAuthStateChanged(firebaseAuth, (nextUser) => {
      if (!isMounted) {
        return;
      }

      setUser(nextUser);
      setIsLoading(false);

      // Token acquisition is part of the bounded backend session validation.
    });

    return () => {
      isMounted = false;
      unsubscribe();
      setAuthTokenProvider(null);
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isTokenLoading,
      isReady: !isLoading && !isTokenLoading,
      async login(email: string, password: string) {
        await signInWithEmailAndPassword(getFirebaseAuth(), email, password);
      },
      async logout() {
        setStoredActingTenantId(null);
        await signOut(getFirebaseAuth());
      },
      async resetPassword(email: string) {
        await sendPasswordResetEmail(getFirebaseAuth(), email);
      },
      async getIdToken() {
        return getFirebaseAuth().currentUser?.getIdToken() ?? null;
      },
    }),
    [user, isLoading, isTokenLoading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return context;
}
