import { Link } from 'react-router-dom';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-gray-900/80 border-t border-gray-700 mt-auto">
      <div className="max-w-layout mx-auto px-6 py-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm">
            <Link
              to="/"
              className="hover:text-white transition-colors"
            >
              Flowdeck
            </Link>
            <span>·</span>
            <Link
              to="/how-it-works"
              className="hover:text-white transition-colors"
            >
              How it works
            </Link>
            <span>·</span>
            <Link
              to="/terms"
              className="hover:text-white transition-colors"
            >
              Terms of Use
            </Link>
            <span>·</span>
            <Link
              to="/contact"
              className="hover:text-white transition-colors"
            >
              Contact
            </Link>
            <span>·</span>
            <span>© {currentYear}</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
