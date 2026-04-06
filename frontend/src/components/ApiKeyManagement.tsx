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
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-green-400 mb-1">API Key Created!</h3>
              <p className="text-sm text-gray-300">{newKey.warning}</p>
            </div>
            <button
              onClick={() => setNewKey(null)}
              className="text-slate-400 hover:text-white"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
          <div className="mb-4 rounded-xl bg-slate-950 p-4">
            <div className="flex items-center justify-between gap-4">
              <code className="text-sm text-green-400 break-all flex-1">{newKey.key}</code>
              <button
                onClick={() => copyToClipboard(newKey.key)}
                className="shrink-0 rounded-lg border border-slate-700 bg-slate-900 px-3 py-1 text-sm text-white transition-colors hover:border-slate-500"
              >
                Copy
              </button>
            </div>
          </div>
          <p className="text-xs text-slate-300">
            Store this key securely. You won't be able to see it again. Use it in the Authorization header: <code className="text-gray-300">Bearer {newKey.key_prefix}...</code>
          </p>
        </div>
      )}

      {/* Create Button */}
      {!showCreateForm && (
        <button
          onClick={() => setShowCreateForm(true)}
          className="rounded-xl bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 transition-colors hover:bg-cyan-400"
        >
          + Create New API Key
        </button>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <div className="rounded-2xl border border-slate-700 bg-slate-950/80 p-6">
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
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                placeholder="e.g., Production Bot, Dev Testing"
                required
              />
              <p className="mt-1 text-xs text-slate-500">A descriptive name to identify this key</p>
            </div>
            {!showExpirationField ? (
              <button
                type="button"
                onClick={() => setShowExpirationField(true)}
                className="text-sm text-cyan-300 transition-colors hover:text-cyan-200"
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
                    className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setShowExpirationField(false);
                      setExpiresAt('');
                    }}
                    className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white transition-colors hover:border-slate-500"
                  >
                    Remove
                  </button>
                </div>
                <p className="mt-1 text-xs text-slate-500">Key will expire at end of this day</p>
              </div>
            )}
            {createError && (
              <p className="text-sm text-red-300">{createError}</p>
            )}
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={creating}
                className="rounded-xl bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 transition-colors hover:bg-cyan-400 disabled:opacity-50"
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
                className="rounded-xl border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:border-slate-500"
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
          <p className="text-sm text-slate-400">Loading API keys...</p>
        ) : error ? (
          <p className="text-sm text-red-300">{error}</p>
        ) : keys.length === 0 ? (
          <p className="text-sm text-slate-400">
            No API keys yet. Create one to access FlowDeck programmatically.
          </p>
        ) : (
          <div className="space-y-4">
            {keys.map((key) => (
              <div
                key={key.id}
                className="rounded-2xl border border-slate-700 bg-slate-950/80 p-4"
              >
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <h4 className="text-white font-medium">{key.name}</h4>
                      <span
                        className={`px-2 py-0.5 text-xs rounded ${
                          key.is_active
                            ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                            : 'border border-slate-600 bg-slate-800 text-slate-300'
                        }`}
                      >
                        {key.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <p className="font-mono text-sm text-slate-400">{key.key_prefix}...</p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => handleToggleActive(key)}
                      disabled={actioningKeyId === key.id}
                      className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-white transition-colors hover:border-slate-500 disabled:opacity-50"
                    >
                      {key.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      onClick={() => handleDelete(key.id)}
                      disabled={actioningKeyId === key.id}
                      className="rounded-lg bg-red-600 px-3 py-1 text-xs text-white transition-colors hover:bg-red-500 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-1 gap-2 text-xs text-slate-400 sm:grid-cols-3">
                  <div>
                    <span className="text-slate-500">Created:</span> {formatDate(key.created_at)}
                  </div>
                  <div>
                    <span className="text-slate-500">Last used:</span> {formatDate(key.last_used_at)}
                  </div>
                  <div>
                    <span className="text-slate-500">Expires:</span>{' '}
                    {key.expires_at ? formatDate(key.expires_at) : 'Never'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Documentation Link */}
      <div className="rounded-2xl border border-blue-500/20 bg-blue-500/10 p-4">
        <h4 className="mb-2 text-sm font-semibold text-blue-200">How to use API keys</h4>
        <p className="mb-3 text-sm text-slate-300">
          Use your API key in the Authorization header for all API requests:
        </p>
        <code className="mb-3 block rounded-xl bg-slate-950 p-3 text-xs text-slate-300">
          Authorization: Bearer fd_live_your_key_here
        </code>
        <p className="text-xs text-slate-400">
          API keys work with all authenticated endpoints including chat, reports, and data APIs.
          See the documentation for examples in Python, JavaScript, and cURL.
        </p>
      </div>
    </div>
  );
}
