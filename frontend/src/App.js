import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import { Toaster } from './components/ui/sonner';
import { toast } from 'sonner';
import LandingPage from './pages/LandingPage';
import PropertiesPage from './pages/PropertiesPage';
import PropertyDetail from './pages/PropertyDetail';
import BookingsPage from './pages/BookingsPage';
import MessagesPage from './pages/MessagesPage';
import MyPropertiesPage from './pages/MyPropertiesPage';
import ProfilePage from './pages/ProfilePage';
import BookingSuccess from './pages/BookingSuccess';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

export const AuthContext = React.createContext();

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionToken, setSessionToken] = useState(null);
  const [gapiLoaded, setGapiLoaded] = useState(false);

  useEffect(() => {
    loadGoogleScript();
    checkAuth();
  }, []);

  const loadGoogleScript = () => {
    if (window.gapi) {
      setGapiLoaded(true);
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => {
      if (GOOGLE_CLIENT_ID) {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleGoogleSignIn,
        });
      }
      setGapiLoaded(true);
    };
    document.body.appendChild(script);
  };

  const handleGoogleSignIn = async (response) => {
    try {
      setLoading(true);
      const authResponse = await axios.post(`${BACKEND_URL}/api/auth/google`, {
        id_token: response.credential || response.id_token,
        access_token: response.access_token || null
      });

      const { session_token, user: userData } = authResponse.data;
      localStorage.setItem('session_token', session_token);
      setSessionToken(session_token);
      setUser(userData);
      toast.success(`Welcome, ${userData.name}!`);
    } catch (error) {
      console.error('Google sign-in failed:', error);
      toast.error('Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Handle OAuth callback from URL hash
    const hash = window.location.hash;
    if (hash.includes('id_token=')) {
      const idToken = hash.split('id_token=')[1].split('&')[0];
      if (idToken) {
        handleGoogleSignIn({ credential: idToken });
        window.history.replaceState(null, '', window.location.pathname);
      }
    }
  }, []);

  const checkAuth = async () => {
    // Check existing session
    const token = localStorage.getItem('session_token');
    if (token) {
      try {
        const response = await axios.get(`${BACKEND_URL}/api/auth/me`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setUser(response.data);
        setSessionToken(token);
      } catch (error) {
        console.error('Auth check failed:', error);
        localStorage.removeItem('session_token');
      }
    }
    setLoading(false);
  };

  const login = () => {
    if (!GOOGLE_CLIENT_ID) {
      toast.error('Google OAuth not configured. Please set REACT_APP_GOOGLE_CLIENT_ID');
      return;
    }

    if (window.google && window.google.accounts && window.google.accounts.id) {
      // Use Google Sign-In with One Tap
      window.google.accounts.id.prompt((notification) => {
        if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
          // Fallback to popup
          const width = 500;
          const height = 600;
          const left = window.screen.width / 2 - width / 2;
          const top = window.screen.height / 2 - height / 2;
          
          window.open(
            `https://accounts.google.com/o/oauth2/v2/auth?client_id=${GOOGLE_CLIENT_ID}&redirect_uri=${encodeURIComponent(window.location.origin)}&response_type=id_token&scope=openid%20email%20profile&nonce=${Math.random()}`,
            'Google Sign In',
            `width=${width},height=${height},left=${left},top=${top}`
          );
        }
      });
    } else {
      // Fallback: redirect to Google OAuth
      const redirectUri = encodeURIComponent(window.location.origin);
      window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${GOOGLE_CLIENT_ID}&redirect_uri=${redirectUri}&response_type=id_token&scope=openid%20email%20profile&nonce=${Math.random()}`;
    }
  };

  const logout = async () => {
    try {
      if (sessionToken) {
        await axios.post(
          `${BACKEND_URL}/api/auth/logout`,
          {},
          { headers: { Authorization: `Bearer ${sessionToken}` } }
        );
      }
    } catch (error) {
      console.error('Logout error:', error);
    }
    
    // Sign out from Google
    if (window.google && window.google.accounts) {
      window.google.accounts.id.disableAutoSelect();
    }
    
    localStorage.removeItem('session_token');
    setUser(null);
    setSessionToken(null);
    toast.success('Logged out successfully');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-spinner"></div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, sessionToken, login, logout }}>
      <BrowserRouter>
        <div className="App">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route
              path="/properties"
              element={user ? <PropertiesPage /> : <Navigate to="/" />}
            />
            <Route
              path="/properties/:id"
              element={user ? <PropertyDetail /> : <Navigate to="/" />}
            />
            <Route
              path="/bookings"
              element={user ? <BookingsPage /> : <Navigate to="/" />}
            />
            <Route
              path="/messages"
              element={user ? <MessagesPage /> : <Navigate to="/" />}
            />
            <Route
              path="/my-properties"
              element={user ? <MyPropertiesPage /> : <Navigate to="/" />}
            />
            <Route
              path="/profile"
              element={user ? <ProfilePage /> : <Navigate to="/" />}
            />
            <Route
              path="/booking-success"
              element={user ? <BookingSuccess /> : <Navigate to="/" />}
            />
          </Routes>
          <Toaster position="top-right" richColors />
        </div>
      </BrowserRouter>
    </AuthContext.Provider>
  );
}

export default App;
