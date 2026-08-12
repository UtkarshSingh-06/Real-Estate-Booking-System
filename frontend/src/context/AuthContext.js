import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { toast } from 'sonner';
import {
  fetchMe,
  loginWithGoogle,
  logoutRequest,
  setAuthToken,
} from '../services/api';

const AuthContext = createContext(null);

const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;
const TOKEN_KEY = 'session_token';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [sessionToken, setSessionToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [gisReady, setGisReady] = useState(false);

  const applySession = useCallback((token, userData) => {
    localStorage.setItem(TOKEN_KEY, token);
    setSessionToken(token);
    setAuthToken(token);
    setUser(userData);
  }, []);

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setSessionToken(null);
    setAuthToken(null);
    setUser(null);
  }, []);

  const handleGoogleCredential = useCallback(
    async (response) => {
      const idToken = response?.credential || response?.id_token;
      if (!idToken) {
        toast.error('Google sign-in failed');
        return;
      }
      try {
        setLoading(true);
        const { data } = await loginWithGoogle(idToken);
        applySession(data.session_token, data.user);
        toast.success(`Welcome, ${data.user.name}!`);
      } catch (error) {
        console.error('Google sign-in failed:', error);
        toast.error('Authentication failed');
      } finally {
        setLoading(false);
      }
    },
    [applySession]
  );

  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => {
      if (GOOGLE_CLIENT_ID && window.google?.accounts?.id) {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleGoogleCredential,
          auto_select: false,
          cancel_on_tap_outside: true,
        });
      }
      setGisReady(true);
    };
    document.body.appendChild(script);

    return () => {
      script.remove();
    };
  }, [handleGoogleCredential]);

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        setLoading(false);
        return;
      }
      setAuthToken(token);
      try {
        const { data } = await fetchMe();
        setSessionToken(token);
        setUser(data);
      } catch (error) {
        clearSession();
      } finally {
        setLoading(false);
      }
    };
    checkAuth();
  }, [clearSession]);

  const login = useCallback(() => {
    if (!GOOGLE_CLIENT_ID) {
      toast.error('Google OAuth not configured. Set REACT_APP_GOOGLE_CLIENT_ID.');
      return;
    }
    if (!gisReady || !window.google?.accounts?.id) {
      toast.error('Google Sign-In is still loading. Please try again.');
      return;
    }
    window.google.accounts.id.prompt((notification) => {
      if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
        // Render a temporary GIS button and click it (popup OAuth code flow alternative)
        const container = document.createElement('div');
        container.style.position = 'fixed';
        container.style.left = '-9999px';
        document.body.appendChild(container);
        window.google.accounts.id.renderButton(container, {
          type: 'standard',
          theme: 'outline',
          size: 'large',
        });
        const btn = container.querySelector('div[role="button"]');
        if (btn) {
          btn.click();
        } else {
          toast.error('Unable to open Google Sign-In. Check OAuth client settings.');
        }
        setTimeout(() => container.remove(), 2000);
      }
    });
  }, [gisReady]);

  const logout = useCallback(async () => {
    try {
      if (sessionToken) {
        await logoutRequest();
      }
    } catch (error) {
      console.error('Logout error:', error);
    }
    if (window.google?.accounts?.id) {
      window.google.accounts.id.disableAutoSelect();
    }
    clearSession();
    toast.success('Logged out successfully');
  }, [clearSession, sessionToken]);

  const value = useMemo(
    () => ({
      user,
      sessionToken,
      loading,
      login,
      logout,
      isAuthenticated: Boolean(user && sessionToken),
    }),
    [user, sessionToken, loading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}

export { AuthContext };
