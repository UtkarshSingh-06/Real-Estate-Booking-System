import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { estimatePrice } from '../services/api';
import Navbar from '../components/Navbar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { DollarSign, Calculator, Sparkles } from 'lucide-react';
import { toast } from 'sonner';

const PROPERTY_TYPES = [
  { value: 'apartment', label: 'Apartment' },
  { value: 'house', label: 'House' },
  { value: 'villa', label: 'Villa' },
  { value: 'condo', label: 'Condo' },
];

const PriceEstimatePage = () => {
  useAuth();
  const [inputs, setInputs] = useState({
    property_type: 'apartment',
    area_sqft: '',
    bedrooms: '2',
    bathrooms: '2',
    amenities: []
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const area = parseFloat(inputs.area_sqft);
    if (!area || area <= 0) {
      toast.error('Please enter a valid area (sqft)');
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const response = await estimatePrice({
        property_type: inputs.property_type,
        area_sqft: area,
        bedrooms: parseInt(inputs.bedrooms) || 2,
        bathrooms: parseInt(inputs.bathrooms) || 2,
        amenities: inputs.amenities
      });
      setResult(response.data);
      toast.success('Price estimate ready');
    } catch (error) {
      console.error('Estimate error:', error);
      toast.error(error.response?.data?.detail || 'Failed to get estimate');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center gap-2 mb-6">
          <Sparkles className="h-8 w-8 text-[hsl(var(--primary))]" />
          <h1 className="text-3xl font-bold">Smart Price Estimate</h1>
        </div>
        <p className="text-gray-600 mb-8">
          Get a similarity-based estimate using comparable listings, property type, size, and features.
        </p>

        <Card className="glass border-0 shadow-xl mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calculator className="h-5 w-5" />
              Property Details
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Property Type</Label>
                  <Select
                    value={inputs.property_type}
                    onValueChange={(v) => setInputs({ ...inputs, property_type: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PROPERTY_TYPES.map((t) => (
                        <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Area (sq ft)</Label>
                  <Input
                    type="number"
                    min="100"
                    step="50"
                    placeholder="e.g. 1500"
                    value={inputs.area_sqft}
                    onChange={(e) => setInputs({ ...inputs, area_sqft: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label>Bedrooms</Label>
                  <Select
                    value={String(inputs.bedrooms)}
                    onValueChange={(v) => setInputs({ ...inputs, bedrooms: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 4, 5, 6].map((n) => (
                        <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Bathrooms</Label>
                  <Select
                    value={String(inputs.bathrooms)}
                    onValueChange={(v) => setInputs({ ...inputs, bathrooms: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button
                type="submit"
                className="w-full bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary))]/90"
                disabled={loading}
              >
                {loading ? 'Estimating...' : 'Get Price Estimate'}
              </Button>
            </form>
          </CardContent>
        </Card>

        {result && (
          <Card className="glass border-2 border-[hsl(var(--primary))]/30 bg-gradient-to-br from-primary/5 to-transparent">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                  <p className="text-sm text-muted-foreground mb-1">Estimated market value</p>
                  <p className="text-4xl font-bold flex items-center gap-2 text-[hsl(var(--primary))]">
                    <DollarSign className="h-10 w-10" />
                    {result.estimated_price?.toLocaleString()} <span className="text-lg font-normal text-foreground">{result.currency}</span>
                  </p>
                </div>
                {result.based_on_listings != null && (
                  <p className="text-sm text-muted-foreground">
                    Based on {result.based_on_listings} similar listing{result.based_on_listings !== 1 ? 's' : ''}
                  </p>
                )}
              </div>
              {(result.method || result.confidence != null) && (
                <div className="mt-4 text-sm text-muted-foreground space-y-1">
                  {result.method && <p>Method: {result.method}</p>}
                  {result.confidence != null && <p>Confidence: {result.confidence}</p>}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default PriceEstimatePage;
