interface PageHeaderProps {
  title: string;
  icon?: React.ReactNode;
  children?: React.ReactNode;
}

/**
 * Shared page header bar: thin, same look across Chat, Copilot, Market, Admin.
 */
export default function PageHeader({ title, icon, children }: PageHeaderProps) {
  return (
    <div className="shrink-0 border-b border-gray-700 bg-gray-800/80 px-4 py-2 flex items-center gap-3">
      {icon != null && (
        <div className="flex items-center justify-center text-blue-400 shrink-0 [&_svg]:w-4 [&_svg]:h-4">
          {icon}
        </div>
      )}
      <span className="text-sm font-semibold text-white">{title}</span>
      {children != null && <div className="ml-auto flex items-center gap-2">{children}</div>}
    </div>
  );
}
