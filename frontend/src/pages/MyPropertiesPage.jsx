import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AuthContext } from '../App';
import Navbar from '../components/Navbar';
import { Card, CardContent, CardFooter } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Plus, MapPin, Bed, Bath, Square, DollarSign, Edit, Trash } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const MyPropertiesPage = () => {
  const { sessionToken, user } = useContext(AuthContext);
  const navigate = useNavigate();
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    address: '',
    price: '',
    property_type: 'apartment',
    area_sqft: '',
    bedrooms: '',
    bathrooms: '',
    amenities: '',
    images: []
  });

  useEffect(() => {
    if (!['owner', 'agent', 'admin'].includes(user.role)) {
      navigate('/properties');
      return;
    }
    fetchProperties();
  }, []);

  const fetchProperties = async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/properties/my`, {
        headers: { Authorization: `Bearer ${sessionToken}` }
      });
      setProperties(response.data.properties);
    } catch (error) {
      console.error('Error fetching properties:', error);
      toast.error('Failed to load properties');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!formData.title || !formData.description || !formData.address || !formData.price) {
      toast.error('Please fill in all required fields');
      return;
    }

    try {
      const propertyData = {
        ...formData,
        price: parseFloat(formData.price),
        area_sqft: parseFloat(formData.area_sqft),
        bedrooms: parseInt(formData.bedrooms),
        bathrooms: parseInt(formData.bathrooms),
        amenities: formData.amenities.split(',').map(a => a.trim()).filter(a => a)
      };

      await axios.post(
        `${BACKEND_URL}/api/properties`,
        propertyData,
        { headers: { Authorization: `Bearer ${sessionToken}` } }
      );
      
      toast.success('Property created successfully!');
      setDialogOpen(false);
      setFormData({
        title: '',
        description: '',
        address: '',
        price: '',
        property_type: 'apartment',
        area_sqft: '',
        bedrooms: '',
        bathrooms: '',
        amenities: '',
        images: []
      });
      fetchProperties();
    } catch (error) {
      console.error('Error creating property:', error);
      toast.error('Failed to create property');
    }
  };

  const handleDelete = async (propertyId) => {
    if (!window.confirm('Are you sure you want to delete this property?')) return;

    try {
      await axios.delete(`${BACKEND_URL}/api/properties/${propertyId}`, {
        headers: { Authorization: `Bearer ${sessionToken}` }
      });
      toast.success('Property deleted');
      fetchProperties();
    } catch (error) {
      console.error('Error deleting property:', error);
      toast.error('Failed to delete property');
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

  return (
    <div>
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-8" data-testid="my-properties-page">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold">My Properties</h1>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button className="bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90" data-testid="add-property-btn">
                <Plus className="mr-2 h-5 w-5" />
                Add Property
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="add-property-dialog">
              <DialogHeader>
                <DialogTitle>Add New Property</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div>
                  <Label>Title *</Label>
                  <Input
                    placeholder="Beautiful 2BR Apartment"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    data-testid="property-title-input"
                  />
                </div>
                <div>
                  <Label>Description *</Label>
                  <Textarea
                    placeholder="Describe your property..."
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={3}
                    data-testid="property-description-input"
                  />
                </div>
                <div>
                  <Label>Address *</Label>
                  <Input
                    placeholder="123 Main St, New York, NY"
                    value={formData.address}
                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                    data-testid="property-address-input"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Price ($) *</Label>
                    <Input
                      type="number"
                      placeholder="500000"
                      value={formData.price}
                      onChange={(e) => setFormData({ ...formData, price: e.target.value })}
                      data-testid="property-price-input"
                    />
                  </div>
                  <div>
                    <Label>Property Type *</Label>
                    <Select value={formData.property_type} onValueChange={(value) => setFormData({ ...formData, property_type: value })}>
                      <SelectTrigger data-testid="property-type-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="apartment">Apartment</SelectItem>
                        <SelectItem value="house">House</SelectItem>
                        <SelectItem value="villa">Villa</SelectItem>
                        <SelectItem value="condo">Condo</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <Label>Area (sqft) *</Label>
                    <Input
                      type="number"
                      placeholder="1200"
                      value={formData.area_sqft}
                      onChange={(e) => setFormData({ ...formData, area_sqft: e.target.value })}
                      data-testid="property-area-input"
                    />
                  </div>
                  <div>
                    <Label>Bedrooms *</Label>
                    <Input
                      type="number"
                      placeholder="2"
                      value={formData.bedrooms}
                      onChange={(e) => setFormData({ ...formData, bedrooms: e.target.value })}
                      data-testid="property-bedrooms-input"
                    />
                  </div>
                  <div>
                    <Label>Bathrooms *</Label>
                    <Input
                      type="number"
                      placeholder="2"
                      value={formData.bathrooms}
                      onChange={(e) => setFormData({ ...formData, bathrooms: e.target.value })}
                      data-testid="property-bathrooms-input"
                    />
                  </div>
                </div>
                <div>
                  <Label>Amenities (comma-separated)</Label>
                  <Input
                    placeholder="Pool, Gym, Parking, Garden"
                    value={formData.amenities}
                    onChange={(e) => setFormData({ ...formData, amenities: e.target.value })}
                    data-testid="property-amenities-input"
                  />
                </div>
                <Button className="w-full" onClick={handleSubmit} data-testid="submit-property-btn">
                  Create Property
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {properties.length === 0 ? (
          <Card className="glass">
            <CardContent className="py-16 text-center">
              <Plus className="h-16 w-16 mx-auto mb-4 text-gray-400" />
              <p className="text-xl text-gray-500">No properties yet</p>
              <p className="text-gray-400 mt-2">Click "Add Property" to list your first property</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {properties.map((property) => (
              <Card key={property.id} className="glass hover:shadow-xl transition" data-testid={`property-card-${property.id}`}>
                <div className="relative h-48 bg-gradient-to-br from-blue-100 to-cyan-100">
                  {property.images && property.images.length > 0 ? (
                    <img src={property.images[0]} alt={property.title} className="w-full h-full object-cover" />
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <MapPin className="h-16 w-16 text-gray-400" />
                    </div>
                  )}
                  <Badge className="absolute top-3 right-3 bg-white text-gray-900">
                    {property.status}
                  </Badge>
                </div>
                <CardContent className="pt-4">
                  <h3 className="text-xl font-bold mb-2 line-clamp-1">{property.title}</h3>
                  <div className="flex items-center text-gray-600 mb-3">
                    <MapPin className="h-4 w-4 mr-1" />
                    <span className="text-sm line-clamp-1">{property.address}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-3 mb-4">
                    <div className="flex items-center gap-1">
                      <Bed className="h-4 w-4 text-gray-500" />
                      <span className="text-sm">{property.bedrooms}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Bath className="h-4 w-4 text-gray-500" />
                      <span className="text-sm">{property.bathrooms}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Square className="h-4 w-4 text-gray-500" />
                      <span className="text-sm">{property.area_sqft}</span>
                    </div>
                  </div>
                  <div className="flex items-center text-[hsl(var(--primary))] font-bold text-2xl">
                    <DollarSign className="h-5 w-5" />
                    {property.price.toLocaleString()}
                  </div>
                </CardContent>
                <CardFooter className="flex gap-2">
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() => navigate(`/properties/${property.id}`)}
                    data-testid={`view-property-${property.id}`}
                  >
                    <Edit className="mr-2 h-4 w-4" />
                    View
                  </Button>
                  <Button
                    variant="destructive"
                    className="flex-1"
                    onClick={() => handleDelete(property.id)}
                    data-testid={`delete-property-${property.id}`}
                  >
                    <Trash className="mr-2 h-4 w-4" />
                    Delete
                  </Button>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default MyPropertiesPage;
