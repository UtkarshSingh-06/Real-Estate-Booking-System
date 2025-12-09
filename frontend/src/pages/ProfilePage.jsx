import React, { useContext, useState } from 'react';
import axios from 'axios';
import { AuthContext } from '../App';
import Navbar from '../components/Navbar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { User, Mail, Phone, Shield } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const ProfilePage = () => {
  const { user, sessionToken } = useContext(AuthContext);
  const [formData, setFormData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    phone: user?.phone || '',
    role: user?.role || 'buyer'
  });

  const handleUpdate = async () => {
    toast.info('Profile updates are managed through your account settings');
  };

  return (
    <div>
      <Navbar />
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="profile-page">
        <h1 className="text-4xl font-bold mb-8">Profile</h1>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Profile Card */}
          <Card className="glass md:col-span-1">
            <CardContent className="pt-6">
              <div className="flex flex-col items-center text-center space-y-4">
                <Avatar className="h-24 w-24">
                  <AvatarImage src={user?.picture} alt={user?.name} />
                  <AvatarFallback className="text-2xl">{user?.name?.[0]}</AvatarFallback>
                </Avatar>
                <div>
                  <h2 className="text-2xl font-bold">{user?.name}</h2>
                  <p className="text-gray-600">{user?.email}</p>
                </div>
                <Badge className="text-sm py-1 px-3">
                  {user?.role}
                </Badge>
              </div>
            </CardContent>
          </Card>

          {/* Details Card */}
          <Card className="glass md:col-span-2">
            <CardHeader>
              <CardTitle>Account Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 gap-4">
                <div>
                  <Label>Full Name</Label>
                  <div className="flex items-center mt-2">
                    <User className="h-5 w-5 mr-2 text-gray-500" />
                    <Input
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      disabled
                      data-testid="name-input"
                    />
                  </div>
                </div>

                <div>
                  <Label>Email</Label>
                  <div className="flex items-center mt-2">
                    <Mail className="h-5 w-5 mr-2 text-gray-500" />
                    <Input
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      disabled
                      data-testid="email-input"
                    />
                  </div>
                </div>

                <div>
                  <Label>Phone</Label>
                  <div className="flex items-center mt-2">
                    <Phone className="h-5 w-5 mr-2 text-gray-500" />
                    <Input
                      placeholder="+1 (555) 123-4567"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      data-testid="phone-input"
                    />
                  </div>
                </div>

                <div>
                  <Label>Role</Label>
                  <div className="flex items-center mt-2">
                    <Shield className="h-5 w-5 mr-2 text-gray-500" />
                    <Select value={formData.role} onValueChange={(value) => setFormData({ ...formData, role: value })} disabled>
                      <SelectTrigger data-testid="role-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="buyer">Buyer</SelectItem>
                        <SelectItem value="owner">Owner</SelectItem>
                        <SelectItem value="agent">Agent</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              <div className="pt-4">
                <p className="text-sm text-gray-600 mb-4">
                  Profile information is synced with your Google account. To update your name or email, please update your Google account settings.
                </p>
                {/* <Button className="w-full" onClick={handleUpdate} data-testid="update-profile-btn">
                  Update Profile
                </Button> */}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Stats Card */}
        <Card className="glass mt-6">
          <CardHeader>
            <CardTitle>Account Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
              <div>
                <div className="text-4xl font-bold text-[hsl(var(--primary))]">0</div>
                <div className="text-gray-600 mt-2">Total Bookings</div>
              </div>
              <div>
                <div className="text-4xl font-bold text-[hsl(var(--primary))]">0</div>
                <div className="text-gray-600 mt-2">Messages Sent</div>
              </div>
              <div>
                <div className="text-4xl font-bold text-[hsl(var(--primary))]">0</div>
                <div className="text-gray-600 mt-2">Properties Viewed</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default ProfilePage;
