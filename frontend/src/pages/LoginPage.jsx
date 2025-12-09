import React, { useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AuthContext } from '../App';
import Navbar from '../components/Navbar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';

const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001').replace(/\/$/, '');

const LoginPage = () => {
  const { user, completeLogin } = useContext(AuthContext);
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    role: 'buyer'
  });

  useEffect(() => {
    if (user) {
      navigate('/properties');
    }
  }, [user, navigate]);

  const submitLogin = async (payload) => {
    setLoading(true);
    try {
      const response = await axios.post(`${BACKEND_URL}/api/auth/login`, payload, {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (response.data && response.data.session_token && response.data.user) {
        completeLogin(response.data.user, response.data.session_token);
        toast.success(`Welcome, ${response.data.user.name}!`);
        navigate('/properties');
      } else {
        throw new Error('Invalid response from server');
      }
    } catch (error) {
      console.error('Login failed', error);
      let msg = 'Unable to sign you in. Please try again.';
      if (error.response) {
        msg = error.response.data?.detail || error.response.data?.message || msg;
      } else if (error.request) {
        msg = 'Cannot connect to server. Please make sure the backend is running.';
      } else {
        msg = error.message || msg;
      }
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.email) {
      toast.error('Please provide your name and email');
      return;
    }
    await submitLogin(formData);
  };

  const handleDemoAccount = async () => {
    const demoPayload = {
      name: 'Demo Buyer',
      email: `demo+${Math.floor(Math.random() * 100000)}@estatebook.com`,
      role: 'buyer'
    };
    setFormData(demoPayload);
    await submitLogin(demoPayload);
  };

  return (
    <div className="min-h-screen">
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-10" data-testid="login-page">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-8 items-stretch">
          <Card className="glass">
            <CardHeader>
              <CardTitle className="text-3xl">Sign in to EstateBook</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <Label className="text-sm font-medium">Full Name</Label>
                <Input
                  placeholder="Jane Doe"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  data-testid="login-name"
                />
              </div>
              <div>
                <Label className="text-sm font-medium">Email</Label>
                <Input
                  type="email"
                  placeholder="you@example.com"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  data-testid="login-email"
                />
              </div>
              <div>
                <Label className="text-sm font-medium">Role</Label>
                <Select
                  value={formData.role}
                  onValueChange={(value) => setFormData({ ...formData, role: value })}
                >
                  <SelectTrigger data-testid="login-role">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="buyer">Buyer</SelectItem>
                    <SelectItem value="owner">Owner</SelectItem>
                    <SelectItem value="agent">Agent</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button
                className="w-full bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                onClick={handleSubmit}
                disabled={loading}
                data-testid="login-submit"
              >
                {loading ? 'Signing in...' : 'Continue'}
              </Button>
              <Button
                variant="outline"
                className="w-full"
                onClick={handleDemoAccount}
                disabled={loading}
                data-testid="demo-login"
              >
                {loading ? 'Please wait...' : 'Use a demo account'}
              </Button>
            </CardContent>
          </Card>

          <Card className="glass bg-gradient-to-br from-blue-50 via-white to-cyan-50 border-none">
            <CardContent className="pt-8 space-y-6">
              <h2 className="text-2xl font-bold">All-in-one real estate workflow</h2>
              <ul className="space-y-3 text-gray-700">
                <li>• Browse and filter curated properties with live pricing</li>
                <li>• Book viewings with instant confirmations</li>
                <li>• Chat securely with property owners and agents</li>
                <li>• Track payments and booking history in one place</li>
              </ul>
              <div className="p-4 rounded-lg bg-white border">
                <p className="font-semibold mb-1">Need an owner account?</p>
                <p className="text-sm text-gray-600">
                  Choose "Owner" or "Agent" in the role selector to list and manage properties.
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;

