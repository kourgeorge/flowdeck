import type { ReactNode } from 'react';

// Skeleton loader components for Portfolio Pulse page

function SkeletonShimmer() {
  return (
    <div className="pointer-events-none absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-slate-700/20 to-transparent" />
  );
}

function SkeletonLine({
  width,
  height = 'h-3',
  rounded = 'rounded-full',
}: {
  width: string;
  height?: string;
  rounded?: string;
}) {
  return <div className={`${height} ${width} ${rounded} animate-pulse bg-slate-700/70`} />;
}

function SkeletonPanel({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`relative overflow-hidden rounded-[1.1rem] border border-slate-700/80 bg-slate-900/80 shadow-[0_14px_40px_rgba(2,6,23,0.28)] ${className}`}>
      <SkeletonShimmer />
      <div className="relative">{children}</div>
    </div>
  );
}

function SkeletonPanelHeader({
  titleWidth = 'w-32',
  subtitleWidth = 'w-52',
}: {
  titleWidth?: string;
  subtitleWidth?: string;
}) {
  return (
    <div className="border-b border-slate-700/70 px-4 py-3">
      <SkeletonLine width={titleWidth} height="h-4" rounded="rounded-md" />
      <div className="mt-2">
        <SkeletonLine width={subtitleWidth} />
      </div>
    </div>
  );
}

export function WidgetCardSkeleton() {
  return (
    <SkeletonPanel className="p-4">
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-2">
            <SkeletonLine width="w-20" height="h-5" rounded="rounded-md" />
            <SkeletonLine width="w-32" />
          </div>
          <SkeletonLine width="w-16" height="h-6" rounded="rounded-full" />
        </div>
        <SkeletonLine width="w-28" height="h-8" rounded="rounded-md" />
        <div className="h-20 rounded-[0.95rem] bg-slate-800/80" />
        <div className="grid grid-cols-2 gap-2">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-[0.95rem] border border-slate-700/70 bg-slate-950/40 p-3">
              <SkeletonLine width="w-14" />
              <div className="mt-2">
                <SkeletonLine width="w-16" height="h-5" rounded="rounded-md" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </SkeletonPanel>
  );
}

export function DashboardPanelSkeleton({ title }: { title?: string }) {
  return (
    <SkeletonPanel>
      <div className="border-b border-slate-700/70 px-4 py-3">
        {title ? (
          <div className="space-y-2">
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-300">{title}</div>
            <SkeletonLine width="w-48" />
          </div>
        ) : (
          <div className="space-y-2">
            <SkeletonLine width="w-28" height="h-4" rounded="rounded-md" />
            <SkeletonLine width="w-48" />
          </div>
        )}
      </div>
      <div className="space-y-3 p-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="flex items-center gap-3 rounded-[0.95rem] border border-slate-700/70 bg-slate-950/40 px-3 py-3">
            <div className="h-8 w-8 shrink-0 rounded-full bg-slate-700/70 animate-pulse" />
            <div className="min-w-0 flex-1 space-y-2">
              <SkeletonLine width={i % 2 === 0 ? 'w-3/4' : 'w-2/3'} />
              <SkeletonLine width={i % 2 === 0 ? 'w-1/2' : 'w-2/5'} />
            </div>
          </div>
        ))}
      </div>
    </SkeletonPanel>
  );
}

export function StatTileSkeleton() {
  return (
    <div className="relative overflow-hidden rounded-[0.9rem] border border-slate-700/70 bg-slate-950/40 px-3 py-2">
      <SkeletonShimmer />
      <div className="relative space-y-2">
        <SkeletonLine width="w-20" />
        <SkeletonLine width="w-14" height="h-7" rounded="rounded-md" />
        <SkeletonLine width="w-24" />
      </div>
    </div>
  );
}

export function PortfolioPulseGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <WidgetCardSkeleton key={i} />
      ))}
    </div>
  );
}

function HeroPanelSkeleton() {
  return (
    <div className="relative overflow-hidden rounded-[1.25rem] border border-cyan-400/25 bg-slate-900 px-5 py-5 shadow-[0_20px_60px_rgba(8,47,73,0.12)]">
      <SkeletonShimmer />
      <div className="pointer-events-none absolute -right-16 top-0 h-40 w-40 rounded-full bg-cyan-400/10 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 left-1/3 h-32 w-32 rounded-full bg-emerald-400/10 blur-3xl" />
      <div className="relative space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1 space-y-2">
            <SkeletonLine width="w-44" height="h-4" rounded="rounded-md" />
            <SkeletonLine width="w-full" />
            <SkeletonLine width="w-10/12" />
          </div>
          <SkeletonLine width="w-24" height="h-9" rounded="rounded-full" />
        </div>

        <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <StatTileSkeleton key={i} />
          ))}
        </div>

        <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_0.95fr_1.05fr]">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="rounded-[1.1rem] border border-white/10 bg-slate-950/30 p-3.5">
              <div className="mb-3 flex items-center justify-between gap-3">
                <SkeletonLine width={i === 1 ? 'w-28' : 'w-32'} height="h-4" rounded="rounded-md" />
                {i === 0 && <SkeletonLine width="w-20" height="h-6" rounded="rounded-full" />}
              </div>
              <div className={`grid gap-2 ${i === 2 ? 'grid-cols-1 xl:grid-cols-2' : 'grid-cols-1 sm:grid-cols-2'}`}>
                {[...Array(i === 1 ? 4 : 6)].map((_, item) => (
                  <div key={item} className="rounded-[0.95rem] border border-slate-700/70 bg-slate-900/70 px-3 py-3">
                    <SkeletonLine width="w-16" />
                    <div className="mt-2">
                      <SkeletonLine width={item % 2 === 0 ? 'w-full' : 'w-4/5'} />
                    </div>
                    <div className="mt-2">
                      <SkeletonLine width="w-12" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-[1.1rem] border border-white/10 bg-slate-950/30 p-3.5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <SkeletonLine width="w-36" height="h-4" rounded="rounded-md" />
            <SkeletonLine width="w-28" />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="flex items-center gap-3 rounded-[0.95rem] border border-slate-700/70 bg-slate-900/70 px-3 py-3">
                <div className="h-[68px] w-[68px] shrink-0 rounded-full bg-slate-700/60 animate-pulse" />
                <div className="min-w-0 flex-1 space-y-2">
                  <SkeletonLine width="w-12" />
                  <SkeletonLine width="w-16" />
                  <SkeletonLine width="w-10" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function EventsPanelSkeleton() {
  return (
    <SkeletonPanel className="flex h-full flex-col">
      <SkeletonPanelHeader titleWidth="w-16" subtitleWidth="w-44" />
      <div className="flex min-h-0 flex-1 flex-col p-4">
        <div className="space-y-1">
          {[...Array(16)].map((_, i) => (
            <div key={i} className="flex h-9 items-center justify-between gap-3 rounded-[0.9rem] border border-slate-700/70 bg-slate-950/40 px-3 py-2">
              <div className="flex min-w-0 items-center gap-2">
                <SkeletonLine width="w-12" height="h-5" rounded="rounded-full" />
                <SkeletonLine width={i % 3 === 0 ? 'w-36' : 'w-28'} />
              </div>
              <div className="flex items-center gap-1.5">
                <SkeletonLine width="w-10" height="h-5" rounded="rounded-full" />
                <SkeletonLine width="w-12" height="h-5" rounded="rounded-full" />
                <SkeletonLine width="w-12" height="h-5" rounded="rounded-full" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </SkeletonPanel>
  );
}

function PriceAndBriefRowSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.35fr_0.95fr]">
      <div className="flex min-h-[360px] flex-col gap-4">
        <SkeletonPanel className="min-h-[360px]">
          <SkeletonPanelHeader titleWidth="w-28" subtitleWidth="w-40" />
          <div className="p-4">
            <div className="h-[280px] rounded-[1rem] bg-slate-950/40" />
            <div className="mt-4 grid grid-cols-4 gap-2">
              {[...Array(4)].map((_, i) => (
                <SkeletonLine key={i} width="w-full" />
              ))}
            </div>
          </div>
        </SkeletonPanel>
        <div className="min-h-[320px]">
          <SkeletonPanel className="min-h-[320px]">
            <SkeletonPanelHeader titleWidth="w-40" subtitleWidth="w-52" />
            <div className="grid h-[248px] grid-cols-8 items-end gap-2 p-4">
              {[...Array(8)].map((_, i) => (
                <div
                  key={i}
                  className="rounded-t-[0.7rem] bg-slate-700/70 animate-pulse"
                  style={{ height: `${35 + (i % 4) * 18}%` }}
                />
              ))}
            </div>
          </SkeletonPanel>
        </div>
      </div>

      <SkeletonPanel className="min-h-[360px]">
        <SkeletonPanelHeader titleWidth="w-28" subtitleWidth="w-52" />
        <div className="space-y-3 p-4">
          <div className="flex gap-2">
            <SkeletonLine width="w-14" height="h-7" rounded="rounded-full" />
            <SkeletonLine width="w-16" height="h-7" rounded="rounded-full" />
            <SkeletonLine width="w-20" height="h-7" rounded="rounded-full" />
          </div>
          <div className="min-h-[240px] rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-4">
            <div className="space-y-3">
              {[...Array(9)].map((_, i) => (
                <SkeletonLine key={i} width={i % 3 === 0 ? 'w-full' : i % 3 === 1 ? 'w-11/12' : 'w-4/5'} />
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="rounded-[0.95rem] border border-slate-700/70 bg-slate-900/60 px-3 py-3">
                <SkeletonLine width="w-12" />
                <div className="mt-2">
                  <SkeletonLine width="w-20" />
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-[1rem] border border-emerald-500/20 bg-emerald-500/10 px-3 py-3">
            <SkeletonLine width="w-16" />
            <div className="mt-2 space-y-2">
              <SkeletonLine width="w-full" />
              <SkeletonLine width="w-5/6" />
            </div>
          </div>
        </div>
      </SkeletonPanel>
    </div>
  );
}

function BottomRowSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <SkeletonPanel>
        <SkeletonPanelHeader titleWidth="w-44" subtitleWidth="w-72" />
        <div className="space-y-3 p-4">
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-[0.9fr_1.1fr]">
            <div className="space-y-3">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {[...Array(2)].map((_, i) => (
                  <div key={i} className="rounded-[0.95rem] border border-slate-700/70 bg-slate-950/40 p-3">
                    <SkeletonLine width="w-14" />
                    <div className="mt-2">
                      <SkeletonLine width="w-20" />
                    </div>
                    <div className="mt-2">
                      <SkeletonLine width="w-12" />
                    </div>
                  </div>
                ))}
              </div>
              <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
                <div className="mb-3 flex items-center justify-between">
                  <SkeletonLine width="w-24" />
                  <SkeletonLine width="w-16" />
                </div>
                <div className="h-[180px] rounded-[0.95rem] bg-slate-900/70" />
              </div>
            </div>
            <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
              <div className="mb-3 flex items-center justify-between gap-3">
                <SkeletonLine width="w-28" />
                <div className="flex gap-1">
                  {[...Array(3)].map((_, i) => (
                    <SkeletonLine key={i} width="w-12" height="h-7" rounded="rounded-full" />
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="flex items-center justify-between rounded-[0.8rem] border border-slate-700/70 bg-slate-900/70 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <SkeletonLine width="w-10" />
                      <SkeletonLine width="w-8" />
                    </div>
                    <SkeletonLine width="w-12" />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
            <div className="mb-3 flex items-center justify-between">
              <SkeletonLine width="w-20" />
              <div className="flex gap-1">
                {[...Array(4)].map((_, i) => (
                  <SkeletonLine key={i} width="w-10" height="h-7" rounded="rounded-full" />
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="rounded-[0.95rem] border border-slate-700/70 bg-slate-900/70 px-3 py-3">
                  <div className="flex items-center justify-between gap-2">
                    <SkeletonLine width="w-12" />
                    <SkeletonLine width="w-10" height="h-6" rounded="rounded-full" />
                  </div>
                  <div className="mt-2">
                    <SkeletonLine width="w-24" />
                  </div>
                  <div className="mt-3 flex items-end justify-between gap-2">
                    <SkeletonLine width="w-14" />
                    <div className="h-[18px] w-[72px] rounded bg-slate-800/80" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </SkeletonPanel>

      <SkeletonPanel>
        <SkeletonPanelHeader titleWidth="w-44" subtitleWidth="w-72" />
        <div className="space-y-3 p-4">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {[...Array(2)].map((_, i) => (
              <div key={i} className="rounded-[0.95rem] border border-slate-700/70 bg-slate-950/40 p-3">
                <SkeletonLine width="w-20" />
                <div className="mt-2 space-y-2">
                  <SkeletonLine width="w-16" />
                  <SkeletonLine width="w-12" />
                </div>
              </div>
            ))}
          </div>

          <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-3">
            <div className="mb-3 flex items-center justify-between">
              <SkeletonLine width="w-32" />
              <SkeletonLine width="w-12" />
            </div>
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <div key={i}>
                  <div className="mb-1 flex items-center justify-between">
                    <SkeletonLine width="w-20" />
                    <SkeletonLine width="w-6" />
                  </div>
                  <div className="h-1.5 rounded-full bg-slate-800" />
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[1rem] border border-slate-700/70 bg-slate-950/40 p-2">
            <div className="mb-2 flex items-center justify-between px-2 py-1">
              <SkeletonLine width="w-28" />
              <SkeletonLine width="w-12" />
            </div>
            <div className="mb-3 flex flex-wrap gap-2 px-2">
              {[...Array(5)].map((_, i) => (
                <SkeletonLine key={i} width="w-14" height="h-7" rounded="rounded-full" />
              ))}
            </div>
            <div className="space-y-1.5">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="rounded-[0.9rem] border border-slate-700/60 bg-slate-900/70 px-3 py-3">
                  <div className="flex flex-wrap gap-1.5">
                    {[...Array(3)].map((__, j) => (
                      <SkeletonLine key={j} width="w-10" height="h-5" rounded="rounded-full" />
                    ))}
                  </div>
                  <div className="mt-2 space-y-2">
                    <SkeletonLine width="w-full" />
                    <SkeletonLine width="w-5/6" />
                    <SkeletonLine width="w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </SkeletonPanel>
    </div>
  );
}

export function PortfolioPulseFullSkeleton() {
  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="grid grid-cols-1 items-stretch gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <HeroPanelSkeleton />
        </div>
        <div className="h-full min-h-0">
          <EventsPanelSkeleton />
        </div>
      </div>

      <PriceAndBriefRowSkeleton />
      <BottomRowSkeleton />
    </div>
  );
}

// Made with Bob
