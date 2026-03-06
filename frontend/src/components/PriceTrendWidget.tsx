import { useEffect, useState, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, HistogramData, UTCTimestamp, ColorType } from 'lightweight-charts';
import { tickerApi } from '../services/api';

interface HistoricalPrice {
  date: string;
  timestamp: number | null;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  adj_close: number;
}

interface HistoricalData {
  ticker: string;
  period: string;
  interval: string;
  data: HistoricalPrice[];
  count: number;
}

interface PriceTrendWidgetProps {
  ticker: string;
  period?: string;
  height?: number;
  /** When true, widget fills parent height and chart uses full tile space (for overview next to key data) */
  fillTile?: boolean;
}

// Convert 'YYYY-MM-DD' to 'yyyyMMdd' for lightweight-charts business day, or use Unix seconds
function toChartTime(dateStr: string, timestamp: number | null): UTCTimestamp | string {
  if (timestamp != null) return Math.floor(timestamp / 1000) as UTCTimestamp;
  const [y, m, d] = dateStr.split('-');
  return `${y}${m}${d}`;
}

export default function PriceTrendWidget({ ticker, period = '6mo', height = 300, fillTile = false }: PriceTrendWidgetProps) {
  const [data, setData] = useState<HistoricalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState(period);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  const periods = [
    { label: '1D', value: '1d' },
    { label: '1W', value: '5d' },
    { label: '1M', value: '1mo' },
    { label: '3M', value: '3mo' },
    { label: '6M', value: '6mo' },
    { label: 'YTD', value: 'ytd' },
    { label: '1Y', value: '1y' },
    { label: '5Y', value: '5y' },
    { label: '10Y', value: '10y' },
    { label: 'MAX', value: 'max' },
  ];

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const interval = selectedPeriod === '1d' ? '5m' : '1d';
        const historicalData = await tickerApi.getHistoricalPrices(ticker, selectedPeriod, interval);
        setData(historicalData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
        console.error('Error fetching historical data:', err);
      } finally {
        setLoading(false);
      }
    };

    if (ticker) {
      fetchData();
    }
  }, [ticker, selectedPeriod]);

  // Create or update TradingView Lightweight Chart
  useEffect(() => {
    if (!containerRef.current || !data?.data?.length) return;

    const el = containerRef.current;
    const width = el.clientWidth;
    const heightPx = fillTile ? el.clientHeight : Math.max(200, Math.min(height, width * 0.55));
    if (width < 50 || heightPx < 50) return;

    // Cleanup previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    }

    const chart = createChart(el, {
      width,
      height: heightPx,
      layout: {
        background: { type: ColorType.Solid, color: '#1f2937' },
        textColor: '#9ca3af',
        fontFamily: 'system-ui, sans-serif',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#374151' },
        horzLines: { color: '#374151' },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          labelBackgroundColor: '#6366f1',
        },
        horzLine: {
          labelBackgroundColor: '#6366f1',
        },
      },
      rightPriceScale: {
        borderColor: '#4b5563',
        scaleMargins: { top: 0.1, bottom: 0.25 },
        entireTextOnly: true,
      },
      timeScale: {
        borderColor: '#4b5563',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderDownColor: '#ef4444',
      borderUpColor: '#10b981',
      wickDownColor: '#ef4444',
      wickUpColor: '#10b981',
    });
    candleSeriesRef.current = candleSeries;

    const candleData: CandlestickData[] = data.data.map((d) => ({
      time: toChartTime(d.date, d.timestamp),
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));
    candleSeries.setData(candleData);

    // Volume histogram at bottom (overlay)
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });
    volumeSeriesRef.current = volumeSeries;
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
      borderVisible: false,
    });

    const volumeData: HistogramData[] = data.data.map((d) => ({
      time: toChartTime(d.date, d.timestamp),
      value: d.volume ?? 0,
      color: d.close >= d.open ? 'rgba(16, 185, 129, 0.6)' : 'rgba(239, 68, 68, 0.6)',
    }));
    volumeSeries.setData(volumeData);

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (!chartRef.current || !containerRef.current) return;
      const w = containerRef.current.clientWidth;
      const h = fillTile ? containerRef.current.clientHeight : Math.max(200, Math.min(height, w * 0.55));
      chartRef.current.applyOptions({ width: w, height: h });
    };

    const ro = new ResizeObserver(handleResize);
    ro.observe(el);

    return () => {
      ro.disconnect();
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        candleSeriesRef.current = null;
        volumeSeriesRef.current = null;
      }
    };
  }, [data, ticker, selectedPeriod, fillTile, height]);

  if (loading) {
    const loadClass = fillTile ? 'bg-gray-800 rounded-lg border border-gray-700 p-3 sm:p-4 overflow-hidden min-w-0 min-h-0 flex flex-col h-full' : 'bg-gray-800 rounded-lg border border-gray-700 p-6';
    return (
      <div className={loadClass}>
        <div className="animate-pulse flex-1 min-h-[200px] flex flex-col">
          <div className="h-6 bg-gray-700 rounded w-32 mb-4 shrink-0"></div>
          <div className="flex-1 bg-gray-700 rounded min-h-[160px]"></div>
        </div>
      </div>
    );
  }

  if (error || !data || data.data.length === 0) {
    const errClass = fillTile ? 'bg-gray-800 rounded-lg border border-gray-700 p-3 sm:p-4 overflow-hidden min-w-0 min-h-0 flex flex-col h-full' : 'bg-gray-800 rounded-lg border border-gray-700 p-6';
    return (
      <div className={errClass}>
        <h3 className="text-lg font-semibold text-white mb-4">Price Trend</h3>
        <div className="text-gray-400 text-sm">Unable to load price data</div>
      </div>
    );
  }

  const rootClass = fillTile
    ? 'bg-gray-800 rounded-lg border border-gray-700 p-3 sm:p-4 overflow-hidden min-w-0 min-h-0 flex flex-col h-full'
    : 'bg-gray-800 rounded-lg border border-gray-700 p-4 sm:p-6 overflow-hidden min-w-0';
  const chartWrapperClass = fillTile
    ? 'relative min-w-0 w-full flex-1 min-h-[200px]'
    : 'relative min-w-0 w-full';

  return (
    <div className={rootClass}>
      <div className={fillTile ? 'mb-2 shrink-0' : 'mb-4'}>
        <h3 className="text-lg font-semibold text-white">Price Trend</h3>
      </div>

      <div
        ref={containerRef}
        className={chartWrapperClass}
        style={fillTile ? { minHeight: 200 } : { height: Math.max(200, Math.min(height, 400)) }}
      />

      <div className={`border-t border-gray-700 min-w-0 ${fillTile ? 'mt-2 pt-2 shrink-0' : 'mt-4 pt-4'}`}>
        <div className="flex flex-wrap gap-2 justify-center">
          {periods.map((p) => (
            <button
              key={p.value}
              onClick={() => setSelectedPeriod(p.value)}
              className={`px-2 sm:px-3 py-1 text-xs font-medium transition-colors shrink-0 ${
                selectedPeriod === p.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
