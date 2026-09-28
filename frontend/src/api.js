import axios from 'axios';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
});

// Products
export const getProducts = (params = {}) => api.get('/products', { params });
export const getProduct = (id) => api.get(`/products/${id}`);
export const updateProductStock = (id, stock) => api.patch(`/products/${id}/stock`, { stock });
export const processOrder = (id, quantity) => api.post(`/products/${id}/orders`, { quantity });

// Suggestions
export const getSuggestions = () => api.get('/suggestions/pending');
export const updatePricingSuggestion = (id, action) => api.patch(`/pricing-suggestions/${id}`, { action });
export const updateReorderSuggestion = (id, action) => api.patch(`/reorder-suggestions/${id}`, { action });

// Strategy
export const getStrategy = () => api.get('/settings/strategy');
export const updateStrategy = (strategy) => api.patch('/settings/strategy', { strategy });

// Manual suggestions
export const suggestPricing = (id) => api.post(`/products/${id}/suggest-pricing`);
export const suggestReorder = (id) => api.post(`/products/${id}/suggest-reorder`);

// Health check
export const healthCheck = () => api.get('/health');

export default api;