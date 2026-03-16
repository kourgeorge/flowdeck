import { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { APP_NAME, LOGO_PATH, COPILOT_NAME } from '../config';
import { useAuth } from '../contexts/AuthContext';
import { digestApi } from '../services/api';
import AuthModal from './AuthModal';
import Footer from './Footer';

// Menu Icons
function FlowDeckIcon() {
  return (
    <img
      src={LOGO_PATH}
      alt=""
      className="w-5 h-5 object-contain shrink-0 grayscale opacity-90 [.bg-blue-600_&]:opacity-100 [.bg-blue-600_&]:invert [.bg-blue-600_&]:brightness-0"
      aria-hidden
    />
  );
}

function DashboardIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
    </svg>
  );
}

function CopilotIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
    </svg>
  );
}

function AdminIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  );
}

function ProfileIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
    </svg>
  );
}

function MarketIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
  );
}

function BriefIcon() {
  return (
    <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
    </svg>
  );
}

const navItems: { to: string; label: string; icon: () => JSX.Element; authOnly?: boolean }[] = [
  { to: '/', label: 'FlowDeck', icon: FlowDeckIcon },
  { to: '/market', label: 'Market View', icon: MarketIcon },
  { to: '/dashboard', label: 'Dashboard', icon: DashboardIcon, authOnly: true },
  { to: '/brief', label: 'Brief', icon: BriefIcon, authOnly: true },
  { to: '/copilot', label: 'Trading Copilot', icon: CopilotIcon, authOnly: true },
  { to: '/chat', label: 'AI Analyst Agent', icon: ChatIcon, authOnly: true },
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

function SidebarIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <rect x="3" y="3" width="18" height="18" rx="2" strokeWidth="2" />
      <path d="M9 3v18" strokeWidth="2" />
    </svg>
  );
}

function todayDateStr() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export default function Layout() {
  // Start collapsed on mobile (< 768px), expanded on desktop
  const [sidebarExpanded, setSidebarExpanded] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth >= 768;
    }
    return false;
  });
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [hasBriefForToday, setHasBriefForToday] = useState<boolean | null>(null);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!user) {
      setHasBriefForToday(null);
      return;
    }
    let cancelled = false;
    digestApi
      .getDigestDates(7)
      .then((res) => {
        if (cancelled) return;
        const dailyDates = (res.dates ?? []).filter((d) => !d.startsWith('w:'));
        setHasBriefForToday(dailyDates.includes(todayDateStr()));
      })
      .catch(() => {
        if (!cancelled) setHasBriefForToday(null);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  const closeSidebarIfMobile = () => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setSidebarExpanded(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Backdrop: mobile only when sidebar expanded */}
      {sidebarExpanded && (
        <button
          type="button"
          aria-label="Close menu"
          onClick={() => setSidebarExpanded(false)}
          className="fixed inset-0 bg-black/50 z-[70] md:hidden"
        />
      )}

      {/* Left sidebar: drawer on mobile, collapsible on desktop */}
      <aside
        className={`fixed md:relative inset-y-0 left-0 shrink-0 border-r border-gray-700 bg-gray-800/95 flex flex-col z-[80] transition-all duration-200 ease-out ${
          sidebarExpanded ? 'w-52 translate-x-0' : 'w-16 -translate-x-full md:translate-x-0'
        }`}
      >
        <div className={`p-4 border-b border-gray-700 flex items-center ${sidebarExpanded ? 'justify-between' : 'justify-center'}`}>
          {sidebarExpanded ? (
            <>
              <NavLink
                to="/"
                onClick={closeSidebarIfMobile}
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
                aria-label="Collapse menu"
                onClick={() => setSidebarExpanded(false)}
                className="p-2 -m-2 text-gray-400 hover:text-white rounded-lg transition-colors"
              >
                <SidebarIcon />
              </button>
            </>
          ) : (
            <button
              type="button"
              aria-label="Expand menu"
              onClick={() => setSidebarExpanded(true)}
              className="p-2 text-gray-400 hover:text-white rounded-lg transition-colors"
            >
              <img
                src={LOGO_PATH}
                alt=""
                className="w-8 h-8 object-contain"
              />
            </button>
          )}
        </div>
        <nav
          className="flex-1 p-4 overflow-y-auto flex flex-col"
          aria-label="Main navigation"
        >
          <div className="flex-1">
            <ul className="space-y-1">
              {navItems.map(({ to, label, icon: Icon, authOnly }) => {
                const disabled = authOnly && !user;
                const title = !sidebarExpanded ? (disabled ? `Sign in to access ${label}` : label) : undefined;
                if (disabled) {
                  return (
                    <li key={to}>
                      <button
                        type="button"
                        title={title}
                        onClick={() => { closeSidebarIfMobile(); setAuthModalOpen(true); }}
                        className={`flex items-center ${sidebarExpanded ? 'gap-3 px-4' : 'justify-center px-2'} py-2 rounded-lg text-sm font-medium w-full text-left cursor-pointer text-gray-500 hover:text-gray-400 opacity-75 hover:opacity-90 transition-colors pointer-events-auto`}
                      >
                        <Icon />
                        {sidebarExpanded && <span>{label}</span>}
                      </button>
                    </li>
                  );
                }
                const navActive = to === '/dashboard' ? location.pathname === '/dashboard' : undefined;
                const isBrief = to === '/brief';
                const showNoBrief = isBrief && hasBriefForToday === false;
                return (
                  <li key={to}>
                    <NavLink
                      to={to}
                      end={to === '/'}
                      title={title ?? (showNoBrief ? 'No brief generated for today' : undefined)}
                      onClick={closeSidebarIfMobile}
                      className={({ isActive }) => {
                        const active = navActive !== undefined ? navActive : isActive;
                        return `flex items-center ${sidebarExpanded ? 'gap-3 px-4' : 'justify-center px-2'} py-2 rounded-lg text-sm font-medium transition-colors ${
                          active
                            ? 'bg-blue-600 text-white'
                            : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                        }`;
                      }}
                    >
                      <span className="relative inline-flex shrink-0">
                        <Icon />
                        {showNoBrief && (
                          <span
                            className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-amber-500 ring-2 ring-gray-800"
                            aria-hidden
                          />
                        )}
                      </span>
                      {sidebarExpanded && (
                        <span className="flex flex-col items-start gap-0 min-w-0">
                          <span>{label}</span>
                          {showNoBrief && (
                            <span className="text-[10px] font-normal text-amber-400">No brief today</span>
                          )}
                        </span>
                      )}
                    </NavLink>
                  </li>
                );
              })}
              {user?.is_admin && (
                <>
                  <li aria-hidden="true">
                    <div className="my-2 border-t border-gray-700" />
                  </li>
                  <li>
                  <NavLink
                    to="/admin"
                    title={!sidebarExpanded ? 'Admin' : undefined}
                    onClick={closeSidebarIfMobile}
                    className={({ isActive }) =>
                      `flex items-center ${sidebarExpanded ? 'gap-3 px-4' : 'justify-center px-2'} py-2 rounded-lg text-sm font-medium transition-colors ${
                        isActive
                          ? 'bg-blue-600 text-white'
                          : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                      }`
                    }
                  >
                    <AdminIcon />
                    {sidebarExpanded && <span>Admin</span>}
                  </NavLink>
                </li>
                </>
              )}
            </ul>
          </div>
          
          {/* User menu at bottom */}
          <div className="mt-auto pt-4 border-t border-gray-700">
            {user && sidebarExpanded && (
              <p className="text-xs text-gray-400 truncate px-4 py-2 mb-2" title={user.email}>
                {user.email}
              </p>
            )}
            <ul className="space-y-1">
              {user ? (
                <>
                  <li>
                    <NavLink
                      to="/profile"
                      title={!sidebarExpanded ? 'Profile' : undefined}
                      onClick={closeSidebarIfMobile}
                      className={({ isActive }) =>
                        `flex items-center ${sidebarExpanded ? 'gap-3 px-4' : 'justify-center px-2'} py-2 rounded-lg text-sm font-medium transition-colors ${
                          isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                        }`
                      }
                    >
                      <ProfileIcon />
                      {sidebarExpanded && <span>Profile</span>}
                    </NavLink>
                  </li>
                  <li>
                    <button
                      type="button"
                      title={!sidebarExpanded ? 'Log out' : undefined}
                      onClick={() => { closeSidebarIfMobile(); logout(); navigate('/'); }}
                      className={`flex items-center ${sidebarExpanded ? 'gap-3 px-4' : 'justify-center px-2'} w-full text-left py-2 rounded-lg text-sm font-medium text-gray-300 hover:bg-gray-700 hover:text-white transition-colors`}
                    >
                      <LogoutIcon />
                      {sidebarExpanded && <span>Log out</span>}
                    </button>
                  </li>
                </>
              ) : (
                <>
                  <li>
                    <button
                      type="button"
                      title={!sidebarExpanded ? 'Sign in to access Profile' : undefined}
                      onClick={() => { closeSidebarIfMobile(); setAuthModalOpen(true); }}
                      className={`flex items-center ${sidebarExpanded ? 'gap-3 px-4' : 'justify-center px-2'} py-2 rounded-lg text-sm font-medium w-full text-left text-gray-500 hover:text-gray-400 opacity-75 hover:opacity-90 transition-colors`}
                    >
                      <ProfileIcon />
                      {sidebarExpanded && <span>Profile</span>}
                    </button>
                  </li>
                  {sidebarExpanded && (
                    <li>
                      <div className="rounded-lg bg-blue-950/60 border border-blue-700/40 p-3 flex flex-col gap-2">
                        <p className="text-xs text-gray-300 leading-snug">
                          <span className="font-medium text-white">Sign in</span> to run AI analysis on any stock, access your personalized dashboard, and use {COPILOT_NAME} — your Trading Copilot.
                        </p>
                        <button
                          type="button"
                          onClick={() => { closeSidebarIfMobile(); setAuthModalOpen(true); }}
                          className="w-full px-3 py-1.5 text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-900"
                        >
                          Sign in
                        </button>
                      </div>
                    </li>
                  )}
                </>
              )}
            </ul>
          </div>
        </nav>
      </aside>
      {authModalOpen && (
        <AuthModal onClose={() => setAuthModalOpen(false)} />
      )}

      {/* Main content area */}
      <div className="flex flex-col flex-1 min-w-0 min-h-0 h-screen overflow-hidden">
        {/* Hamburger: visible on mobile when sidebar is collapsed */}
        {!sidebarExpanded && (
          <div className="md:hidden sticky top-0 z-20 flex items-center border-b border-gray-700 bg-gray-900/95 px-3 py-1.5 shrink-0">
            <button
              type="button"
              aria-expanded={sidebarExpanded}
              aria-label="Open menu"
              onClick={() => setSidebarExpanded(true)}
              className="p-1 -ml-1 text-gray-300 hover:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <HamburgerIcon open={false} />
            </button>
          </div>
        )}
        <main className="flex-1 min-w-0 min-h-0 overflow-auto">
          <Outlet />
        </main>
        <Footer />
      </div>
    </div>
  );
}
