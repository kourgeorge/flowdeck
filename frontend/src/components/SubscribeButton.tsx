import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { subscriptionApi } from '../services/subscriptionApi';
import AuthModal from './AuthModal';

interface SubscribeButtonProps {
  ticker: string;
  onSubscribed?: () => void;
  onUnsubscribed?: () => void;
  className?: string;
}

export default function SubscribeButton({ ticker, onSubscribed, onUnsubscribed, className = '' }: SubscribeButtonProps) {
  const { user } = useAuth();
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [authModalOpen, setAuthModalOpen] = useState(false);

  const checkSubscription = useCallback(async () => {
    if (!user || !ticker) {
      setChecking(false);
      return;
    }
    try {
      const list = await subscriptionApi.list();
      const sub = list.find((s) => s.ticker.toUpperCase() === ticker.toUpperCase());
      setIsSubscribed(!!sub);
    } catch {
      setIsSubscribed(false);
    } finally {
      setChecking(false);
    }
  }, [user, ticker]);

  useEffect(() => {
    checkSubscription();
  }, [checkSubscription]);

  const handleClick = async () => {
    if (!user) {
      setAuthModalOpen(true);
      return;
    }
    setLoading(true);
    try {
      if (isSubscribed) {
        await subscriptionApi.unsubscribe(ticker);
        setIsSubscribed(false);
        onUnsubscribed?.();
      } else {
        await subscriptionApi.subscribe(ticker);
        setIsSubscribed(true);
        onSubscribed?.();
      }
    } catch {
      // Show feedback on error
    } finally {
      setLoading(false);
    }
  };

  if (checking && user) {
    return (
      <button
        type="button"
        disabled
        className={`px-3 py-1.5 text-sm rounded-lg border border-gray-600 text-gray-400 ${className}`}
      >
        ...
      </button>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={handleClick}
        disabled={loading}
        className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors disabled:opacity-50 ${
          isSubscribed
            ? 'bg-gray-700 text-gray-300 border border-gray-600 hover:bg-gray-600'
            : 'bg-blue-600 text-white hover:bg-blue-700'
        } ${className}`}
      >
        {loading ? (isSubscribed ? 'Unsubscribing...' : 'Subscribing...') : isSubscribed ? 'Unsubscribe' : 'Subscribe'}
      </button>
      {authModalOpen && <AuthModal onClose={() => setAuthModalOpen(false)} />}
    </>
  );
}
