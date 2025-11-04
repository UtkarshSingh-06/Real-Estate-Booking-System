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

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export const AuthContext = React.createContext();

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionToken, setSessionToken] = useState(null);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    // Check for session_id in URL (from OAuth redirect)
    const hash = window.location.hash;
    if (hash.includes('session_id=')) {
      const sessionId = hash.split('session_id=')[1].split('&')[0];
      await processSession(sessionId);
      // Clean URL
      window.history.replaceState(null, '', window.location.pathname);
      return;
    }

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

  const processSession = async (sessionId) => {
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/session`, {
        session_id: sessionId
      });
      const { session_token, user: userData } = response.data;
      localStorage.setItem('session_token', session_token);
      setSessionToken(session_token);
      setUser(userData);
      toast.success(`Welcome, ${userData.name}!`);
    } catch (error) {
      console.error('Session processing failed:', error);
      toast.error('Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const login = () => {
    const redirectUrl = `${window.location.origin}/properties`;
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const logout = async () => {
    try {
      await axios.post(
        `${BACKEND_URL}/api/auth/logout`,
        {},
        { headers: { Authorization: `Bearer ${sessionToken}` } }
      );
    } catch (error) {
      console.error('Logout error:', error);
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
