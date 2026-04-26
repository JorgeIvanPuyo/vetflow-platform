"use client";

import {
  User,
  onAuthStateChanged,
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

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  isTokenLoading: boolean;
  isReady: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  getIdToken: () => Promise<string | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTokenLoading, setIsTokenLoading] = useState(false);

  useEffect(() => {
    let isMounted = true;
    const firebaseAuth = getFirebaseAuth();

    setAuthTokenProvider(async () =>
      getFirebaseAuth().currentUser?.getIdToken() ?? null,
    );

    const unsubscribe = onAuthStateChanged(firebaseAuth, async (nextUser) => {
      if (!isMounted) {
        return;
      }

      setUser(nextUser);
      setIsLoading(false);

      if (!nextUser) {
        setIsTokenLoading(false);
        return;
      }

      setIsTokenLoading(true);
      try {
        await nextUser.getIdToken();
      } finally {
        if (isMounted) {
          setIsTokenLoading(false);
        }
      }
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
        await signOut(getFirebaseAuth());
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
