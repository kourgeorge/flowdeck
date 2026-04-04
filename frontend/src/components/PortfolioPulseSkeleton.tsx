// Skeleton loader components for Portfolio Pulse page

export function WidgetCardSkeleton() {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 animate-pulse">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="h-5 bg-gray-700 rounded w-20 mb-2"></div>
          <div className="h-4 bg-gray-700 rounded w-32"></div>
        </div>
        <div className="h-6 w-16 bg-gray-700 rounded-full"></div>
      </div>

      {/* Price and change */}
      <div className="mb-4">
        <div className="h-8 bg-gray-700 rounded w-28 mb-2"></div>
        <div className="h-5 bg-gray-700 rounded w-20"></div>
      </div>

      {/* Sparkline */}
      <div className="h-16 bg-gray-700 rounded mb-4"></div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="h-16 bg-gray-700 rounded"></div>
        <div className="h-16 bg-gray-700 rounded"></div>
        <div className="h-16 bg-gray-700 rounded"></div>
        <div className="h-16 bg-gray-700 rounded"></div>
      </div>

      {/* Brief excerpt */}
      <div className="space-y-2">
        <div className="h-3 bg-gray-700 rounded w-full"></div>
        <div className="h-3 bg-gray-700 rounded w-5/6"></div>
        <div className="h-3 bg-gray-700 rounded w-4/6"></div>
      </div>
    </div>
  );
}

export function DashboardPanelSkeleton({ title }: { title?: string }) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      {title && (
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-white">{title}</h3>
        </div>
      )}
      <div className="space-y-3 animate-pulse">
        <div className="h-4 bg-gray-700 rounded w-full"></div>
        <div className="h-4 bg-gray-700 rounded w-5/6"></div>
        <div className="h-4 bg-gray-700 rounded w-4/6"></div>
        <div className="h-4 bg-gray-700 rounded w-3/4"></div>
      </div>
    </div>
  );
}

export function StatTileSkeleton() {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 animate-pulse">
      <div className="h-4 bg-gray-700 rounded w-24 mb-3"></div>
      <div className="h-8 bg-gray-700 rounded w-20"></div>
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
    <div className="space-y-6">
      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTileSkeleton />
        <StatTileSkeleton />
        <StatTileSkeleton />
        <StatTileSkeleton />
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
