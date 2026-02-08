import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { APP_NAME, LOGO_PATH } from '../config';
import Footer from './Footer';

const navItems = [
  { to: '/', label: 'Home' },
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
            className="flex flex-col items-center gap-2 rounded-lg hover:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-800 md:flex-1"
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
          className="flex-1 p-4"
          aria-label="Main navigation"
          onClick={() => setSidebarOpen(false)}
        >
          <ul className="space-y-1">
            {navItems.map(({ to, label }) => (
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
          </ul>
        </nav>
      </aside>

      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Hamburger: mobile only */}
        <div className="md:hidden sticky top-0 z-20 flex items-center border-b border-gray-700 bg-gray-900/95 px-4 py-3">
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
        <main className="flex-1 min-w-0">
          <Outlet />
        </main>
        <Footer />
      </div>
    </div>
  );
}
