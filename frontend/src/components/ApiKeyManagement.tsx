import { useState, useEffect } from 'react';
import { apiKeyApi, type ApiKey, type CreateApiKeyResponse } from '../services/authApi';

export default function ApiKeyManagement() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Create key form
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [keyName, setKeyName] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [showExpirationField, setShowExpirationField] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  
  // Newly created key (shown once)
  const [newKey, setNewKey] = useState<CreateApiKeyResponse | null>(null);
  
  // Action states
  const [actioningKeyId, setActioningKeyId] = useState<number | null>(null);

  const loadKeys = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiKeyApi.list();
      setKeys(data);
    } catch (err) {
      setError('Failed to load API keys');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadKeys();
  }, []);

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyName.trim()) {
      setCreateError('Please enter a name for the API key');
      return;
    }
    
    setCreating(true);
    setCreateError(null);
    try {
      const body = {
        name: keyName.trim(),
        expires_at: expiresAt.trim() || null,
      };
      const created = await apiKeyApi.create(body);
      setNewKey(created);
      setKeyName('');
      setExpiresAt('');
      setShowCreateForm(false);
      await loadKeys();
    } catch (err: any) {
      const msg = err?.response?.data?.detail;
      setCreateError(typeof msg === 'string' ? msg : 'Failed to create API key');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (keyId: number) => {
    if (!confirm('Are you sure you want to delete this API key? This action cannot be undone.')) {
      return;
    }
    setActioningKeyId(keyId);
    try {
      await apiKeyApi.delete(keyId);
      await loadKeys();
    } catch (err) {
      alert('Failed to delete API key');
    } finally {
      setActioningKeyId(null);
    }
  };

  const handleToggleActive = async (key: ApiKey) => {
    setActioningKeyId(key.id);
    try {
      if (key.is_active) {
        await apiKeyApi.deactivate(key.id);
      } else {
        await apiKeyApi.activate(key.id);
      }
      await loadKeys();
    } catch (err) {
      alert(`Failed to ${key.is_active ? 'deactivate' : 'activate'} API key`);
    } finally {
      setActioningKeyId(null);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleDateString();
  };

  return (
    <div className="space-y-6">
      {/* New Key Display (shown once after creation) */}
      {newKey && (
        <div className="bg-green-900/20 border border-green-700 rounded-lg p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-green-400 mb-1">API Key Created!</h3>
              <p className="text-sm text-gray-300">{newKey.warning}</p>
            </div>
            <button
              onClick={() => setNewKey(null)}
              className="text-gray-400 hover:text-white"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          <div className="bg-gray-900 rounded p-4 mb-4">
            <div className="flex items-center justify-between gap-4">
              <code className="text-sm text-green-400 break-all flex-1">{newKey.key}</code>
              <button
                onClick={() => copyToClipboard(newKey.key)}
                className="px-3 py-1 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded transition-colors shrink-0"
              >
                Copy
              </button>
            </div>
          </div>
          <p className="text-xs text-gray-400">
            Store this key securely. You won't be able to see it again. Use it in the Authorization header: <code className="text-gray-300">Bearer {newKey.key_prefix}...</code>
          </p>
        </div>
      )}

      {/* Create Button */}
      {!showCreateForm && (
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          + Create New API Key
        </button>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <div className="bg-gray-700/50 border border-gray-600 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Create New API Key</h3>
          <form onSubmit={handleCreateKey} className="space-y-4">
            <div>
              <label htmlFor="key-name" className="block text-sm font-medium text-gray-300 mb-1">
                Name <span className="text-red-400">*</span>
              </label>
              <input
                id="key-name"
                type="text"
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., Production Bot, Dev Testing"
                required
              />
              <p className="text-xs text-gray-400 mt-1">A descriptive name to identify this key</p>
            </div>
            {!showExpirationField ? (
              <button
                type="button"
                onClick={() => setShowExpirationField(true)}
                className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
              >
                + Set expiration date (optional)
              </button>
            ) : (
              <div>
                <label htmlFor="key-expires" className="block text-sm font-medium text-gray-300 mb-1">
                  Expires On (Optional)
                </label>
                <div className="flex gap-2">
                  <input
                    id="key-expires"
                    type="date"
                    value={expiresAt}
                    onChange={(e) => setExpiresAt(e.target.value)}
                    className="flex-1 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setShowExpirationField(false);
                      setExpiresAt('');
                    }}
                    className="px-3 py-2 bg-gray-600 hover:bg-gray-500 text-white rounded-lg text-sm transition-colors"
                  >
                    Remove
                  </button>
                </div>
                <p className="text-xs text-gray-400 mt-1">Key will expire at end of this day</p>
              </div>
            )}
            {createError && (
              <p className="text-sm text-red-400">{createError}</p>
            )}
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={creating}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {creating ? 'Creating...' : 'Create API Key'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowCreateForm(false);
                  setKeyName('');
                  setExpiresAt('');
                  setShowExpirationField(false);
                  setCreateError(null);
                }}
                className="px-4 py-2 bg-gray-600 hover:bg-gray-500 text-white rounded-lg text-sm font-medium transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Keys List */}
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">Your API Keys</h3>
        {loading ? (
          <p className="text-gray-400 text-sm">Loading API keys...</p>
        ) : error ? (
          <p className="text-red-400 text-sm">{error}</p>
        ) : keys.length === 0 ? (
          <p className="text-gray-400 text-sm">
            No API keys yet. Create one to access FlowDeck programmatically.
          </p>
        ) : (
          <div className="space-y-4">
            {keys.map((key) => (
              <div
                key={key.id}
                className="bg-gray-700/50 border border-gray-600 rounded-lg p-4"
              >
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <h4 className="text-white font-medium">{key.name}</h4>
                      <span
                        className={`px-2 py-0.5 text-xs rounded ${
                          key.is_active
                            ? 'bg-green-900/30 text-green-400 border border-green-700'
                            : 'bg-gray-600 text-gray-300 border border-gray-500'
                        }`}
                      >
                        {key.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-400 font-mono">{key.key_prefix}...</p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => handleToggleActive(key)}
                      disabled={actioningKeyId === key.id}
                      className="px-3 py-1 bg-gray-600 hover:bg-gray-500 disabled:opacity-50 text-white text-xs rounded transition-colors"
                    >
                      {key.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      onClick={() => handleDelete(key.id)}
                      disabled={actioningKeyId === key.id}
                      className="px-3 py-1 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-xs rounded transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-gray-400">
                  <div>
                    <span className="text-gray-500">Created:</span> {formatDate(key.created_at)}
                  </div>
                  <div>
                    <span className="text-gray-500">Last used:</span> {formatDate(key.last_used_at)}
                  </div>
                  <div>
                    <span className="text-gray-500">Expires:</span>{' '}
                    {key.expires_at ? formatDate(key.expires_at) : 'Never'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Documentation Link */}
      <div className="bg-blue-900/20 border border-blue-700 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-blue-400 mb-2">📚 How to use API keys</h4>
        <p className="text-sm text-gray-300 mb-3">
          Use your API key in the Authorization header for all API requests:
        </p>
        <code className="block bg-gray-900 rounded p-3 text-xs text-gray-300 mb-3">
          Authorization: Bearer fd_live_your_key_here
        </code>
        <p className="text-xs text-gray-400">
          API keys work with all authenticated endpoints including chat, reports, and data APIs.
          See the documentation for examples in Python, JavaScript, and cURL.
        </p>
      </div>
    </div>
  );
}

// Made with Bob
