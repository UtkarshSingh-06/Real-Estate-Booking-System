import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import { LoadingState } from './components/States';
import LandingPage from './pages/LandingPage';
import PropertiesPage from './pages/PropertiesPage';
import PropertyDetail from './pages/PropertyDetail';
import BookingsPage from './pages/BookingsPage';
import MessagesPage from './pages/MessagesPage';
import MyPropertiesPage from './pages/MyPropertiesPage';
import ProfilePage from './pages/ProfilePage';
import BookingSuccess from './pages/BookingSuccess';
import PriceEstimatePage from './pages/PriceEstimatePage';
import AnalyticsPage from './pages/AnalyticsPage';
import './App.css';

export { AuthContext } from './context/AuthContext';

function AppRoutes() {
  const { loading } = useAuth();

  if (loading) {
    return <LoadingState label="Checking session..." />;
  }

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/properties" element={<PropertiesPage />} />
        <Route path="/properties/:id" element={<PropertyDetail />} />
        <Route path="/bookings" element={<BookingsPage />} />
        <Route path="/messages" element={<MessagesPage />} />
        <Route path="/my-properties" element={<MyPropertiesPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/booking-success" element={<BookingSuccess />} />
        <Route path="/price-estimate" element={<PriceEstimatePage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
      </Route>
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="App">
          <AppRoutes />
          <Toaster position="top-right" richColors />
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
