// Skeleton loader components for Portfolio Pulse page

export function WidgetCardSkeleton() {
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700/50 p-5 overflow-hidden relative">
      {/* Shimmer effect overlay */}
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-gray-700/20 to-transparent"></div>
      
      <div className="relative">
        {/* Header */}
        <div className="flex items-start justify-between mb-5">
          <div className="flex-1 space-y-2.5">
            <div className="h-5 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-md w-24 animate-pulse"></div>
            <div className="h-4 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-md w-36 animate-pulse"></div>
          </div>
          <div className="h-7 w-20 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-full animate-pulse"></div>
        </div>

        {/* Price and change */}
        <div className="mb-5 space-y-2.5">
          <div className="h-9 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-md w-32 animate-pulse"></div>
          <div className="h-5 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-md w-24 animate-pulse"></div>
        </div>

        {/* Sparkline chart */}
        <div className="h-20 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-lg mb-5 animate-pulse relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-t from-gray-800/50 to-transparent"></div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 gap-3 mb-5">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-gradient-to-br from-gray-700/50 to-gray-700/30 rounded-lg p-3 space-y-2 animate-pulse">
              <div className="h-3 bg-gray-600/50 rounded w-16"></div>
              <div className="h-5 bg-gray-600/50 rounded w-20"></div>
            </div>
          ))}
        </div>

        {/* Brief excerpt */}
        <div className="space-y-2.5 pt-3 border-t border-gray-700/50">
          <div className="h-3 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-full w-full animate-pulse"></div>
          <div className="h-3 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-full w-11/12 animate-pulse"></div>
          <div className="h-3 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-full w-3/4 animate-pulse"></div>
        </div>
      </div>
    </div>
  );
}

export function DashboardPanelSkeleton({ title }: { title?: string }) {
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700/50 p-6 overflow-hidden relative">
      {/* Shimmer effect overlay */}
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-gray-700/20 to-transparent"></div>
      
      <div className="relative">
        {title && (
          <div className="mb-5">
            <h3 className="text-lg font-semibold text-white">{title}</h3>
          </div>
        )}
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="h-10 w-10 bg-gradient-to-br from-gray-700 to-gray-700/50 rounded-lg animate-pulse flex-shrink-0"></div>
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-full animate-pulse" style={{ width: `${85 - i * 10}%` }}></div>
                <div className="h-3 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-full animate-pulse" style={{ width: `${60 - i * 8}%` }}></div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function StatTileSkeleton() {
  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700/50 p-5 overflow-hidden relative">
      {/* Shimmer effect overlay */}
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-gray-700/20 to-transparent"></div>
      
      <div className="relative space-y-3">
        <div className="h-4 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-md w-28 animate-pulse"></div>
        <div className="h-9 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-md w-24 animate-pulse"></div>
        <div className="h-3 bg-gradient-to-r from-gray-700 to-gray-700/50 rounded-full w-16 animate-pulse"></div>
      </div>
    </div>
  );
}

export function PortfolioPulseGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {Array.from({ length: count }).map((_, i) => (
        <WidgetCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function PortfolioPulseFullSkeleton() {
  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <StatTileSkeleton key={i} />
        ))}
      </div>

      {/* Main panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DashboardPanelSkeleton title="Market Overview" />
        <DashboardPanelSkeleton title="Top Movers" />
      </div>

      {/* Widget cards */}
      <PortfolioPulseGridSkeleton count={6} />
    </div>
  );
}

// Made with Bob
