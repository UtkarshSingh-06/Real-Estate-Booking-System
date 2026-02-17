import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AuthContext } from '../App';
import Navbar from '../components/Navbar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { BarChart2, TrendingUp, Home, Calendar, DollarSign } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const AnalyticsPage = () => {
  const { sessionToken } = useContext(AuthContext);
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState(null);
  const [marketTrends, setMarketTrends] = useState([]);
  const [buyerBehavior, setBuyerBehavior] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const [dashRes, trendsRes, behaviorRes] = await Promise.all([
          axios.get(`${BACKEND_URL}/api/analytics/dashboard`, { headers: { Authorization: `Bearer ${sessionToken}` } }),
          axios.get(`${BACKEND_URL}/api/analytics/market-trends`, { headers: { Authorization: `Bearer ${sessionToken}` } }),
          axios.get(`${BACKEND_URL}/api/analytics/buyer-behavior`, { headers: { Authorization: `Bearer ${sessionToken}` } })
        ]);
        setDashboard(dashRes.data);
        setMarketTrends(trendsRes.data.market_trends || []);
        setBuyerBehavior(behaviorRes.data);
      } catch (error) {
        console.error('Analytics fetch error:', error);
        toast.error('Failed to load analytics');
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [sessionToken]);

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

  const maxTrendPrice = marketTrends.length ? Math.max(...marketTrends.map((t) => t.avg_price)) : 0;

  return (
    <div>
      <Navbar />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center gap-2 mb-8">
          <BarChart2 className="h-8 w-8 text-[hsl(var(--primary))]" />
          <h1 className="text-3xl font-bold">Market Insights & Analytics</h1>
        </div>
        <p className="text-gray-600 mb-8">
          Predictive analytics for home buyer behavior and market trends.
        </p>

        {/* Dashboard summary */}
        {dashboard && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <Card className="glass">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Total Listings</CardTitle>
                <Home className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{dashboard.total_listings}</div>
              </CardContent>
            </Card>
            <Card className="glass">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Total Bookings</CardTitle>
                <Calendar className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{dashboard.total_bookings}</div>
              </CardContent>
            </Card>
            <Card className="glass">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">Avg. Listing Price</CardTitle>
                <DollarSign className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {dashboard.average_listing_price?.toLocaleString()} {dashboard.currency || 'USD'}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Market trends */}
        <Card className="glass mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Price & Listing Trends
            </CardTitle>
          </CardHeader>
          <CardContent>
            {marketTrends.length === 0 ? (
              <p className="text-muted-foreground py-8 text-center">No trend data yet. Listings over time will appear here.</p>
            ) : (
              <div className="space-y-4">
                <div className="flex gap-2 overflow-x-auto pb-2">
                  {marketTrends.map((t, i) => (
                    <div
                      key={i}
                      className="flex-shrink-0 flex flex-col items-center gap-1 p-3 rounded-lg bg-muted/50 min-w-[80px]"
                    >
                      <span className="text-xs text-muted-foreground">
                        {t._id?.year}-{String(t._id?.month || 0).padStart(2, '0')}
                      </span>
                      <span className="font-semibold text-[hsl(var(--primary))]">
                        ${(t.avg_price || 0).toLocaleString(0)}
                      </span>
                      <span className="text-xs text-muted-foreground">{t.count} listings</span>
                    </div>
                  ))}
                </div>
                <div className="h-8 flex items-end gap-1">
                  {marketTrends.map((t, i) => (
                    <div
                      key={i}
                      className="flex-1 min-w-[12px] rounded-t bg-[hsl(var(--primary))]/70 hover:bg-[hsl(var(--primary))] transition-colors"
                      style={{ height: maxTrendPrice ? `${Math.max(12, (t.avg_price / maxTrendPrice) * 100)}%` : '20%' }}
                      title={`${t._id?.year}-${t._id?.month}: $${(t.avg_price || 0).toLocaleString()}`}
                    />
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Buyer behavior */}
        {buyerBehavior && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <Card className="glass">
              <CardHeader>
                <CardTitle>Bookings by Property Type</CardTitle>
              </CardHeader>
              <CardContent>
                {(!buyerBehavior.bookings_by_property_type || buyerBehavior.bookings_by_property_type.length === 0) ? (
                  <p className="text-muted-foreground py-4 text-center">No booking data yet.</p>
                ) : (
                  <ul className="space-y-3">
                    {buyerBehavior.bookings_by_property_type.map((item, i) => (
                      <li key={i} className="flex justify-between items-center p-2 rounded-lg bg-muted/50">
                        <span className="capitalize font-medium">{item._id || 'Unknown'}</span>
                        <span className="text-[hsl(var(--primary))] font-bold">{item.bookings} bookings</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
            <Card className="glass">
              <CardHeader>
                <CardTitle>Most Popular Properties</CardTitle>
              </CardHeader>
              <CardContent>
                {(!buyerBehavior.most_popular_properties || buyerBehavior.most_popular_properties.length === 0) ? (
                  <p className="text-muted-foreground py-4 text-center">No popular listings yet.</p>
                ) : (
                  <ul className="space-y-2">
                    {buyerBehavior.most_popular_properties.slice(0, 5).map((p) => (
                      <li key={p.id}>
                        <button
                          type="button"
                          onClick={() => navigate(`/properties/${p.id}`)}
                          className="w-full text-left flex justify-between items-center p-2 rounded-lg hover:bg-muted/50 transition-colors"
                        >
                          <span className="font-medium line-clamp-1">{p.title}</span>
                          <span className="text-sm text-[hsl(var(--primary))]">{p.booking_count} bookings</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};

export default AnalyticsPage;
