declare module "yahoo-finance2" {
  interface YahooFinanceInstance {
    quote(symbol: string): Promise<Record<string, unknown>>;
  }
  const defaultExport: new (options?: unknown) => YahooFinanceInstance;
  export default defaultExport;
}
