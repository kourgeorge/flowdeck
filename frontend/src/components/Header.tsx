import { Link } from 'react-router-dom';
import { APP_NAME, LOGO_PATH } from '../config';

export default function Header() {
  return (
    <header className="bg-gray-900/95 border-b border-gray-700 sticky top-0 z-50 backdrop-blur-sm">
      <div className="max-w-layout mx-auto px-6 py-4">
        <div className="flex items-center justify-between">
          <Link
            to="/"
            className="flex items-center gap-3 text-xl font-bold text-white hover:text-blue-400 transition-colors focus:outline-none"
          >
            <img src={LOGO_PATH} alt="" className="w-8 h-8 object-contain" />
            {APP_NAME}
          </Link>
          <nav className="flex items-center gap-6">
            <Link
              to="/"
              className="text-gray-300 hover:text-white text-sm font-medium transition-colors"
            >
              Home
            </Link>
            <Link
              to="/how-it-works"
              className="text-gray-300 hover:text-white text-sm font-medium transition-colors"
            >
              How it works
            </Link>
            <Link
              to="/contact"
              className="text-gray-300 hover:text-white text-sm font-medium transition-colors"
            >
              Contact
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
}
