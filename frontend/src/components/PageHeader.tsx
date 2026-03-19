import { useContext, useEffect } from 'react';
import { LayoutHeaderContext } from './LayoutHeaderContext';

interface PageHeaderProps {
  title: string;
  icon?: React.ReactNode;
  children?: React.ReactNode;
  compact?: boolean;
}

function HamburgerIcon() {
  return (
    <span className="flex h-5 w-6 flex-col justify-center gap-1.5" aria-hidden>
      <span className="block h-0.5 w-full rounded bg-current" />
      <span className="block h-0.5 w-full rounded bg-current" />
      <span className="block h-0.5 w-full rounded bg-current" />
    </span>
  );
}

/**
 * Shared page header bar: thin, same look across Chat, Copilot, Market, Admin.
 */
export default function PageHeader({ title, icon, children, compact = false }: PageHeaderProps) {
  const layoutHeader = useContext(LayoutHeaderContext);

  useEffect(() => {
    layoutHeader?.registerPageHeader();
    return () => {
      layoutHeader?.unregisterPageHeader();
    };
  }, [layoutHeader]);

  return (
    <div className={`shrink-0 border-b border-gray-700 bg-gray-800/80 px-4 flex items-center ${compact ? 'gap-2 py-1' : 'gap-3 py-2'}`}>
      {layoutHeader?.showMobileMenuButton && (
        <button
          type="button"
          aria-label="Open menu"
          onClick={layoutHeader.openMobileMenu}
          className="md:hidden p-1 -ml-1 text-gray-300 hover:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 shrink-0"
        >
          <HamburgerIcon />
        </button>
      )}
      {icon != null && (
        <div className={`flex items-center justify-center text-blue-400 shrink-0 ${compact ? '[&_svg]:w-3 [&_svg]:h-3' : '[&_svg]:w-4 [&_svg]:h-4'}`}>
          {icon}
        </div>
      )}
      <span className={compact ? 'text-[11px] font-semibold text-white leading-none' : 'text-sm font-semibold text-white'}>{title}</span>
      {children != null && <div className={`ml-auto flex items-center ${compact ? 'gap-1.5' : 'gap-2'}`}>{children}</div>}
    </div>
  );
}
