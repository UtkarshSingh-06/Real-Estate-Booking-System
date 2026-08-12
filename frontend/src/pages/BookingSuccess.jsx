import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getPaymentStatus } from '../services/api';
import Navbar from '../components/Navbar';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { CheckCircle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const BookingSuccess = () => {
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('session_id');
  useAuth();
  const navigate = useNavigate();
  const [status, setStatus] = useState('checking');
  const [bookingStatus, setBookingStatus] = useState(null);
  const [paymentStatus, setPaymentStatus] = useState(null);
  const [attempts, setAttempts] = useState(0);
  const maxAttempts = 5;

  useEffect(() => {
    if (sessionId) {
      pollPaymentStatus();
    }
  }, [sessionId, attempts]);

  const pollPaymentStatus = async () => {
    if (attempts >= maxAttempts) {
      setStatus('timeout');
      return;
    }

    try {
      const response = await getPaymentStatus(sessionId);
      setBookingStatus(response.data.booking_status || null);
      setPaymentStatus(response.data.payment_status || null);

      if (response.data.booking_status === 'confirmed') {
        setStatus('success');
        toast.success('Payment confirmed by the server');
      } else if (response.data.status === 'expired') {
        setStatus('expired');
        toast.error('Payment session expired');
      } else {
        // Continue polling
        setTimeout(() => setAttempts(prev => prev + 1), 2000);
      }
    } catch (error) {
      console.error('Error checking payment status:', error);
      setStatus('error');
      toast.error('Error verifying payment');
    }
  };

  return (
    <div>
      <Navbar />
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-16" data-testid="booking-success-page">
        <Card className="glass">
          <CardContent className="pt-12 pb-12">
            {status === 'checking' && (
              <div className="text-center space-y-6">
                <Loader2 className="h-16 w-16 mx-auto animate-spin text-[hsl(var(--primary))]" />
                <h2 className="text-2xl font-bold">Verifying Payment...</h2>
                <p className="text-gray-600">
                  Payment confirmation is completed securely by the payment webhook.
                </p>
                {(paymentStatus || bookingStatus) && (
                  <p className="text-sm text-gray-500">
                    Payment: {paymentStatus || 'pending'} · Booking: {bookingStatus || 'payment_pending'}
                  </p>
                )}
              </div>
            )}

            {status === 'success' && (
              <div className="text-center space-y-6 fade-in">
                <div className="bg-green-100 rounded-full w-24 h-24 mx-auto flex items-center justify-center">
                  <CheckCircle className="h-16 w-16 text-green-600" />
                </div>
                <h2 className="text-3xl font-bold text-gray-900">Booking Confirmed!</h2>
                <p className="text-gray-600 text-lg">
                  The payment webhook has confirmed your booking.
                </p>
                {bookingStatus && <p className="text-gray-500">Booking status: {bookingStatus}</p>}
                <p className="text-gray-500">
                  You will receive a confirmation email shortly with all the details.
                </p>
                <div className="flex flex-col sm:flex-row gap-4 justify-center mt-8">
                  <Button
                    onClick={() => navigate('/bookings')}
                    className="bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                    data-testid="view-bookings-btn"
                  >
                    View My Bookings
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => navigate('/properties')}
                    data-testid="browse-properties-btn"
                  >
                    Browse More Properties
                  </Button>
                </div>
              </div>
            )}

            {status === 'expired' && (
              <div className="text-center space-y-6">
                <div className="bg-red-100 rounded-full w-24 h-24 mx-auto flex items-center justify-center">
                  <CheckCircle className="h-16 w-16 text-red-600" />
                </div>
                <h2 className="text-3xl font-bold text-gray-900">Session Expired</h2>
                <p className="text-gray-600 text-lg">
                  Your payment session has expired. Please try again.
                </p>
                <Button
                  onClick={() => navigate('/properties')}
                  className="bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                >
                  Back to Properties
                </Button>
              </div>
            )}

            {status === 'timeout' && (
              <div className="text-center space-y-6">
                <h2 className="text-2xl font-bold text-gray-900">Payment Verification Timeout</h2>
                <p className="text-gray-600">
                  The payment webhook has not confirmed the booking yet. Check My Bookings for the latest status.
                </p>
                {bookingStatus && <p className="text-gray-500">Booking status: {bookingStatus}</p>}
                <div className="flex flex-col sm:flex-row gap-4 justify-center">
                  <Button onClick={() => navigate('/bookings')}>
                    View Bookings
                  </Button>
                  <Button variant="outline" onClick={() => navigate('/properties')}>
                    Back to Properties
                  </Button>
                </div>
              </div>
            )}

            {status === 'error' && (
              <div className="text-center space-y-6">
                <h2 className="text-2xl font-bold text-gray-900">Verification Error</h2>
                <p className="text-gray-600">
                  There was an error verifying your payment. Please contact support.
                </p>
                <Button onClick={() => navigate('/properties')}>
                  Back to Properties
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default BookingSuccess;
