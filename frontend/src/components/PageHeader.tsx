interface PageHeaderProps {
  title: string;
  icon?: React.ReactNode;
  children?: React.ReactNode;
  compact?: boolean;
}

/**
 * Shared page header bar: thin, same look across Chat, Copilot, Market, Admin.
 */
export default function PageHeader({ title, icon, children, compact = false }: PageHeaderProps) {
  return (
    <div className={`shrink-0 border-b border-gray-700 bg-gray-800/80 px-4 flex items-center ${compact ? 'gap-2 py-1' : 'gap-3 py-2'}`}>
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
