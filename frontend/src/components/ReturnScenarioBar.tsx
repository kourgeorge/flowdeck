/**
 * ReturnScenarioBar
 *
 * Renders a compact visual spectrum bar for Bear / Expected / Bull return scenarios.
 * The bar spans from the most negative to the most positive value, with colour-coded
 * markers and labels for each scenario.
 *
 * Usage:
 *   <ReturnScenarioBar
 *     expected={8}
 *     bear={-12}
 *     bull={15}
 *   />
 */

interface ReturnScenarioBarProps {
  expected?: number | null;
  bear?: number | null;
  bull?: number | null;
  /** compact = smaller text / tighter spacing (default: false) */
  compact?: boolean;
}

function fmt(v: number) {
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

/** Map a value in [min, max] to a 0–100 percentage position */
function toPos(value: number, min: number, max: number): number {
  if (max === min) return 50;
  return ((value - min) / (max - min)) * 100;
}

export default function ReturnScenarioBar({
  expected,
  bear,
  bull,
  compact = false,
}: ReturnScenarioBarProps) {
  const hasAny = expected != null || bear != null || bull != null;
  if (!hasAny) return null;

  // Determine axis range — pad 10 % on each side so labels don't clip
  const values = [expected, bear, bull].filter((v): v is number => v != null);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const span = rawMax - rawMin || 10;
  const pad = span * 0.18;
  const axisMin = rawMin - pad;
  const axisMax = rawMax + pad;

  // Zero-line position (only shown when axis crosses zero)
  const showZero = axisMin < 0 && axisMax > 0;
  const zeroPos = toPos(0, axisMin, axisMax);

  const barH = compact ? 'h-1.5' : 'h-2';

  return (
    <div className={`w-full ${compact ? 'space-y-1' : 'space-y-2'}`}>
      {/* Label row */}
      <div className={`flex items-center gap-1 ${compact ? 'text-xs' : 'text-sm'} text-gray-400 font-medium`}>
        <span>Return Scenarios</span>
      </div>

      {/* Bar track */}
      <div className="relative w-full">
        {/* Gradient track */}
        <div
          className={`w-full ${barH} rounded-full`}
          style={{
            background:
              'linear-gradient(to right, #ef4444 0%, #f97316 25%, #6b7280 50%, #22c55e 75%, #10b981 100%)',
            opacity: 0.35,
          }}
        />

        {/* Zero line */}
        {showZero && (
          <div
            className="absolute top-0 bottom-0 w-px bg-gray-400/60"
            style={{ left: `${zeroPos}%` }}
          />
        )}

        {/* Bear marker */}
        {bear != null && (
          <Marker
            pos={toPos(bear, axisMin, axisMax)}
            color="#f87171"
            value={fmt(bear)}
            label="Bear"
            compact={compact}
            above={false}
          />
        )}

        {/* Bull marker */}
        {bull != null && (
          <Marker
            pos={toPos(bull, axisMin, axisMax)}
            color="#4ade80"
            value={fmt(bull)}
            label="Bull"
            compact={compact}
            above={false}
          />
        )}

        {/* Expected marker — rendered last so it sits on top */}
        {expected != null && (
          <Marker
            pos={toPos(expected, axisMin, axisMax)}
            color={expected >= 0 ? '#34d399' : '#f87171'}
            value={fmt(expected)}
            label="Expected"
            compact={compact}
            above={true}
            isExpected
          />
        )}
      </div>

      {/* Value chips row */}
      <div className={`flex flex-wrap gap-2 mt-1`}>
        {bear != null && (
          <Chip label="Bear" value={fmt(bear)} color="red" compact={compact} />
        )}
        {expected != null && (
          <Chip
            label="Expected"
            value={fmt(expected)}
            color={expected >= 0 ? 'green' : 'red'}
            compact={compact}
            highlight
          />
        )}
        {bull != null && (
          <Chip label="Bull" value={fmt(bull)} color="green" compact={compact} />
        )}
      </div>
    </div>
  );
}

// ─── Internal sub-components ──────────────────────────────────────────────────

interface MarkerProps {
  pos: number;
  color: string;
  value: string;
  label: string;
  compact: boolean;
  above: boolean;
  isExpected?: boolean;
}

function Marker({ pos, color, compact, isExpected }: MarkerProps) {
  if (isExpected) {
    // Expected: larger circle with white border ring — clearly distinct
    const size = compact ? 14 : 18;
    const inner = compact ? 8 : 10;
    return (
      <div
        className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex items-center justify-center"
        style={{ left: `${pos}%`, width: size, height: size }}
      >
        {/* Outer ring */}
        <div
          style={{
            position: 'absolute',
            width: size,
            height: size,
            borderRadius: '50%',
            border: `2px solid ${color}`,
            boxShadow: `0 0 8px ${color}99`,
          }}
        />
        {/* Inner filled circle */}
        <div
          style={{
            width: inner,
            height: inner,
            borderRadius: '50%',
            backgroundColor: color,
            boxShadow: `0 0 6px ${color}`,
          }}
        />
      </div>
    );
  }

  // Bear / Bull: small rotated diamond
  const size = compact ? 9 : 11;
  return (
    <div
      className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2"
      style={{ left: `${pos}%` }}
    >
      <div
        style={{
          width: size,
          height: size,
          backgroundColor: color,
          transform: 'rotate(45deg)',
          borderRadius: 2,
          opacity: 0.85,
        }}
      />
    </div>
  );
}

interface ChipProps {
  label: string;
  value: string;
  color: 'green' | 'red';
  compact: boolean;
  highlight?: boolean;
}

function Chip({ label, value, color, compact, highlight }: ChipProps) {
  const base = compact ? 'px-2 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs';

  const colorMap = {
    green: {
      normal: 'bg-green-500/15 text-green-400',
      highlighted: 'bg-green-500/30 text-green-300 ring-1 ring-inset ring-green-400/50',
      dot: '#4ade80',
    },
    red: {
      normal: 'bg-red-500/15 text-red-400',
      highlighted: 'bg-red-500/30 text-red-300 ring-1 ring-inset ring-red-400/50',
      dot: '#f87171',
    },
  };

  const c = colorMap[color];
  const cls = highlight ? c.highlighted : c.normal;

  if (highlight) {
    // Expected chip: solid look with ◎ icon and bold value
    return (
      <div className={`flex items-center gap-1.5 rounded-md ${base} ${cls} font-semibold`}>
        <span style={{ color: c.dot, fontSize: '0.7em', lineHeight: 1 }}>◎</span>
        <span className="text-gray-300">{label}</span>
        <span style={{ color: c.dot }}>{value}</span>
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-1.5 rounded-md ${base} ${cls} font-medium`}>
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0 opacity-70"
        style={{ backgroundColor: c.dot }}
      />
      <span className="text-gray-500">{label}</span>
      <span>{value}</span>
    </div>
  );
}

// Made with Bob
