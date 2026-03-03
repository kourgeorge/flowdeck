import { Link } from 'react-router-dom';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-gray-900/80 border-t border-gray-700 shrink-0">
      <div className="px-4 py-1.5 text-xs text-gray-500 flex flex-wrap items-center gap-x-2 gap-y-1">
        <Link to="/" className="hover:text-gray-300 transition-colors">Flowdeck</Link>
        <span>·</span>
        <Link to="/docs" className="hover:text-gray-300 transition-colors">Documentation</Link>
        <span>·</span>
        <Link to="/terms" className="hover:text-gray-300 transition-colors">Terms of Use</Link>
        <span>·</span>
        <Link to="/contact" className="hover:text-gray-300 transition-colors">Contact</Link>
        <span>·</span>
        <span>© {currentYear}</span>
      </div>
    </footer>
  );
}
