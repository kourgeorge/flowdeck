import { useState, useEffect } from 'react';
import { paymentApi, type TokenPackage } from '../services/paymentApi';

export default function TokenPurchase() {
  const [packages, setPackages] = useState<TokenPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState<string | null>(null);

  useEffect(() => {
    paymentApi.getPackages().then((data) => {
      setPackages(data.packages);
      setLoading(false);
    });
  }, []);

  const handlePurchase = async (packageId: string) => {
    setPurchasing(packageId);
    try {
      const { approval_url } = await paymentApi.createPayment(packageId);
      window.location.href = approval_url; // Redirect to PayPal
    } catch (error) {
      alert('Failed to start payment. Please try again.');
      setPurchasing(null);
    }
  };

  if (loading) return <div className="text-slate-400">Loading packages...</div>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {packages.map((pkg) => (
        <div
          key={pkg.id}
          className="relative rounded-2xl border border-slate-700 bg-slate-950/80 p-4 transition-colors hover:border-cyan-500/60"
        >
          {pkg.badge && (
            <div className="absolute right-3 top-3 rounded-full bg-cyan-500 px-2 py-0.5 text-xs font-semibold text-slate-950">
              {pkg.badge}
            </div>
          )}
          <h3 className="text-base font-bold text-white mb-1">{pkg.name}</h3>
          <div className="text-2xl font-bold text-white mb-0.5">
            {pkg.tokens.toLocaleString()}
            <span className="ml-1 text-sm text-slate-400">tokens</span>
          </div>
          <div className="mb-3 text-lg font-semibold text-cyan-300">
            ${pkg.price.toFixed(2)}
          </div>
          <button
            onClick={() => handlePurchase(pkg.id)}
            disabled={purchasing === pkg.id}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-500 px-3 py-2 text-sm font-medium text-slate-950 transition-colors hover:bg-cyan-400 disabled:opacity-50"
          >
            {purchasing === pkg.id ? (
              'Processing...'
            ) : (
              <>
                <span>Pay with PayPal</span>
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M20.067 8.478c.492.88.556 2.014.3 3.327-.74 3.806-3.276 5.12-6.514 5.12h-.5a.805.805 0 00-.794.68l-.04.22-.63 3.993-.028.15a.805.805 0 01-.793.68H8.032c-.356 0-.623-.29-.623-.645 0-.054.005-.108.016-.161l1.176-7.45a.805.805 0 01.793-.68h2.374c3.238 0 5.774-1.314 6.514-5.12.256-1.313.192-2.447-.3-3.327z"/>
                </svg>
              </>
            )}
          </button>
        </div>
      ))}
    </div>
  );
}
