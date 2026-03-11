import { Link } from 'react-router-dom';
import { useState } from 'react';
import { APP_NAME, LOGO_PATH } from '../config';

export default function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

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

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-6">
            <Link
              to="/"
              className="text-gray-300 hover:text-white text-sm font-medium transition-colors"
            >
              Home
            </Link>
            <Link
              to="/market"
              className="text-gray-300 hover:text-white text-sm font-medium transition-colors"
            >
              Market View
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

          {/* Mobile Menu Button */}
          <button
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="md:hidden text-gray-300 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 rounded p-2"
            aria-label="Toggle menu"
            aria-expanded={isMenuOpen}
          >
            <svg
              className="w-6 h-6"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              {isMenuOpen ? (
                <path d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Navigation Menu */}
        {isMenuOpen && (
          <nav className="md:hidden mt-4 pb-4 flex flex-col gap-4 border-t border-gray-700 pt-4">
            <Link
              to="/"
              className="text-gray-300 hover:text-white text-sm font-medium transition-colors"
              onClick={() => setIsMenuOpen(false)}
            >
              Home
            </Link>
            <Link
              to="/market"
              className="text-gray-300 hover:text-white text-sm font-medium transition-colors"
              onClick={() => setIsMenuOpen(false)}
            >
              Market View
            </Link>
            <Link
              to="/how-it-works"
              className="text-gray-300 hover:text-white text-sm font-medium transition-colors"
              onClick={() => setIsMenuOpen(false)}
            >
              How it works
            </Link>
            <Link
              to="/contact"
              className="text-gray-300 hover:text-white text-sm font-medium transition-colors"
              onClick={() => setIsMenuOpen(false)}
            >
              Contact
            </Link>
          </nav>
        )}
      </div>
    </header>
  );
}
