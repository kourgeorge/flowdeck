import { useState } from 'react';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { APP_NAME, LOGO_PATH, COPILOT_NAME } from '../config';
import { useAuth } from '../contexts/AuthContext';
import AuthModal from './AuthModal';

const navItems: { to: string; label: string; authOnly?: boolean }[] = [
  { to: '/dashboard', label: 'Dashboard', authOnly: true },
  { to: '/copilot', label: COPILOT_NAME, authOnly: true },
  { to: '/chat', label: 'AI Analyst Agent', authOnly: true },
];

function HamburgerIcon({ open }: { open: boolean }) {
  return (
    <span className="flex flex-col justify-center gap-1.5 w-6 h-5">
      <span
        className={`block h-0.5 w-full bg-current rounded transition-all duration-200 ${
          open ? 'rotate-45 translate-y-2' : ''
        }`}
      />
      <span
        className={`block h-0.5 w-full bg-current rounded transition-all duration-200 ${
          open ? 'opacity-0' : ''
        }`}
      />
      <span
        className={`block h-0.5 w-full bg-current rounded transition-all duration-200 ${
          open ? '-rotate-45 -translate-y-2' : ''
        }`}
      />
    </span>
  );
}

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen">
      {/* Backdrop: mobile only when sidebar open */}
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close menu"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
        />
      )}

      {/* Left sidebar: drawer on mobile, always visible on md+ */}
      <aside
        className={`fixed md:relative inset-y-0 left-0 w-52 shrink-0 border-r border-gray-700 bg-gray-800/95 flex flex-col z-40 transition-transform duration-200 ease-out ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <div className="p-4 border-b border-gray-700 flex items-center justify-between md:block">
          <NavLink
            to="/"
            onClick={() => setSidebarOpen(false)}
            className="flex flex-col items-center gap-2 rounded-lg hover:opacity-90 transition-opacity focus:outline-none md:flex-1"
          >
            <img
              src={LOGO_PATH}
              alt=""
              className="w-16 h-16 object-contain"
            />
            <span className="text-sm font-semibold text-white text-center leading-tight">
              {APP_NAME}
            </span>
          </NavLink>
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setSidebarOpen(false)}
            className="md:hidden p-2 -m-2 text-gray-400 hover:text-white rounded-lg"
          >
            <HamburgerIcon open />
          </button>
        </div>
        <nav
          className="flex-1 p-4 overflow-y-auto"
          aria-label="Main navigation"
          onClick={() => setSidebarOpen(false)}
        >
          {user && (
            <p className="text-xs text-gray-400 truncate px-4 py-1 mb-2" title={user.email}>
              {user.email}
            </p>
          )}
          <ul className="space-y-1">
            {navItems
              .filter((item) => !('authOnly' in item && item.authOnly) || user)
              .map(({ to, label }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    className={({ isActive }) =>
                      `block px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        isActive
                          ? 'bg-blue-600 text-white'
                          : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                      }`
                    }
                  >
                    {label}
                  </NavLink>
                </li>
              ))}
            {user?.is_admin && (
              <li>
                <NavLink
                  to="/admin"
                  className={({ isActive }) =>
                    `block px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                    }`
                  }
                >
                  Admin
                </NavLink>
              </li>
            )}
            {user && (
              <li>
                <NavLink
                  to="/profile"
                  className={({ isActive }) =>
                    `block px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                    }`
                  }
                >
                  Profile
                </NavLink>
              </li>
            )}
            <li>
              {user ? (
                <button
                  type="button"
                  onClick={() => { logout(); setSidebarOpen(false); navigate('/'); }}
                  className="block w-full text-left px-4 py-2 rounded-lg text-sm text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
                >
                  Log out
                </button>
              ) : (
                <div className="mt-2 rounded-lg bg-blue-950/60 border border-blue-700/40 p-3 flex flex-col gap-2">
                  <p className="text-xs text-gray-300 leading-snug">
                    <span className="font-medium text-white">Sign in</span> to run AI analysis on any stock, access your personalized dashboard, and use {COPILOT_NAME} — your Trading Copilot.
                  </p>
                  <button
                    type="button"
                    onClick={() => { setAuthModalOpen(true); setSidebarOpen(false); }}
                    className="w-full px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900"
                  >
                    Sign in
                  </button>
                </div>
              )}
            </li>
          </ul>
        </nav>
        {/* Sidebar bottom footer */}
        <div className="p-4 border-t border-gray-700 text-xs text-gray-500 flex flex-col gap-1">
          <div className="flex flex-wrap gap-x-2 gap-y-1">
            <Link to="/" className="hover:text-gray-300 transition-colors">Flowdeck</Link>
            <span>·</span>
            <Link to="/how-it-works" className="hover:text-gray-300 transition-colors">How it works</Link>
            <span>·</span>
            <Link to="/terms" className="hover:text-gray-300 transition-colors">Terms of Use</Link>
            <span>·</span>
            <Link to="/contact" className="hover:text-gray-300 transition-colors">Contact</Link>
          </div>
          <span>© {new Date().getFullYear()}</span>
        </div>
      </aside>
      {authModalOpen && (
        <AuthModal onClose={() => setAuthModalOpen(false)} />
      )}

      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0 min-h-0 h-screen overflow-hidden">
        {/* Hamburger: mobile only */}
        <div className="md:hidden sticky top-0 z-20 flex items-center border-b border-gray-700 bg-gray-900/95 px-4 py-3 shrink-0">
          <button
            type="button"
            aria-expanded={sidebarOpen}
            aria-label="Open menu"
            onClick={() => setSidebarOpen((o) => !o)}
            className="p-2 -ml-2 text-gray-300 hover:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <HamburgerIcon open={sidebarOpen} />
          </button>
        </div>
        <main className="flex-1 min-w-0 min-h-0 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
