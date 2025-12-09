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
import LoginPage from './pages/LoginPage';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export const AuthContext = React.createContext();

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionToken, setSessionToken] = useState(null);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
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
        setUser(null);
        setSessionToken(null);
      }
    }
    setLoading(false);
  };

  const completeLogin = (userData, token) => {
    localStorage.setItem('session_token', token);
    setSessionToken(token);
    setUser(userData);
    setLoading(false);
    toast.success(`Welcome, ${userData.name}!`);
  };

  const login = () => {
    window.location.href = '/login';
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
    <AuthContext.Provider value={{ user, sessionToken, login, logout, completeLogin }}>
      <BrowserRouter>
        <div className="App">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
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
