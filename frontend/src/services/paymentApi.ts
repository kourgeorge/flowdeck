import axios from 'axios';
import { API_BASE_URL } from './api';

export interface TokenPackage {
  id: string;
  name: string;
  tokens: number;
  price: number;
  currency: string;
  badge?: string;
}

// Get stored token (matches authApi.ts)
function getStoredToken(): string | null {
  return localStorage.getItem('flowdeck_token');
}

export const paymentApi = {
  async getPackages(): Promise<{ packages: TokenPackage[] }> {
    const response = await axios.get(`${API_BASE_URL}/api/payments/packages`);
    return response.data;
  },

  async createPayment(packageId: string): Promise<{ payment_id: string; approval_url: string }> {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const response = await axios.post(
      `${API_BASE_URL}/api/payments/create`,
      { package_id: packageId },
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },

  async executePayment(paymentId: string, payerId: string): Promise<any> {
    const token = getStoredToken();
    if (!token) throw new Error('Not authenticated');
    const response = await axios.post(
      `${API_BASE_URL}/api/payments/execute?payment_id=${paymentId}&PayerID=${payerId}`,
      {},
      { headers: { Authorization: `Bearer ${token}` } }
    );
    return response.data;
  },
};

// Made with Bob
