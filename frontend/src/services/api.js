import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export const api = axios.create({
  baseURL: BACKEND_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export function setAuthToken(token) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
}

export function getBackendUrl() {
  return BACKEND_URL;
}

// Auth
export const loginWithGoogle = (idToken) =>
  api.post('/api/auth/google', { id_token: idToken });

export const fetchMe = () => api.get('/api/auth/me');

export const logoutRequest = () => api.post('/api/auth/logout');

// Properties
export const getProperties = (params) => api.get('/api/properties', { params });

export const getMyProperties = (params) => api.get('/api/properties/my', { params });

export const getProperty = (id) => api.get(`/api/properties/${id}`);

export const createProperty = (data) => api.post('/api/properties', data);

export const updateProperty = (id, data) => api.put(`/api/properties/${id}`, data);

export const deleteProperty = (id) => api.delete(`/api/properties/${id}`);

export const searchProperties = (data) => api.post('/api/properties/search', data);

export const realtimeSearch = (params) =>
  api.get('/api/properties/search/realtime', { params });

// Bookings
export const createBooking = (data) => api.post('/api/bookings', data);

export const getBookings = (params) => api.get('/api/bookings', { params });

export const getOwnerBookings = (params) => api.get('/api/bookings/owner', { params });

export const updateBookingStatus = (id, status) =>
  api.put(`/api/bookings/${id}/status`, null, { params: { status } });

// Payments
export const createCheckout = (bookingId, originUrl) =>
  api.post('/api/payments/create-checkout', {
    booking_id: bookingId,
    origin_url: originUrl,
  });

export const getPaymentStatus = (sessionId) =>
  api.get(`/api/payments/status/${sessionId}`);

// Messages
export const getConversations = (params) => api.get('/api/conversations', { params });

export const getMessages = (conversationId, params) =>
  api.get(`/api/conversations/${conversationId}/messages`, { params });

export const sendMessage = (data) => api.post('/api/messages', data);

export const markMessageRead = (id) => api.put(`/api/messages/${id}/read`);

// AI / analytics
export const estimatePrice = (data) => api.post('/api/ai/estimate-price', data);

export const getRecommendations = (params) =>
  api.get('/api/ai/recommendations', { params });

export const getAnalyticsDashboard = () => api.get('/api/analytics/dashboard');

export const getMarketTrends = () => api.get('/api/analytics/market-trends');

export const getBuyerBehavior = () => api.get('/api/analytics/buyer-behavior');

export default api;
