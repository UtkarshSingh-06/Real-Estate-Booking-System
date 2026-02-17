import React, { useState, useEffect, useContext, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AuthContext } from '../App';
import Navbar from '../components/Navbar';
import { Card, CardContent, CardFooter } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { MapPin, Bed, Bath, Square, DollarSign, Search, Sparkles } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const DEBOUNCE_MS = 400;

const PropertiesPage = () => {
  const { sessionToken } = useContext(AuthContext);
  const navigate = useNavigate();
  const [properties, setProperties] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [recommendationType, setRecommendationType] = useState('');
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    query: '',
    min_price: '',
    max_price: '',
    property_type: '',
    bedrooms: '',
    bathrooms: ''
  });

  const fetchProperties = useCallback(async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/properties`, {
        headers: { Authorization: `Bearer ${sessionToken}` }
      });
      setProperties(response.data.properties);
    } catch (error) {
      console.error('Error fetching properties:', error);
      toast.error('Failed to load properties');
    } finally {
      setLoading(false);
    }
  }, [sessionToken]);

  const fetchRecommendations = useCallback(async () => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/ai/recommendations?limit=6`, {
        headers: { Authorization: `Bearer ${sessionToken}` }
      });
      setRecommendations(response.data.recommendations || []);
      setRecommendationType(response.data.type || '');
    } catch (error) {
      console.error('Error fetching recommendations:', error);
    }
  }, [sessionToken]);

  useEffect(() => {
    fetchProperties();
    fetchRecommendations();
  }, [fetchProperties, fetchRecommendations]);

  const runRealtimeSearch = useCallback(async () => {
    const params = new URLSearchParams();
    if (filters.query?.trim()) params.set('q', filters.query.trim());
    if (filters.min_price) params.set('min_price', filters.min_price);
    if (filters.max_price) params.set('max_price', filters.max_price);
    if (filters.property_type) params.set('property_type', filters.property_type);
    if (filters.bedrooms) params.set('bedrooms', filters.bedrooms);
    if (filters.bathrooms) params.set('bathrooms', filters.bathrooms);
    try {
      const response = await axios.get(
        `${BACKEND_URL}/api/properties/search/realtime?${params.toString()}`,
        { headers: { Authorization: `Bearer ${sessionToken}` } }
      );
      setProperties(response.data.properties);
    } catch (error) {
      console.error('Realtime search error:', error);
    } finally {
      setLoading(false);
    }
  }, [sessionToken, filters]);

  const hasFilters = filters.query?.trim() || filters.min_price || filters.max_price || filters.property_type || filters.bedrooms || filters.bathrooms;
  useEffect(() => {
    if (!sessionToken || !hasFilters) return;
    setLoading(true);
    const t = setTimeout(runRealtimeSearch, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [sessionToken, hasFilters, runRealtimeSearch]);

  const handleSearch = async () => {
    setLoading(true);
    try {
      const searchParams = { query: filters.query?.trim() || undefined };
      if (filters.min_price) searchParams.min_price = parseFloat(filters.min_price);
      if (filters.max_price) searchParams.max_price = parseFloat(filters.max_price);
      if (filters.property_type) searchParams.property_type = filters.property_type;
      if (filters.bedrooms) searchParams.bedrooms = parseInt(filters.bedrooms);
      if (filters.bathrooms) searchParams.bathrooms = parseInt(filters.bathrooms);

      const response = await axios.post(
        `${BACKEND_URL}/api/properties/search`,
        searchParams,
        { headers: { Authorization: `Bearer ${sessionToken}` } }
      );
      setProperties(response.data.properties);
    } catch (error) {
      console.error('Error searching properties:', error);
      toast.error('Search failed');
    } finally {
      setLoading(false);
    }
  };

  const handleClearFilters = () => {
    setFilters({
      query: '',
      min_price: '',
      max_price: '',
      property_type: '',
      bedrooms: '',
      bathrooms: ''
    });
    fetchProperties();
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
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="properties-page">
        {/* Search and Filters */}
        <div className="glass rounded-xl p-6 mb-8">
          <h2 className="text-2xl font-bold mb-4">Real-Time Property Search</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
            <Input
              placeholder="Search by keyword, address..."
              value={filters.query}
              onChange={(e) => setFilters({ ...filters, query: e.target.value })}
              className="lg:col-span-2"
              data-testid="search-query-input"
            />
            <Input
              type="number"
              placeholder="Min Price"
              value={filters.min_price}
              onChange={(e) => setFilters({ ...filters, min_price: e.target.value })}
              data-testid="min-price-input"
            />
            <Input
              type="number"
              placeholder="Max Price"
              value={filters.max_price}
              onChange={(e) => setFilters({ ...filters, max_price: e.target.value })}
              data-testid="max-price-input"
            />
            <Select value={filters.property_type} onValueChange={(value) => setFilters({ ...filters, property_type: value })}>
              <SelectTrigger data-testid="property-type-select">
                <SelectValue placeholder="Property Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="apartment">Apartment</SelectItem>
                <SelectItem value="house">House</SelectItem>
                <SelectItem value="villa">Villa</SelectItem>
                <SelectItem value="condo">Condo</SelectItem>
              </SelectContent>
            </Select>
            <Input
              type="number"
              placeholder="Bedrooms"
              value={filters.bedrooms}
              onChange={(e) => setFilters({ ...filters, bedrooms: e.target.value })}
              data-testid="bedrooms-input"
            />
            <Input
              type="number"
              placeholder="Bathrooms"
              value={filters.bathrooms}
              onChange={(e) => setFilters({ ...filters, bathrooms: e.target.value })}
              data-testid="bathrooms-input"
            />
          </div>
          <div className="flex gap-3 mt-4">
            <Button onClick={handleSearch} className="flex-1" data-testid="search-btn">
              <Search className="mr-2 h-4 w-4" />
              Search
            </Button>
            <Button onClick={handleClearFilters} variant="outline" data-testid="clear-filters-btn">
              Clear Filters
            </Button>
          </div>
        </div>

        {/* Recommended for you */}
        {recommendations.length > 0 && (
          <div className="mb-10">
            <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-[hsl(var(--primary))]" />
              {recommendationType === 'personalized' && 'Recommended for you'}
              {recommendationType === 'similar' && 'Similar properties'}
              {recommendationType === 'trending' && 'Trending listings'}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {recommendations.map((property) => (
                <Card key={property.id} className="property-card glass overflow-hidden hover:shadow-2xl">
                  <div className="relative h-40 bg-gradient-to-br from-blue-100 to-cyan-100">
                    {property.images?.length > 0 ? (
                      <img src={property.images[0]} alt={property.title} className="w-full h-full object-cover" />
                    ) : (
                      <div className="flex items-center justify-center h-full">
                        <MapPin className="h-12 w-12 text-gray-400" />
                      </div>
                    )}
                    <Badge className="absolute top-2 right-2 bg-white text-gray-900">{property.property_type}</Badge>
                  </div>
                  <CardContent className="pt-3">
                    <h3 className="font-bold line-clamp-1">{property.title}</h3>
                    <div className="flex items-center text-gray-600 text-sm mt-1">
                      <MapPin className="h-3 w-3 mr-1" />
                      <span className="line-clamp-1">{property.address}</span>
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
                      <span>{property.bedrooms} bed</span>
                      <span>{property.bathrooms} bath</span>
                      <span>{property.area_sqft} sqft</span>
                    </div>
                    <div className="flex items-center text-[hsl(var(--primary))] font-bold mt-2">
                      <DollarSign className="h-4 w-4" />
                      {property.price?.toLocaleString()}
                    </div>
                  </CardContent>
                  <CardFooter>
                    <Button className="w-full bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90" onClick={() => navigate(`/properties/${property.id}`)}>
                      View Details
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Properties Grid */}
        <div className="mb-6">
          <h2 className="text-3xl font-bold mb-2">Available Properties</h2>
          <p className="text-gray-600">{properties.length} properties found • Results update as you type</p>
        </div>

        {properties.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-xl text-gray-500">No properties found. Try adjusting your filters.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {properties.map((property) => (
              <Card key={property.id} className="property-card glass overflow-hidden hover:shadow-2xl" data-testid={`property-card-${property.id}`}>
                <div className="relative h-48 bg-gradient-to-br from-blue-100 to-cyan-100">
                  {property.images && property.images.length > 0 ? (
                    <img
                      src={property.images[0]}
                      alt={property.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <MapPin className="h-16 w-16 text-gray-400" />
                    </div>
                  )}
                  <Badge className="absolute top-3 right-3 bg-white text-gray-900">
                    {property.property_type}
                  </Badge>
                </div>
                <CardContent className="pt-4">
                  <h3 className="text-xl font-bold mb-2 line-clamp-1">{property.title}</h3>
                  <div className="flex items-center text-gray-600 mb-3">
                    <MapPin className="h-4 w-4 mr-1" />
                    <span className="text-sm line-clamp-1">{property.address}</span>
                  </div>
                  <p className="text-gray-600 text-sm line-clamp-2 mb-4">{property.description}</p>
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
                      <span className="text-sm">{property.area_sqft} sqft</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center text-[hsl(var(--primary))] font-bold text-2xl">
                      <DollarSign className="h-5 w-5" />
                      {property.price.toLocaleString()}
                    </div>
                  </div>
                </CardContent>
                <CardFooter>
                  <Button
                    className="w-full bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                    onClick={() => navigate(`/properties/${property.id}`)}
                    data-testid={`view-property-${property.id}`}
                  >
                    View Details
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

export default PropertiesPage;
