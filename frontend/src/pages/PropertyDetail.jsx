import React, { useState, useEffect, useContext } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AuthContext } from '../App';
import Navbar from '../components/Navbar';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { MapPin, Bed, Bath, Square, DollarSign, Calendar, MessageCircle } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const PropertyDetail = () => {
  const { id } = useParams();
  const { sessionToken, user } = useContext(AuthContext);
  const navigate = useNavigate();
  const [property, setProperty] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bookingData, setBookingData] = useState({
    booking_date: '',
    time_slot: '10:00 AM',
    deposit_amount: 0
  });
  const [bookingOpen, setBookingOpen] = useState(false);
  const [messageOpen, setMessageOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [similarProperties, setSimilarProperties] = useState([]);

  useEffect(() => {
    fetchProperty();
  }, [id]);

  useEffect(() => {
    if (!id || !sessionToken) return;
    axios.get(`${BACKEND_URL}/api/ai/recommendations?property_id=${id}&limit=3`, {
      headers: { Authorization: `Bearer ${sessionToken}` }
    }).then((res) => setSimilarProperties(res.data.recommendations || [])).catch(() => {});
  }, [id, sessionToken]);

  const fetchProperty = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/properties/${id}`, {
        headers: { Authorization: `Bearer ${sessionToken}` }
      });
      setProperty(response.data);
      setBookingData({ ...bookingData, deposit_amount: response.data.price * 0.1 });
    } catch (error) {
      console.error('Error fetching property:', error);
      toast.error('Failed to load property');
    } finally {
      setLoading(false);
    }
  };

  const handleBooking = async () => {
    if (!bookingData.booking_date) {
      toast.error('Please select a date');
      return;
    }

    try {
      const response = await axios.post(
        `${BACKEND_URL}/api/bookings`,
        bookingData,
        { headers: { Authorization: `Bearer ${sessionToken}` } }
      );
      const bookingId = response.data.id;
      toast.success('Booking created! Proceeding to payment...');
      
      // Create payment checkout
      const paymentResponse = await axios.post(
        `${BACKEND_URL}/api/payments/create-checkout`,
        {
          booking_id: bookingId,
          origin_url: window.location.origin
        },
        { headers: { Authorization: `Bearer ${sessionToken}` } }
      );
      
      // Redirect to Stripe
      window.location.href = paymentResponse.data.url;
    } catch (error) {
      console.error('Error creating booking:', error);
      toast.error('Failed to create booking');
    }
  };

  const handleSendMessage = async () => {
    if (!message.trim()) {
      toast.error('Please enter a message');
      return;
    }

    try {
      await axios.post(
        `${BACKEND_URL}/api/messages`,
        {
          receiver_id: property.owner_id,
          property_id: property.id,
          message: message
        },
        { headers: { Authorization: `Bearer ${sessionToken}` } }
      );
      toast.success('Message sent!');
      setMessageOpen(false);
      setMessage('');
      navigate('/messages');
    } catch (error) {
      console.error('Error sending message:', error);
      toast.error('Failed to send message');
    }
  };

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

  if (!property) {
    return (
      <div>
        <Navbar />
        <div className="flex items-center justify-center min-h-[calc(100vh-64px)]">
          <p className="text-xl text-gray-500">Property not found</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="property-detail-page">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Images */}
            <div className="relative h-96 rounded-xl overflow-hidden bg-gradient-to-br from-blue-100 to-cyan-100">
              {property.images && property.images.length > 0 ? (
                <img
                  src={property.images[0]}
                  alt={property.title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="flex items-center justify-center h-full">
                  <MapPin className="h-24 w-24 text-gray-400" />
                </div>
              )}
              <Badge className="absolute top-4 right-4 text-lg py-1 px-3">
                {property.property_type}
              </Badge>
            </div>

            {/* Details */}
            <Card className="glass">
              <CardContent className="pt-6 space-y-6">
                <div>
                  <h1 className="text-4xl font-bold mb-3">{property.title}</h1>
                  <div className="flex items-center text-gray-600 text-lg">
                    <MapPin className="h-5 w-5 mr-2" />
                    <span>{property.address}</span>
                  </div>
                </div>

                <div className="flex items-center text-[hsl(var(--primary))] text-4xl font-bold">
                  <DollarSign className="h-8 w-8" />
                  {property.price.toLocaleString()}
                </div>

                <div className="grid grid-cols-3 gap-6 py-6 border-t border-b">
                  <div className="text-center">
                    <Bed className="h-8 w-8 mx-auto mb-2 text-gray-600" />
                    <div className="text-2xl font-bold">{property.bedrooms}</div>
                    <div className="text-sm text-gray-600">Bedrooms</div>
                  </div>
                  <div className="text-center">
                    <Bath className="h-8 w-8 mx-auto mb-2 text-gray-600" />
                    <div className="text-2xl font-bold">{property.bathrooms}</div>
                    <div className="text-sm text-gray-600">Bathrooms</div>
                  </div>
                  <div className="text-center">
                    <Square className="h-8 w-8 mx-auto mb-2 text-gray-600" />
                    <div className="text-2xl font-bold">{property.area_sqft}</div>
                    <div className="text-sm text-gray-600">Sqft</div>
                  </div>
                </div>

                <div>
                  <h2 className="text-2xl font-bold mb-3">Description</h2>
                  <p className="text-gray-700 leading-relaxed">{property.description}</p>
                </div>

                {property.amenities && property.amenities.length > 0 && (
                  <div>
                    <h2 className="text-2xl font-bold mb-3">Amenities</h2>
                    <div className="flex flex-wrap gap-2">
                      {property.amenities.map((amenity, index) => (
                        <Badge key={index} variant="secondary" className="text-sm py-1 px-3">
                          {amenity}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {similarProperties.length > 0 && (
                  <div>
                    <h2 className="text-2xl font-bold mb-3">Similar Properties</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      {similarProperties.map((p) => (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => navigate(`/properties/${p.id}`)}
                          className="text-left rounded-lg border p-3 hover:bg-muted/50 transition-colors"
                        >
                          <div className="font-medium line-clamp-1">{p.title}</div>
                          <div className="text-sm text-[hsl(var(--primary))] font-bold mt-1">
                            ${p.price?.toLocaleString()}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">{p.bedrooms} bed · {p.area_sqft} sqft</div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Booking Card */}
            {user.id !== property.owner_id && (
              <Card className="glass sticky top-20">
                <CardContent className="pt-6 space-y-4">
                  <h3 className="text-2xl font-bold">Book a Viewing</h3>
                  <p className="text-gray-600">Schedule a visit to this property</p>
                  <div className="space-y-3">
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <div className="text-sm text-gray-600">Deposit Required</div>
                      <div className="text-2xl font-bold text-[hsl(var(--primary))]">
                        ${(property.price * 0.1).toLocaleString()}
                      </div>
                    </div>
                  </div>

                  <Dialog open={bookingOpen} onOpenChange={setBookingOpen}>
                    <DialogTrigger asChild>
                      <Button className="w-full bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90" size="lg" data-testid="book-viewing-btn">
                        <Calendar className="mr-2 h-5 w-5" />
                        Book Viewing
                      </Button>
                    </DialogTrigger>
                    <DialogContent data-testid="booking-dialog">
                      <DialogHeader>
                        <DialogTitle>Schedule a Viewing</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div>
                          <Label>Select Date</Label>
                          <Input
                            type="date"
                            value={bookingData.booking_date}
                            onChange={(e) => setBookingData({ ...bookingData, booking_date: e.target.value })}
                            min={new Date().toISOString().split('T')[0]}
                            data-testid="booking-date-input"
                          />
                        </div>
                        <div>
                          <Label>Time Slot</Label>
                          <select
                            className="w-full p-2 border rounded-md"
                            value={bookingData.time_slot}
                            onChange={(e) => setBookingData({ ...bookingData, time_slot: e.target.value })}
                            data-testid="time-slot-select"
                          >
                            <option>10:00 AM</option>
                            <option>2:00 PM</option>
                            <option>4:00 PM</option>
                            <option>6:00 PM</option>
                          </select>
                        </div>
                        <div className="bg-blue-50 p-4 rounded-lg">
                          <div className="text-sm text-gray-600">Deposit Amount</div>
                          <div className="text-xl font-bold">${bookingData.deposit_amount.toLocaleString()}</div>
                        </div>
                        <Button className="w-full" onClick={handleBooking} data-testid="confirm-booking-btn">
                          Proceed to Payment
                        </Button>
                      </div>
                    </DialogContent>
                  </Dialog>

                  <Dialog open={messageOpen} onOpenChange={setMessageOpen}>
                    <DialogTrigger asChild>
                      <Button variant="outline" className="w-full" size="lg" data-testid="contact-owner-btn">
                        <MessageCircle className="mr-2 h-5 w-5" />
                        Contact Owner
                      </Button>
                    </DialogTrigger>
                    <DialogContent data-testid="message-dialog">
                      <DialogHeader>
                        <DialogTitle>Send Message</DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div>
                          <Label>Message</Label>
                          <Textarea
                            placeholder="Hi, I'm interested in this property..."
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            rows={5}
                            data-testid="message-textarea"
                          />
                        </div>
                        <Button className="w-full" onClick={handleSendMessage} data-testid="send-message-btn">
                          Send Message
                        </Button>
                      </div>
                    </DialogContent>
                  </Dialog>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PropertyDetail;
