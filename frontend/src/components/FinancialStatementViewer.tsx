import { useState, useEffect } from 'react';
import React from 'react';

interface FinancialStatementViewerProps {
  data: {
    format: 'json' | 'text' | 'error';
    data: any;
  };
  statementType: 'cashflow' | 'balance_sheet' | 'income_statement';
}

// Format large numbers for display
const formatNumber = (value: string | number | null | undefined): string => {
  if (value === null || value === undefined || value === 'None' || value === '') {
    return 'N/A';
  }
  
  // Convert string to number if needed
  let num: number;
  if (typeof value === 'string') {
    // Remove any commas
    const cleanValue = value.replace(/,/g, '');
    if (cleanValue === 'None' || cleanValue === '') {
      return 'N/A';
    }
    num = parseFloat(cleanValue);
    if (isNaN(num)) {
      return value; // Return original if not a number
    }
  } else {
    num = value;
  }
  
  const absNum = Math.abs(num);
  const sign = num < 0 ? '-' : '';
  
  if (absNum >= 1e12) {
    return `${sign}$${(absNum / 1e12).toFixed(2)}T`;
  } else if (absNum >= 1e9) {
    return `${sign}$${(absNum / 1e9).toFixed(2)}B`;
  } else if (absNum >= 1e6) {
    return `${sign}$${(absNum / 1e6).toFixed(2)}M`;
  } else if (absNum >= 1e3) {
    return `${sign}$${(absNum / 1e3).toFixed(2)}K`;
  } else {
    return `${sign}$${absNum.toFixed(2)}`;
  }
};

// Human-readable field names
const fieldLabels: Record<string, string> = {
  fiscalDateEnding: 'Fiscal Date Ending',
  reportedCurrency: 'Currency',
  // Cash Flow fields
  operatingCashflow: 'Operating Cash Flow',
  paymentsForOperatingActivities: 'Payments for Operating Activities',
  proceedsFromOperatingActivities: 'Proceeds from Operating Activities',
  changeInOperatingLiabilities: 'Change in Operating Liabilities',
  changeInOperatingAssets: 'Change in Operating Assets',
  depreciationDepletionAndAmortization: 'Depreciation, Depletion & Amortization',
  capitalExpenditures: 'Capital Expenditures',
  changeInReceivables: 'Change in Receivables',
  changeInInventory: 'Change in Inventory',
  profitLoss: 'Profit/Loss',
  cashflowFromInvestment: 'Cash Flow from Investment',
  cashflowFromFinancing: 'Cash Flow from Financing',
  proceedsFromRepaymentsOfShortTermDebt: 'Proceeds from Repayments of Short Term Debt',
  paymentsForRepurchaseOfCommonStock: 'Payments for Repurchase of Common Stock',
  paymentsForRepurchaseOfEquity: 'Payments for Repurchase of Equity',
  paymentsForRepurchaseOfPreferredStock: 'Payments for Repurchase of Preferred Stock',
  dividendPayout: 'Dividend Payout',
  dividendPayoutCommonStock: 'Dividend Payout (Common Stock)',
  dividendPayoutPreferredStock: 'Dividend Payout (Preferred Stock)',
  proceedsFromIssuanceOfCommonStock: 'Proceeds from Issuance of Common Stock',
  proceedsFromIssuanceOfLongTermDebtAndCapitalSecuritiesNet: 'Proceeds from Issuance of Long Term Debt',
  proceedsFromIssuanceOfPreferredStock: 'Proceeds from Issuance of Preferred Stock',
  proceedsFromRepurchaseOfEquity: 'Proceeds from Repurchase of Equity',
  proceedsFromSaleOfTreasuryStock: 'Proceeds from Sale of Treasury Stock',
  changeInCashAndCashEquivalents: 'Change in Cash and Cash Equivalents',
  changeInExchangeRate: 'Change in Exchange Rate',
  netIncome: 'Net Income',
  // Balance Sheet - Assets
  cashAndCashEquivalentsAtCarryingValue: 'Cash and Cash Equivalents',
  cashAndShortTermInvestments: 'Cash and Short Term Investments',
  inventory: 'Inventory',
  currentNetReceivables: 'Current Net Receivables',
  totalAssets: 'Total Assets',
  totalCurrentAssets: 'Total Current Assets',
  propertyPlantEquipment: 'Property, Plant & Equipment',
  accumulatedDepreciationAmortizationPPE: 'Accumulated Depreciation (PPE)',
  intangibleAssets: 'Intangible Assets',
  intangibleAssetsExcludingGoodwill: 'Intangible Assets (Excluding Goodwill)',
  goodwill: 'Goodwill',
  investments: 'Investments',
  longTermInvestments: 'Long Term Investments',
  shortTermInvestments: 'Short Term Investments',
  otherCurrentAssets: 'Other Current Assets',
  otherNonCurrentAssets: 'Other Non-Current Assets',
  otherAssets: 'Other Assets',
  nonCurrentAssets: 'Non-Current Assets',
  // Balance Sheet - Liabilities
  totalLiabilities: 'Total Liabilities',
  totalCurrentLiabilities: 'Total Current Liabilities',
  currentAccountsPayable: 'Current Accounts Payable',
  deferredRevenue: 'Deferred Revenue',
  currentDebt: 'Current Debt',
  shortTermDebt: 'Short Term Debt',
  capitalLeaseObligations: 'Capital Lease Obligations',
  longTermDebt: 'Long Term Debt',
  longTermDebtNoncurrent: 'Long Term Debt (Non-Current)',
  currentLongTermDebt: 'Current Long Term Debt',
  longTermDebtAndCapitalLeaseObligation: 'Long Term Debt & Capital Lease Obligations',
  otherCurrentLiabilities: 'Other Current Liabilities',
  otherNonCurrentLiabilities: 'Other Non-Current Liabilities',
  otherLiabilities: 'Other Liabilities',
  nonCurrentLiabilities: 'Non-Current Liabilities',
  // Balance Sheet - Equity
  totalShareholderEquity: 'Total Shareholder Equity',
  commonStock: 'Common Stock',
  retainedEarnings: 'Retained Earnings',
  accumulatedOtherComprehensiveIncomeLoss: 'Accumulated Other Comprehensive Income (Loss)',
  otherEquity: 'Other Equity',
  treasuryStock: 'Treasury Stock',
  preferredStock: 'Preferred Stock',
  commonStockSharesOutstanding: 'Common Stock Shares Outstanding',
  // Balance Sheet - Other
  totalLiabilitiesAndTotalEquity: 'Total Liabilities and Equity',
  totalInvestments: 'Total Investments',
  totalDebt: 'Total Debt',
  netDebt: 'Net Debt',
};

// Key fields to display for cashflow (in order)
const cashflowKeyFields = [
  'fiscalDateEnding',
  'operatingCashflow',
  'netIncome',
  'depreciationDepletionAndAmortization',
  'changeInReceivables',
  'changeInInventory',
  'capitalExpenditures',
  'cashflowFromInvestment',
  'cashflowFromFinancing',
  'dividendPayout',
  'proceedsFromRepurchaseOfEquity',
  'changeInCashAndCashEquivalents',
];

// Key fields for balance sheet (ordered logically: Assets, Liabilities, Equity)
const balanceSheetKeyFields = [
  // Assets Section
  'cashAndCashEquivalentsAtCarryingValue',
  'cashAndShortTermInvestments',
  'shortTermInvestments',
  'currentNetReceivables',
  'inventory',
  'otherCurrentAssets',
  'totalCurrentAssets',
  'propertyPlantEquipment',
  'accumulatedDepreciationAmortizationPPE',
  'longTermInvestments',
  'investments',
  'goodwill',
  'intangibleAssets',
  'intangibleAssetsExcludingGoodwill',
  'otherNonCurrentAssets',
  'otherAssets',
  'nonCurrentAssets',
  'totalAssets',
  // Liabilities Section
  'currentAccountsPayable',
  'shortTermDebt',
  'currentDebt',
  'currentLongTermDebt',
  'deferredRevenue',
  'otherCurrentLiabilities',
  'totalCurrentLiabilities',
  'longTermDebt',
  'longTermDebtNoncurrent',
  'longTermDebtAndCapitalLeaseObligation',
  'capitalLeaseObligations',
  'otherNonCurrentLiabilities',
  'otherLiabilities',
  'nonCurrentLiabilities',
  'totalLiabilities',
  // Equity Section
  'commonStock',
  'preferredStock',
  'retainedEarnings',
  'accumulatedOtherComprehensiveIncomeLoss',
  'treasuryStock',
  'otherEquity',
  'totalShareholderEquity',
  // Total
  'totalLiabilitiesAndTotalEquity',
  'commonStockSharesOutstanding',
  'totalDebt',
  'netDebt',
];

export default function FinancialStatementViewer({ data, statementType }: FinancialStatementViewerProps) {
  const [selectedPeriod, setSelectedPeriod] = useState<'quarterly' | 'annual'>('quarterly');
  const [isInitialized, setIsInitialized] = useState(false);
  
  // Auto-select period based on available data (only on initial load)
  useEffect(() => {
    if (data.format === 'json' && !isInitialized) {
      const jsonData = data.data;
      const hasQuarterly = jsonData.quarterlyReports && jsonData.quarterlyReports.length > 0;
      const hasAnnual = jsonData.annualReports && jsonData.annualReports.length > 0;
      
      // Prefer quarterly if available, otherwise annual
      if (hasQuarterly) {
        setSelectedPeriod('quarterly');
      } else if (hasAnnual) {
        setSelectedPeriod('annual');
      }
      setIsInitialized(true);
    }
  }, [data, isInitialized]);

  if (data.format === 'error') {
    return (
      <div className="bg-red-500/10 border border-red-500 rounded-lg p-4">
        <p className="text-red-400">Error loading data: {data.data}</p>
      </div>
    );
  }

  if (data.format === 'text') {
    // Try to parse as CSV and display as table
    const textData = data.data;
    const lines = textData.split('\n').filter((line: string) => line.trim());
    
    // Check if it looks like CSV (has commas)
    if (lines.length > 0 && lines[0].includes(',')) {
      const headers = lines[0].split(',').map((h: string) => h.trim().replace(/"/g, ''));
      const rows = lines.slice(1).map((line: string) => {
        const values = line.split(',').map((v: string) => v.trim().replace(/"/g, ''));
        return values;
      });
      
      return (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white capitalize">
              {statementType.replace('_', ' ')} Statement
            </h3>
          </div>
          <div className="overflow-x-auto rounded-lg border border-gray-700">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-900/50 border-b-2 border-gray-700">
                  {headers.map((header: string, idx: number) => (
                    <th
                      key={idx}
                      className={`py-4 px-6 text-sm font-bold text-gray-200 ${
                        idx === 0 
                          ? 'text-left sticky left-0 bg-gray-900/50 z-20 border-r border-gray-700' 
                          : 'text-right min-w-[140px]'
                      }`}
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row: string[], rowIdx: number) => {
                  const isTotalRow = row[0]?.toLowerCase().includes('total');
                  return (
                    <tr
                      key={rowIdx}
                      className={`border-b border-gray-700/50 transition-colors hover:bg-gray-750/30 ${
                        isTotalRow 
                          ? 'bg-blue-900/20 border-t-2 border-b-2 border-blue-700/50' 
                          : rowIdx % 2 === 0 
                            ? 'bg-gray-800/80' 
                            : 'bg-gray-800/40'
                      }`}
                    >
                      {row.map((cell: string, cellIdx: number) => {
                        const isEmpty = !cell || cell === 'None' || cell === '';
                        const isNumeric = cellIdx > 0 && !isEmpty && !isNaN(parseFloat(cell.replace(/,/g, '')));
                        const formattedValue = isNumeric ? formatNumber(cell) : cell;
                        
                        return (
                          <td
                            key={cellIdx}
                            className={`py-3 px-6 text-sm ${
                              cellIdx === 0
                                ? 'text-left sticky left-0 z-10 border-r border-gray-700/50 bg-inherit font-medium text-gray-200'
                                : 'text-right text-gray-100'
                            } ${
                              isTotalRow && cellIdx === 0
                                ? 'font-bold text-blue-300'
                                : ''
                            } ${
                              isTotalRow && cellIdx > 0
                                ? 'font-bold text-blue-300'
                                : ''
                            } ${isEmpty ? 'text-gray-500' : ''}`}
                          >
                            {cellIdx === 0 && isTotalRow && (
                              <span className="mr-2 text-blue-400">▸</span>
                            )}
                            {formattedValue}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      );
    }
    
    // Fallback to plain text display
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-white mb-4 capitalize">
          {statementType.replace('_', ' ')}
        </h3>
        <div className="text-gray-300 whitespace-pre-wrap font-mono text-sm bg-gray-900 p-4 rounded border border-gray-700 overflow-x-auto">
          {data.data}
        </div>
      </div>
    );
  }

  // JSON format (Alpha Vantage)
  const jsonData = data.data;
  const hasAnnual = jsonData.annualReports && jsonData.annualReports.length > 0;
  const hasQuarterly = jsonData.quarterlyReports && jsonData.quarterlyReports.length > 0;

  if (!hasAnnual && !hasQuarterly) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <p className="text-gray-400">No data available</p>
      </div>
    );
  }

  // Determine which reports to show
  let reports: any[] = [];
  if (selectedPeriod === 'quarterly' && hasQuarterly) {
    reports = jsonData.quarterlyReports;
  } else if (selectedPeriod === 'annual' && hasAnnual) {
    reports = jsonData.annualReports;
  } else if (hasQuarterly) {
    reports = jsonData.quarterlyReports;
  } else if (hasAnnual) {
    reports = jsonData.annualReports;
  }

  if (reports.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <p className="text-gray-400">No {selectedPeriod} data available</p>
      </div>
    );
  }

  // Get all unique fields from all reports (excluding fiscalDateEnding and reportedCurrency)
  const allFields = new Set<string>();
  reports.forEach((report) => {
    Object.keys(report).forEach((key) => {
      if (key !== 'fiscalDateEnding' && key !== 'reportedCurrency') {
        allFields.add(key);
      }
    });
  });

  // Determine fields to show based on statement type
  let fieldsToShow: string[] = [];
  if (statementType === 'cashflow') {
    fieldsToShow = [
      ...cashflowKeyFields.filter(f => allFields.has(f)),
      ...Array.from(allFields).filter(f => !cashflowKeyFields.includes(f))
    ];
  } else if (statementType === 'balance_sheet') {
    // For balance sheet, use ordered key fields first, then remaining fields
    fieldsToShow = [
      ...balanceSheetKeyFields.filter(f => allFields.has(f)),
      ...Array.from(allFields).filter(f => !balanceSheetKeyFields.includes(f))
    ];
  } else {
    fieldsToShow = Array.from(allFields);
  }

  // Get section name for balance sheet
  const getBalanceSheetSection = (field: string): string | null => {
    if (statementType !== 'balance_sheet') return null;
    
    const fieldIndex = balanceSheetKeyFields.indexOf(field);
    if (fieldIndex === -1) return null;
    
    const assetsEnd = balanceSheetKeyFields.indexOf('totalAssets');
    const liabilitiesEnd = balanceSheetKeyFields.indexOf('totalLiabilities');
    
    if (fieldIndex <= assetsEnd) return 'Assets';
    if (fieldIndex <= liabilitiesEnd) return 'Liabilities';
    return 'Equity';
  };

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white capitalize">
          {statementType.replace('_', ' ')} Statement
        </h3>
        {(hasAnnual && hasQuarterly) && (
          <div className="flex gap-2">
            <button
              onClick={() => setSelectedPeriod('quarterly')}
              className={`px-4 py-2 text-sm font-medium rounded transition-colors ${
                selectedPeriod === 'quarterly'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              Quarterly
            </button>
            <button
              onClick={() => setSelectedPeriod('annual')}
              className={`px-4 py-2 text-sm font-medium rounded transition-colors ${
                selectedPeriod === 'annual'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              Annual
            </button>
          </div>
        )}
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-700">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-900/50 border-b-2 border-gray-700">
              <th className="text-left py-4 px-6 text-sm font-bold text-gray-200 sticky left-0 bg-gray-900/50 z-20 border-r border-gray-700">
                {statementType === 'balance_sheet' ? 'Balance Sheet Item' : 'Item'}
              </th>
              {reports.map((report, idx) => (
                <th
                  key={idx}
                  className="text-right py-4 px-6 text-sm font-bold text-gray-200 min-w-[140px] bg-gray-900/50"
                >
                  <div className="flex flex-col">
                    <span>{report.fiscalDateEnding || 'N/A'}</span>
                    {report.reportedCurrency && (
                      <span className="text-xs font-normal text-gray-400 mt-1">
                        {report.reportedCurrency}
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {fieldsToShow.map((field, fieldIdx) => {
              const label = fieldLabels[field] || field.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase());
              const section = getBalanceSheetSection(field);
              const isTotalRow = field.toLowerCase().includes('total') && 
                                (field === 'totalAssets' || field === 'totalCurrentAssets' || 
                                 field === 'totalLiabilities' || field === 'totalCurrentLiabilities' ||
                                 field === 'totalShareholderEquity' || field === 'totalLiabilitiesAndTotalEquity');
              
              // Check if previous field was in a different section
              const prevField = fieldIdx > 0 ? fieldsToShow[fieldIdx - 1] : null;
              const prevSection = prevField ? getBalanceSheetSection(prevField) : null;
              const showSectionDivider = section && prevSection && section !== prevSection;
              
              return (
                <React.Fragment key={field}>
                  {showSectionDivider && (
                    <tr>
                      <td
                        colSpan={reports.length + 1}
                        className="py-3 px-6 bg-gray-900/70 border-t-2 border-b border-gray-600"
                      >
                        <div className="text-base font-bold text-white uppercase tracking-wide">
                          {section}
                        </div>
                      </td>
                    </tr>
                  )}
                  <tr
                    className={`border-b border-gray-700/50 transition-colors hover:bg-gray-750/30 ${
                      isTotalRow 
                        ? 'bg-blue-900/20 border-t-2 border-b-2 border-blue-700/50' 
                        : fieldIdx % 2 === 0 
                          ? 'bg-gray-800/80' 
                          : 'bg-gray-800/40'
                    }`}
                  >
                    <td className={`py-3 px-6 text-sm sticky left-0 z-10 border-r border-gray-700/50 bg-inherit ${
                      isTotalRow 
                        ? 'font-bold text-blue-300' 
                        : 'font-medium text-gray-200'
                    }`}>
                      <div className="flex items-center">
                        {isTotalRow && (
                          <span className="mr-2 text-blue-400">▸</span>
                        )}
                        <span className={isTotalRow ? 'font-bold' : ''}>{label}</span>
                      </div>
                    </td>
                    {reports.map((report, reportIdx) => {
                      const value = report[field];
                      const formattedValue = formatNumber(value);
                      const isEmpty = formattedValue === 'N/A' || formattedValue === '';
                      
                      return (
                        <td
                          key={reportIdx}
                          className={`py-3 px-6 text-sm text-right ${
                            isTotalRow 
                              ? 'font-bold text-blue-300' 
                              : 'text-gray-100'
                          } ${isEmpty ? 'text-gray-500' : ''}`}
                        >
                          {formattedValue}
                        </td>
                      );
                    })}
                  </tr>
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

