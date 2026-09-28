import React, { useState, useEffect, useCallback } from 'react';
import {
  getProducts,
  getSuggestions,
  processOrder,
  updatePricingSuggestion,
  updateReorderSuggestion,
  getStrategy,
  updateStrategy,
} from './api';

export default function App() {
  const [products, setProducts] = useState([]);
  const [pricingSuggestions, setPricingSuggestions] = useState([]);
  const [reorderSuggestions, setReorderSuggestions] = useState([]);
  const [strategy, setStrategy] = useState('AI');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState({});

  // Fetch product list
  const fetchProducts = useCallback(async () => {
    try {
      const response = await getProducts();
      setProducts(response.data);
    } catch (err) {
      console.error('Error fetching products:', err);
      setError('Failed to fetch products from backend.');
    }
  }, []);

  // Fetch pending suggestions
  const fetchSuggestions = useCallback(async () => {
    try {
      const response = await getSuggestions();
      setPricingSuggestions(response.data.pricing || []);
      setReorderSuggestions(response.data.reorder || []);
    } catch (err) {
      console.error('Error fetching suggestions:', err);
    }
  }, []);

  // Fetch active strategy
  const fetchStrategySetting = useCallback(async () => {
    try {
      const response = await getStrategy();
      setStrategy(response.data.strategy);
    } catch (err) {
      console.error('Error fetching strategy:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      setError(null);
      await Promise.all([fetchProducts(), fetchSuggestions(), fetchStrategySetting()]);
      setLoading(false);
    };
    init();
  }, [fetchProducts, fetchSuggestions, fetchStrategySetting]);

  // Poll pending suggestions and products every 3 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchSuggestions();
      fetchProducts();
    }, 3000);
    return () => clearInterval(interval);
  }, [fetchSuggestions, fetchProducts]);

  // Handle Strategy Switch
  const handleStrategyChange = async (e) => {
    const newStrategy = e.target.value;
    try {
      setError(null);
      const res = await updateStrategy(newStrategy);
      setStrategy(res.data.strategy);
    } catch (err) {
      console.error('Failed to update strategy:', err);
      setError('Failed to update advisor strategy.');
    }
  };

  // Simulate Sale
  const handleSimulateSale = async (productId) => {
    setActionLoading((prev) => ({ ...prev, [productId]: true }));
    setError(null);
    try {
      await processOrder(productId, 1);
      // Immediately refresh products and suggestions in parallel
      await Promise.all([fetchProducts(), fetchSuggestions()]);
      // Quick follow-up check after 1.5s to catch AI generation immediately
      setTimeout(fetchSuggestions, 1500);
    } catch (err) {
      console.error('Simulate sale failed:', err);
      setError(err.response?.data?.detail || 'Sale simulation failed.');
    } finally {
      setActionLoading((prev) => ({ ...prev, [productId]: false }));
    }
  };

  // Handle Pricing Suggestion Action (ACCEPT / REJECT)
  const handlePricingAction = async (suggestionId, action) => {
    setActionLoading((prev) => ({ ...prev, [`p_${suggestionId}`]: true }));
    setError(null);
    try {
      await updatePricingSuggestion(suggestionId, action);
      await Promise.all([fetchProducts(), fetchSuggestions()]);
    } catch (err) {
      console.error(`Failed to ${action} pricing suggestion:`, err);
      setError(err.response?.data?.detail || `Failed to ${action} pricing suggestion.`);
    } finally {
      setActionLoading((prev) => ({ ...prev, [`p_${suggestionId}`]: false }));
    }
  };

  // Handle Reorder Suggestion Action (ACCEPT / REJECT)
  const handleReorderAction = async (suggestionId, action) => {
    setActionLoading((prev) => ({ ...prev, [`r_${suggestionId}`]: true }));
    setError(null);
    try {
      await updateReorderSuggestion(suggestionId, action);
      await Promise.all([fetchProducts(), fetchSuggestions()]);
    } catch (err) {
      console.error(`Failed to ${action} reorder suggestion:`, err);
      setError(err.response?.data?.detail || `Failed to ${action} reorder suggestion.`);
    } finally {
      setActionLoading((prev) => ({ ...prev, [`r_${suggestionId}`]: false }));
    }
  };

  // Helper map product id to product name
  const getProductName = (productId) => {
    const prod = products.find((p) => p.id === productId);
    return prod ? `${prod.name} (${prod.sku})` : productId;
  };

  const totalSuggestions = pricingSuggestions.length + reorderSuggestions.length;

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div>
          <h1>StockPulse</h1>
          <p style={{ fontSize: '0.85rem', opacity: 0.9 }}>
            AI Inventory &amp; Dynamic Pricing Engine — Reactive Commerce Advisor
          </p>
        </div>
        <div className="strategy-selector">
          <label htmlFor="strategy-select" style={{ fontWeight: 600 }}>Advisor Strategy:</label>
          <select
            id="strategy-select"
            value={strategy}
            onChange={handleStrategyChange}
          >
            <option value="AI">AI (LLM / Fallback)</option>
            <option value="RULE_BASED">Rule-Based Advisor</option>
          </select>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        {error && (
          <div className="error-message">
            <strong>Notice:</strong> {error}
            <button
              onClick={() => setError(null)}
              style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}
            >
              ✕
            </button>
          </div>
        )}

        {/* Section 1: Pending Recommendations */}
        <section className="suggestions-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.5rem', borderBottom: '1px solid #eee' }}>
            <h2>Pending Human Approvals ({totalSuggestions})</h2>
            <span style={{ fontSize: '0.85rem', color: '#666' }}>Auto-polling every 3s</span>
          </div>

          {loading ? (
            <div className="empty-state">
              <p>Loading recommendations...</p>
            </div>
          ) : totalSuggestions === 0 ? (
            <div className="empty-state">
              <p>No pending recommendations.</p>
              <p style={{ fontSize: '0.85rem', color: '#888', marginTop: '0.5rem' }}>
                Simulate a sale on an item below to trigger reactive inventory or demand signals!
              </p>
            </div>
          ) : (
            <div>
              {/* Pricing Suggestions */}
              {pricingSuggestions.map((sug) => {
                const isBusy = actionLoading[`p_${sug.id}`];
                const triggerClass = `trigger-${sug.trigger_reason.toLowerCase()}`;
                const dirClass = `direction-${sug.direction.toLowerCase()}`;
                return (
                  <div key={`p_${sug.id}`} className="suggestion-card">
                    <div className="suggestion-header">
                      <div>
                        <h3>
                          Pricing Recommendation: {getProductName(sug.product_id)}
                        </h3>
                        <span style={{ fontSize: '0.8rem', color: '#777' }}>
                          Product ID: {sug.product_id}
                        </span>
                      </div>
                      <span className={`trigger-badge ${triggerClass}`}>
                        {sug.trigger_reason}
                      </span>
                    </div>

                    <div className="suggestion-details">
                      <p>
                        <strong>Pricing Adjustment:</strong> ${sug.current_price.toFixed(2)} →{' '}
                        <span style={{ fontWeight: 'bold', fontSize: '1.05rem', color: '#2e7d32' }}>
                          ${sug.recommended_price.toFixed(2)}
                        </span>
                        <span className={`direction-badge ${dirClass}`}>
                          {sug.direction}
                        </span>
                      </p>
                      <p>
                        <strong>Confidence:</strong> {(sug.confidence * 100).toFixed(0)}%
                      </p>
                      <p>
                        <strong>Reasoning:</strong> {sug.reasoning}
                      </p>
                    </div>

                    <div className="suggestion-actions">
                      <button
                        className="btn btn-primary"
                        onClick={() => handlePricingAction(sug.id, 'ACCEPT')}
                        disabled={isBusy}
                      >
                        {isBusy ? 'Processing...' : 'Accept Price'}
                      </button>
                      <button
                        className="btn btn-secondary"
                        onClick={() => handlePricingAction(sug.id, 'REJECT')}
                        disabled={isBusy}
                      >
                        Reject Price
                      </button>
                    </div>
                  </div>
                );
              })}

              {/* Reorder Suggestions */}
              {reorderSuggestions.map((sug) => {
                const isBusy = actionLoading[`r_${sug.id}`];
                const triggerClass = `trigger-${sug.trigger_reason.toLowerCase()}`;
                return (
                  <div key={`r_${sug.id}`} className="suggestion-card">
                    <div className="suggestion-header">
                      <div>
                        <h3>
                          Replenishment Order: {getProductName(sug.product_id)}
                        </h3>
                        <span style={{ fontSize: '0.8rem', color: '#777' }}>
                          Product ID: {sug.product_id}
                        </span>
                      </div>
                      <span className={`trigger-badge ${triggerClass}`}>
                        {sug.trigger_reason}
                      </span>
                    </div>

                    <div className="suggestion-details">
                      <p>
                        <strong>Current Stock:</strong> {sug.current_stock} units
                      </p>
                      <p>
                        <strong>Recommended Reorder Quantity:</strong>{' '}
                        <span style={{ fontWeight: 'bold', fontSize: '1.05rem', color: '#1565c0' }}>
                          +{sug.recommended_quantity} units
                        </span>{' '}
                        (Lead time: {sug.suggested_lead_time_days || 7} days)
                      </p>
                      <p>
                        <strong>Confidence:</strong> {(sug.confidence * 100).toFixed(0)}%
                      </p>
                      <p>
                        <strong>Reasoning:</strong> {sug.reasoning}
                      </p>
                    </div>

                    <div className="suggestion-actions">
                      <button
                        className="btn btn-primary"
                        onClick={() => handleReorderAction(sug.id, 'ACCEPT')}
                        disabled={isBusy}
                      >
                        {isBusy ? 'Processing...' : 'Accept Reorder'}
                      </button>
                      <button
                        className="btn btn-secondary"
                        onClick={() => handleReorderAction(sug.id, 'REJECT')}
                        disabled={isBusy}
                      >
                        Reject Reorder
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Section 2: Products Catalog */}
        <section className="products-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.5rem', borderBottom: '1px solid #eee' }}>
            <h2>Inventory &amp; Merchandising Catalog</h2>
            <span style={{ fontSize: '0.85rem', color: '#666' }}>{products.length} Products</span>
          </div>

          <table className="products-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>SKU</th>
                <th>Category</th>
                <th>Price</th>
                <th>Stock</th>
                <th>Threshold</th>
                <th>Velocity</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {products.map((prod) => {
                const isOut = prod.stock_level === 0 || prod.status === 'OUT_OF_STOCK';
                const isBusy = actionLoading[prod.id];
                const statusClass = `status-${prod.status.toLowerCase()}`;
                const isPrimaryDemo = prod.id === 'PRD-003';
                const isSpikeDemo = prod.id === 'PRD-008';

                return (
                  <tr key={prod.id} style={isPrimaryDemo ? { backgroundColor: '#f0f7ff' } : {}}>
                    <td>
                      <strong>{prod.name}</strong>
                      {isPrimaryDemo && (
                        <span style={{ marginLeft: '6px', fontSize: '0.7rem', background: '#e3f2fd', color: '#0d47a1', padding: '2px 6px', borderRadius: '4px' }}>
                          Primary Demo
                        </span>
                      )}
                      {isSpikeDemo && (
                        <span style={{ marginLeft: '6px', fontSize: '0.7rem', background: '#e8f5e9', color: '#1b5e20', padding: '2px 6px', borderRadius: '4px' }}>
                          Spike Demo
                        </span>
                      )}
                    </td>
                    <td><code>{prod.sku}</code></td>
                    <td>{prod.category}</td>
                    <td><strong>${prod.current_price.toFixed(2)}</strong></td>
                    <td>
                      <span style={{ color: prod.stock_level < prod.reorder_threshold ? '#d32f2f' : '#2e7d32', fontWeight: 600 }}>
                        {prod.stock_level}
                      </span>
                    </td>
                    <td>{prod.reorder_threshold}</td>
                    <td>{prod.demand_velocity.toFixed(1)}</td>
                    <td>
                      <span className={`status-badge ${statusClass}`}>
                        {prod.status}
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn btn-primary"
                        onClick={() => handleSimulateSale(prod.id)}
                        disabled={isOut || isBusy}
                        title={isOut ? 'Out of stock' : 'Simulate 1 sale'}
                      >
                        {isBusy ? 'Processing...' : 'Simulate Sale'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}
