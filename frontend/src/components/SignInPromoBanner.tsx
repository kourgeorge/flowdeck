import { useAuth } from '../contexts/AuthContext';

interface SignInPromoBannerProps {
  onSignInClick: () => void;
  className?: string;
}

export default function SignInPromoBanner({ onSignInClick, className = '' }: SignInPromoBannerProps) {
  const { user } = useAuth();

  if (user) return null;

  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 px-4 py-3 bg-gradient-to-r from-blue-900/40 to-indigo-900/30 border-b border-gray-700/80 ${className}`}
      role="banner"
    >
      <p className="text-sm text-gray-200">
        <span className="font-medium text-white">Sign in</span> to subscribe to your favorite stocks and get them in one place on your home page.
      </p>
      <button
        type="button"
        onClick={onSignInClick}
        className="shrink-0 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900"
      >
        Sign in
      </button>
    </div>
  );
}
