import React from 'react';

interface FundamentalData {
  Symbol?: string;
  Name?: string;
  Description?: string;
  Sector?: string;
  Industry?: string;
  Exchange?: string;
  Currency?: string;
  Country?: string;
  MarketCapitalization?: string | number;
  EBITDA?: string | number;
  PERatio?: string | number;
  PEGRatio?: string | number;
  BookValue?: string | number;
  DividendPerShare?: string | number;
  DividendYield?: string | number;
  EPS?: string | number;
  RevenuePerShareTTM?: string | number;
  ProfitMargin?: string | number;
  OperatingMarginTTM?: string | number;
  ReturnOnAssetsTTM?: string | number;
  ReturnOnEquityTTM?: string | number;
  RevenueTTM?: string | number;
  GrossProfitTTM?: string | number;
  DilutedEPSTTM?: string | number;
  QuarterlyEarningsGrowthYOY?: string | number;
  QuarterlyRevenueGrowthYOY?: string | number;
  AnalystTargetPrice?: string | number;
  AnalystRatingStrongBuy?: string | number;
  AnalystRatingBuy?: string | number;
  AnalystRatingHold?: string | number;
  AnalystRatingSell?: string | number;
  AnalystRatingStrongSell?: string | number;
  TrailingPE?: string | number;
  ForwardPE?: string | number;
  PriceToSalesRatioTTM?: string | number;
  PriceToBookRatio?: string | number;
  EVToRevenue?: string | number;
  EVToEBITDA?: string | number;
  Beta?: string | number;
  '52WeekHigh'?: string | number;
  '52WeekLow'?: string | number;
  '50DayMovingAverage'?: string | number;
  '200DayMovingAverage'?: string | number;
  SharesOutstanding?: string | number;
  SharesFloat?: string | number;
  PercentInsiders?: string | number;
  PercentInstitutions?: string | number;
  DividendDate?: string;
  ExDividendDate?: string;
  LatestQuarter?: string;
  FiscalYearEnd?: string;
  Address?: string;
  OfficialSite?: string;
  CIK?: string;
  [key: string]: any;
}

interface FundamentalPanesProps {
  data: FundamentalData;
  analystRecommendations?: {
    recommendation?: string;
    target_price?: number | string;
    latest_date?: string;
    breakdown?: Record<string, number | string>;
    total_analysts?: number | string;
  } | null;
  isLoadingRecommendations?: boolean;
  companyOfficers?: any[];
  isLoadingOfficers?: boolean;
}

const FundamentalPanes: React.FC<FundamentalPanesProps> = ({
  data,
  analystRecommendations,
  isLoadingRecommendations = false,
  companyOfficers = [],
  isLoadingOfficers = false
}) => {
  const fundamentalData = data;
  const OFFICERS_PER_PAGE = 5;
  const [officersPage, setOfficersPage] = React.useState(1);

  // Format number with appropriate units
  const formatNumber = (value: string | number | null | undefined, decimals: number = 2): string => {
    if (value === null || value === undefined || value === 'N/A' || value === '') return 'N/A';
    const num = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(num)) return 'N/A';
    if (Math.abs(num) >= 1e12) return `$${(num / 1e12).toFixed(decimals)}T`;
    if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(decimals)}B`;
    if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(decimals)}M`;
    if (Math.abs(num) >= 1e3) return `$${(num / 1e3).toFixed(decimals)}K`;
    return `$${num.toFixed(decimals)}`;
  };

  // Format percentage
  const formatPercent = (value: string | number | null | undefined, decimals: number = 2): string => {
    if (value === null || value === undefined || value === 'N/A' || value === '') return 'N/A';
    const num = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(num)) return 'N/A';
    return `${(num * 100).toFixed(decimals)}%`;
  };

  // Format ratio
  const formatRatio = (value: string | number | null | undefined, decimals: number = 2): string => {
    if (value === null || value === undefined || value === 'N/A' || value === '') return 'N/A';
    const num = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(num)) return 'N/A';
    return num.toFixed(decimals);
  };

  // Format date
  const formatDate = (value: string | null | undefined): string => {
    if (!value || value === 'N/A') return 'N/A';
    try {
      const date = new Date(value);
      return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch {
      return value;
    }
  };

  // Calculate analyst rating summary
  const strongBuy = parseFloat(String(fundamentalData.AnalystRatingStrongBuy || 0));
  const buy = parseFloat(String(fundamentalData.AnalystRatingBuy || 0));
  const hold = parseFloat(String(fundamentalData.AnalystRatingHold || 0));
  const sell = parseFloat(String(fundamentalData.AnalystRatingSell || 0));
  const strongSell = parseFloat(String(fundamentalData.AnalystRatingStrongSell || 0));
  const totalRatings = strongBuy + buy + hold + sell + strongSell;
  const buyPercentage = totalRatings > 0 ? ((strongBuy + buy) / totalRatings) * 100 : 0;
  const totalOfficerPages = Math.max(1, Math.ceil(companyOfficers.length / OFFICERS_PER_PAGE));
  const officerStartIndex = (officersPage - 1) * OFFICERS_PER_PAGE;
  const officerEndIndex = officerStartIndex + OFFICERS_PER_PAGE;
  const visibleOfficers = companyOfficers.slice(officerStartIndex, officerEndIndex);

  React.useEffect(() => {
    setOfficersPage((prevPage) => Math.min(prevPage, totalOfficerPages));
  }, [totalOfficerPages]);

  React.useEffect(() => {
    setOfficersPage(1);
  }, [companyOfficers]);

  return (
    <div className="space-y-6">
      {/* Company Overview Section */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          Company Overview
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-400 mb-1">Company Name</p>
            <p className="text-white font-semibold">{fundamentalData.Name || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-400 mb-1">Symbol</p>
            <p className="text-white font-semibold">{fundamentalData.Symbol || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-400 mb-1">Sector</p>
            <p className="text-white font-semibold">{fundamentalData.Sector || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-400 mb-1">Industry</p>
            <p className="text-white font-semibold">{fundamentalData.Industry || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-400 mb-1">Exchange</p>
            <p className="text-white font-semibold">{fundamentalData.Exchange || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm text-gray-400 mb-1">Country</p>
            <p className="text-white font-semibold">{fundamentalData.Country || 'N/A'}</p>
          </div>
          {fundamentalData.Description && (
            <div className="md:col-span-2">
              <p className="text-sm text-gray-400 mb-1">Description</p>
              <p className="text-gray-300 text-sm leading-relaxed">{fundamentalData.Description}</p>
            </div>
          )}
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Valuation Metrics */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Valuation Metrics
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Market Cap</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData.MarketCapitalization)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Enterprise Value</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData.EVToRevenue ? parseFloat(String(fundamentalData.EVToRevenue)) * parseFloat(String(fundamentalData.RevenueTTM || 0)) : null)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">P/E Ratio (Trailing)</span>
              <span className="text-white font-semibold">{formatRatio(fundamentalData.TrailingPE || fundamentalData.PERatio)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">P/E Ratio (Forward)</span>
              <span className="text-white font-semibold">{formatRatio(fundamentalData.ForwardPE)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">PEG Ratio</span>
              <span className="text-white font-semibold">{formatRatio(fundamentalData.PEGRatio)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Price to Sales</span>
              <span className="text-white font-semibold">{formatRatio(fundamentalData.PriceToSalesRatioTTM)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Price to Book</span>
              <span className="text-white font-semibold">{formatRatio(fundamentalData.PriceToBookRatio)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">EV/Revenue</span>
              <span className="text-white font-semibold">{formatRatio(fundamentalData.EVToRevenue)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">EV/EBITDA</span>
              <span className="text-white font-semibold">{formatRatio(fundamentalData.EVToEBITDA)}</span>
            </div>
          </div>
        </div>

        {/* Profitability Metrics */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
            Profitability
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Revenue (TTM)</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData.RevenueTTM)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Gross Profit (TTM)</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData.GrossProfitTTM)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">EBITDA</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData.EBITDA)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Profit Margin</span>
              <span className="text-white font-semibold">{formatPercent(fundamentalData.ProfitMargin)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Operating Margin</span>
              <span className="text-white font-semibold">{formatPercent(fundamentalData.OperatingMarginTTM)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Return on Assets</span>
              <span className="text-white font-semibold">{formatPercent(fundamentalData.ReturnOnAssetsTTM)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Return on Equity</span>
              <span className="text-white font-semibold">{formatPercent(fundamentalData.ReturnOnEquityTTM)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">EPS (TTM)</span>
              <span className="text-white font-semibold">{formatRatio(fundamentalData.DilutedEPSTTM || fundamentalData.EPS)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Revenue per Share</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData.RevenuePerShareTTM)}</span>
            </div>
          </div>
        </div>

        {/* Growth & Performance */}
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
            </svg>
            Growth & Performance
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Quarterly Revenue Growth</span>
              <span className={`font-semibold ${parseFloat(String(fundamentalData.QuarterlyRevenueGrowthYOY || 0)) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {formatPercent(fundamentalData.QuarterlyRevenueGrowthYOY)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Quarterly Earnings Growth</span>
              <span className={`font-semibold ${parseFloat(String(fundamentalData.QuarterlyEarningsGrowthYOY || 0)) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {formatPercent(fundamentalData.QuarterlyEarningsGrowthYOY)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Beta</span>
              <span className="text-white font-semibold">{formatRatio(fundamentalData.Beta)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">52 Week High</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData['52WeekHigh'])}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">52 Week Low</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData['52WeekLow'])}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">50 Day MA</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData['50DayMovingAverage'])}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">200 Day MA</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData['200DayMovingAverage'])}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Dividends & Ownership */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Dividends
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Dividend Yield</span>
              <span className="text-white font-semibold">{formatPercent(fundamentalData.DividendYield)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Dividend per Share</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData.DividendPerShare)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Dividend Date</span>
              <span className="text-white font-semibold">{formatDate(fundamentalData.DividendDate)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Ex-Dividend Date</span>
              <span className="text-white font-semibold">{formatDate(fundamentalData.ExDividendDate)}</span>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            Ownership
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Shares Outstanding</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData.SharesOutstanding)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Shares Float</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData.SharesFloat)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">% Insiders</span>
              <span className="text-white font-semibold">{formatPercent(fundamentalData.PercentInsiders)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">% Institutions</span>
              <span className="text-white font-semibold">{formatPercent(fundamentalData.PercentInstitutions)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Book Value</span>
              <span className="text-white font-semibold">{formatNumber(fundamentalData.BookValue)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Analyst Ratings */}
      {totalRatings > 0 && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Analyst Ratings
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <div className="flex items-center justify-between mb-4">
                <span className="text-white font-semibold">Target Price</span>
                <span className="text-xl text-blue-400 font-bold">
                  {formatNumber(fundamentalData.AnalystTargetPrice)}
                </span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-400">Strong Buy</span>
                  <span className="text-green-400 font-semibold">{strongBuy}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-400">Buy</span>
                  <span className="text-blue-400 font-semibold">{buy}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-400">Hold</span>
                  <span className="text-yellow-400 font-semibold">{hold}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-400">Sell</span>
                  <span className="text-orange-400 font-semibold">{sell}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-400">Strong Sell</span>
                  <span className="text-red-400 font-semibold">{strongSell}</span>
                </div>
              </div>
            </div>
            <div>
              <div className="mb-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-gray-400">Total Ratings</span>
                  <span className="text-white font-semibold">{totalRatings}</span>
                </div>
                <div className="w-full bg-gray-700 rounded-full h-3 mb-2">
                  <div
                    className="bg-gradient-to-r from-green-500 to-blue-500 h-3 rounded-full transition-all duration-300"
                    style={{ width: `${buyPercentage}%` }}
                  ></div>
                </div>
                <p className="text-xs text-gray-400">Buy Rating: {buyPercentage.toFixed(1)}%</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Analyst Recommendations (Yahoo Finance) */}
      {isLoadingRecommendations ? (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <div className="animate-pulse">
            <div className="h-6 bg-gray-700 rounded w-48 mb-4"></div>
            <div className="h-32 bg-gray-700 rounded"></div>
          </div>
        </div>
      ) : analystRecommendations && analystRecommendations.recommendation ? (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Analyst Recommendations (Yahoo Finance)</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <div className="mb-4">
                <div className="text-sm text-gray-400 mb-2">Overall Recommendation</div>
                <div className={`text-3xl font-bold ${
                  analystRecommendations.recommendation === 'BUY'
                    ? 'text-green-400'
                    : analystRecommendations.recommendation === 'SELL'
                    ? 'text-red-400'
                    : 'text-yellow-400'
                }`}>
                  {analystRecommendations.recommendation}
                </div>
                {analystRecommendations.target_price != null && !Number.isNaN(Number(analystRecommendations.target_price)) && (
                  <div className="text-sm text-gray-400 mt-2">
                    Target Price: <span className="text-white font-semibold">${Number(analystRecommendations.target_price).toFixed(2)}</span>
                  </div>
                )}
                {analystRecommendations.latest_date && (
                  <div className="text-xs text-gray-500 mt-1">
                    Updated: {new Date(analystRecommendations.latest_date).toLocaleDateString()}
                  </div>
                )}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-400 mb-3">Recommendation Breakdown</div>
              <div className="space-y-2">
                {analystRecommendations.breakdown && Object.entries(analystRecommendations.breakdown).map(([rating, count]) => {
                  const numCount = Number(count);
                  const totalAnalysts = Number(analystRecommendations.total_analysts ?? 0);
                  return (
                    <div key={rating} className="flex items-center justify-between">
                      <span className="text-sm text-gray-300">{rating}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-32 bg-gray-700 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${
                              rating === 'Strong Buy' || rating === 'Buy' ? 'bg-green-500' :
                              rating === 'Strong Sell' || rating === 'Sell' ? 'bg-red-500' :
                              'bg-yellow-500'
                            }`}
                            style={{ width: `${totalAnalysts > 0 ? (numCount / totalAnalysts) * 100 : 0}%` }}
                          ></div>
                        </div>
                        <span className="text-sm font-semibold text-white w-8 text-right">{numCount}</span>
                      </div>
                    </div>
                  );
                })}
                <div className="pt-2 border-t border-gray-700">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-gray-300">Total Analysts</span>
                    <span className="text-sm font-bold text-white">{analystRecommendations.total_analysts ?? 'N/A'}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : analystRecommendations && !analystRecommendations.recommendation ? (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-2">Analyst Recommendations (Yahoo Finance)</h3>
          <p className="text-gray-400 text-sm">No analyst recommendations available for this stock.</p>
        </div>
      ) : null}

      {/* Company Officers */}
      {isLoadingOfficers ? (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 animate-pulse">
          <div className="h-6 bg-gray-700 rounded w-40 mb-4" />
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-gray-700 rounded" />
            ))}
          </div>
        </div>
      ) : companyOfficers.length > 0 ? (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            Company Officers
          </h3>
          <div className="space-y-3">
            {visibleOfficers.map((officer, idx) => (
              <div
                key={idx}
                className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 py-3 border-b border-gray-700 last:border-0"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm font-semibold truncate">{officer.name}</p>
                  <p className="text-gray-400 text-xs truncate">{officer.title}</p>
                </div>
                <div className="flex items-center gap-3 text-xs shrink-0">
                  {officer.age && (
                    <span className="text-gray-400">
                      Age: <span className="text-white font-medium">{officer.age}</span>
                    </span>
                  )}
                  {officer.total_pay && (
                    <span className="text-gray-400">
                      Pay: <span className="text-green-400 font-medium">
                        ${(officer.total_pay / 1000000).toFixed(2)}M
                      </span>
                    </span>
                  )}
                </div>
              </div>
            ))}
            {companyOfficers.length > 5 && (
              <div className="pt-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <p className="text-gray-500 text-xs text-center sm:text-left">
                  Showing {officerStartIndex + 1}-{Math.min(officerEndIndex, companyOfficers.length)} of {companyOfficers.length} officers
                </p>
                <div className="flex items-center justify-center sm:justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setOfficersPage((prevPage) => Math.max(1, prevPage - 1))}
                    disabled={officersPage === 1}
                    className="px-3 py-1 text-xs rounded border border-gray-600 text-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-700 transition-colors"
                  >
                    Previous
                  </button>
                  <span className="text-xs text-gray-400">
                    Page {officersPage} of {totalOfficerPages}
                  </span>
                  <button
                    type="button"
                    onClick={() => setOfficersPage((prevPage) => Math.min(totalOfficerPages, prevPage + 1))}
                    disabled={officersPage === totalOfficerPages}
                    className="px-3 py-1 text-xs rounded border border-gray-600 text-gray-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-700 transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {/* Additional Info */}
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Additional Information
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {fundamentalData.LatestQuarter && (
            <div>
              <p className="text-sm text-gray-400 mb-1">Latest Quarter</p>
              <p className="text-white font-semibold">{formatDate(fundamentalData.LatestQuarter)}</p>
            </div>
          )}
          {fundamentalData.FiscalYearEnd && (
            <div>
              <p className="text-sm text-gray-400 mb-1">Fiscal Year End</p>
              <p className="text-white font-semibold">{fundamentalData.FiscalYearEnd}</p>
            </div>
          )}
          {fundamentalData.CIK && (
            <div>
              <p className="text-sm text-gray-400 mb-1">CIK</p>
              <p className="text-white font-semibold">{fundamentalData.CIK}</p>
            </div>
          )}
          {fundamentalData.OfficialSite && (
            <div className="md:col-span-2 lg:col-span-3">
              <p className="text-sm text-gray-400 mb-1">Official Website</p>
              <a
                href={fundamentalData.OfficialSite}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 font-semibold"
              >
                {fundamentalData.OfficialSite}
              </a>
            </div>
          )}
          {fundamentalData.Address && (
            <div className="md:col-span-2 lg:col-span-3">
              <p className="text-sm text-gray-400 mb-1">Address</p>
              <p className="text-white font-semibold">{fundamentalData.Address}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default FundamentalPanes;
