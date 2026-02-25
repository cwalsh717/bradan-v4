// Dashboard
export interface DashboardTicker {
  id: number;
  category: string;
  display_name: string;
  symbol: string;
  data_source: string;
  display_format: string;
  display_order: number;
  is_active: boolean;
}

// Live price from WebSocket
export interface PriceUpdate {
  symbol: string;
  price: number;
  timestamp: string;
  change?: number;
  change_percent?: number;
}

// Stock profile
export interface StockProfile {
  symbol: string;
  name: string;
  exchange: string;
  sector: string;
  industry: string;
  currency: string;
}

// Search result
export interface SearchResult {
  symbol: string;
  name: string;
  exchange: string;
  cached: boolean;
}
