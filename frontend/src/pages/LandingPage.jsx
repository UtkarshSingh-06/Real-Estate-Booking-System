import React, { useContext } from 'react';
import { AuthContext } from '../App';
import { useNavigate } from 'react-router-dom';
import { Building2, MapPin, Calendar, MessageCircle, Shield, Star } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';

const LandingPage = () => {
  const { user, login } = useContext(AuthContext);
  const navigate = useNavigate();

  React.useEffect(() => {
    if (user) {
      navigate('/properties');
    }
  }, [user, navigate]);

  const features = [
    {
      icon: MapPin,
      title: 'Search Properties',
      description: 'Find your dream home with advanced search filters and interactive maps'
    },
    {
      icon: Calendar,
      title: 'Easy Booking',
      description: 'Schedule property viewings instantly with our seamless booking system'
    },
    {
      icon: MessageCircle,
      title: 'Live Chat',
      description: 'Connect with property owners in real-time through our messaging platform'
    },
    {
      icon: Shield,
      title: 'Secure Payments',
      description: 'Safe and secure deposit payments powered by Stripe'
    }
  ];

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-50 via-cyan-50 to-teal-50 opacity-70"></div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24 md:py-32">
          <div className="text-center space-y-8">
            <div className="flex justify-center mb-6">
              <Building2 className="h-16 w-16 text-[hsl(var(--primary))]" />
            </div>
            <h1 className="text-5xl md:text-7xl font-bold text-gray-900">
              Find Your <span className="gradient-text">Perfect Home</span>
            </h1>
            <p className="text-xl md:text-2xl text-gray-600 max-w-3xl mx-auto">
              Discover, book, and connect with property owners in real-time. Your dream home is just a click away.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center mt-8">
              <Button
                size="lg"
                className="text-lg px-8 py-6 bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                onClick={login}
                data-testid="get-started-btn"
              >
                Get Started
              </Button>
              <Button
                size="lg"
                variant="outline"
                className="text-lg px-8 py-6"
                onClick={login}
              >
                Sign In
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">Why Choose EstateBook?</h2>
            <p className="text-xl text-gray-600">Everything you need to find and book your perfect property</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <Card key={index} className="glass border-2 hover:shadow-xl transition-all duration-300 fade-in" style={{ animationDelay: `${index * 100}ms` }}>
                  <CardContent className="pt-6">
                    <div className="flex flex-col items-center text-center space-y-4">
                      <div className="p-4 bg-gradient-to-br from-blue-100 to-cyan-100 rounded-full">
                        <Icon className="h-8 w-8 text-[hsl(var(--primary))]" />
                      </div>
                      <h3 className="text-xl font-semibold text-gray-900">{feature.title}</h3>
                      <p className="text-gray-600">{feature.description}</p>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </div>

      {/* Stats Section */}
      <div className="py-16 bg-gradient-to-r from-blue-600 to-cyan-600 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-center">
            <div>
              <div className="text-5xl font-bold mb-2">10K+</div>
              <div className="text-xl opacity-90">Properties Listed</div>
            </div>
            <div>
              <div className="text-5xl font-bold mb-2">50K+</div>
              <div className="text-xl opacity-90">Happy Customers</div>
            </div>
            <div>
              <div className="text-5xl font-bold mb-2">4.9</div>
              <div className="text-xl opacity-90 flex items-center justify-center gap-2">
                <Star className="h-6 w-6 fill-current" />
                Average Rating
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="py-20 bg-gray-50">
        <div className="max-w-4xl mx-auto text-center px-4 sm:px-6 lg:px-8">
          <h2 className="text-4xl font-bold text-gray-900 mb-6">Ready to Find Your Dream Home?</h2>
          <p className="text-xl text-gray-600 mb-8">Join thousands of satisfied customers who found their perfect property with EstateBook</p>
          <Button
            size="lg"
            className="text-lg px-12 py-6 bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
            onClick={login}
          >
            Start Your Journey
          </Button>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <p className="text-gray-400">© 2025 EstateBook. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
