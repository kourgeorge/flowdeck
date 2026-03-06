import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { consumePostAuthRedirect, setStoredAuth } from '../services/authApi';

export default function AuthCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = searchParams.get('token');
    const email = searchParams.get('email');
    const userId = searchParams.get('user_id');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      setError(errorParam);
      // Redirect to home after showing error
      setTimeout(() => {
        navigate('/');
      }, 3000);
      return;
    }

    if (token && email && userId) {
      // Store authentication
      setStoredAuth(token, email, parseInt(userId, 10));

      const target = consumePostAuthRedirect() ?? '/dashboard';
      // Force full reload so auth context initializes from stored credentials.
      window.location.replace(target);
    } else {
      setError('Invalid authentication response');
      setTimeout(() => {
        navigate('/');
      }, 3000);
    }
  }, [searchParams, navigate]);

  if (error) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center px-4">
        <div className="bg-gray-800 border border-red-500 rounded-lg p-6 max-w-md w-full">
          <h2 className="text-xl font-semibold text-red-400 mb-2">Authentication Error</h2>
          <p className="text-gray-300 mb-4">{error}</p>
          <p className="text-sm text-gray-400">Redirecting to home page...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center px-4">
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 max-w-md w-full">
        <div className="flex items-center justify-center mb-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        </div>
        <h2 className="text-xl font-semibold text-white text-center mb-2">
          Completing sign in...
        </h2>
        <p className="text-gray-400 text-center text-sm">
          Please wait while we complete your authentication.
        </p>
      </div>
    </div>
  );
}

// Made with Bob
