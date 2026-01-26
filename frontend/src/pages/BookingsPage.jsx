import React, { useState, useEffect, useContext } from 'react';
import axios from 'axios';
import { AuthContext } from '../App';
import Navbar from '../components/Navbar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Calendar, MapPin, Clock, DollarSign, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const BookingsPage = () => {
  const { sessionToken, user } = useContext(AuthContext);
  const [bookings, setBookings] = useState([]);
  const [ownerBookings, setOwnerBookings] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBookings();
  }, []);

  const fetchBookings = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/bookings`, {
        headers: { Authorization: `Bearer ${sessionToken}` }
      });
      setBookings(response.data.bookings);

      if (['owner', 'agent', 'admin'].includes(user.role)) {
        const ownerResponse = await axios.get(`${BACKEND_URL}/api/bookings/owner`, {
          headers: { Authorization: `Bearer ${sessionToken}` }
        });
        setOwnerBookings(ownerResponse.data.bookings);
      }
    } catch (error) {
      console.error('Error fetching bookings:', error);
      toast.error('Failed to load bookings');
    } finally {
      setLoading(false);
    }
  };

  const updateBookingStatus = async (bookingId, status) => {
    try {
      await axios.put(
        `${BACKEND_URL}/api/bookings/${bookingId}/status?status=${status}`,
        {},
        { headers: { Authorization: `Bearer ${sessionToken}` } }
      );
      toast.success(`Booking ${status}`);
      fetchBookings();
    } catch (error) {
      console.error('Error updating booking:', error);
      toast.error('Failed to update booking');
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'confirmed':
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case 'rejected':
        return <XCircle className="h-5 w-5 text-red-600" />;
      case 'cancelled':
        return <XCircle className="h-5 w-5 text-gray-600" />;
      default:
        return <AlertCircle className="h-5 w-5 text-yellow-600" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'confirmed':
        return 'bg-green-100 text-green-800';
      case 'rejected':
        return 'bg-red-100 text-red-800';
      case 'cancelled':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-yellow-100 text-yellow-800';
    }
  };

  const BookingCard = ({ booking, isOwner = false }) => (
    <Card className="glass" data-testid={`booking-card-${booking.id}`}>
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-xl">Booking #{booking.id.slice(-8)}</CardTitle>
            <p className="text-sm text-gray-600 mt-1">Property ID: {booking.property_id}</p>
          </div>
          <div className="flex items-center gap-2">
            {getStatusIcon(booking.status)}
            <Badge className={getStatusColor(booking.status)}>
              {booking.status}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-2">
            <Calendar className="h-5 w-5 text-gray-500" />
            <div>
              <div className="text-sm text-gray-600">Date</div>
              <div className="font-medium">{booking.booking_date}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-gray-500" />
            <div>
              <div className="text-sm text-gray-600">Time</div>
              <div className="font-medium">{booking.time_slot}</div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 pt-3 border-t">
          <DollarSign className="h-5 w-5 text-gray-500" />
          <div>
            <div className="text-sm text-gray-600">Deposit</div>
            <div className="font-bold text-lg">${booking.deposit_amount.toLocaleString()}</div>
          </div>
          <Badge className={booking.payment_status === 'paid' ? 'bg-green-100 text-green-800 ml-auto' : 'bg-yellow-100 text-yellow-800 ml-auto'}>
            {booking.payment_status}
          </Badge>
        </div>

        {isOwner && booking.status === 'pending' && (
          <div className="flex gap-3 pt-3 border-t">
            <Button
              className="flex-1 bg-green-600 hover:bg-green-700"
              onClick={() => updateBookingStatus(booking.id, 'confirmed')}
              data-testid={`confirm-booking-${booking.id}`}
            >
              <CheckCircle className="mr-2 h-4 w-4" />
              Confirm
            </Button>
            <Button
              variant="destructive"
              className="flex-1"
              onClick={() => updateBookingStatus(booking.id, 'rejected')}
              data-testid={`reject-booking-${booking.id}`}
            >
              <XCircle className="mr-2 h-4 w-4" />
              Reject
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );

  if (loading) {
    return (
      <div>
        <Navbar />
        <div className="flex items-center justify-center min-h-[calc(100vh-64px)]">
          <div className="loading-spinner"></div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="bookings-page">
        <h1 className="text-4xl font-bold mb-8">My Bookings</h1>

        <Tabs defaultValue="my-bookings" className="space-y-6">
          <TabsList className="glass">
            <TabsTrigger value="my-bookings" data-testid="my-bookings-tab">My Bookings</TabsTrigger>
            {['owner', 'agent', 'admin'].includes(user.role) && (
              <TabsTrigger value="received-bookings" data-testid="received-bookings-tab">Received Bookings</TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="my-bookings">
            {bookings.length === 0 ? (
              <Card className="glass">
                <CardContent className="py-16 text-center">
                  <Calendar className="h-16 w-16 mx-auto mb-4 text-gray-400" />
                  <p className="text-xl text-gray-500">No bookings yet</p>
                  <p className="text-gray-400 mt-2">Start exploring properties to make your first booking!</p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {bookings.map((booking) => (
                  <BookingCard key={booking.id} booking={booking} />
                ))}
              </div>
            )}
          </TabsContent>

          {['owner', 'agent', 'admin'].includes(user.role) && (
            <TabsContent value="received-bookings">
              {ownerBookings.length === 0 ? (
                <Card className="glass">
                  <CardContent className="py-16 text-center">
                    <Calendar className="h-16 w-16 mx-auto mb-4 text-gray-400" />
                    <p className="text-xl text-gray-500">No bookings received</p>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {ownerBookings.map((booking) => (
                    <BookingCard key={booking.id} booking={booking} isOwner={true} />
                  ))}
                </div>
              )}
            </TabsContent>
          )}
        </Tabs>
      </div>
    </div>
  );
};

export default BookingsPage;
