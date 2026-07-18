import { Link } from 'react-router-dom';
import { COPILOT_NAME } from '../config';

export default function HowItWorksPage() {
  return (
    <div className="min-h-screen p-8">
      <div className="text-gray-300">
        <h1 className="text-3xl font-bold text-white mb-2">How Flowdeck Works</h1>
        <p className="text-gray-500 text-sm mb-10">
          How we use AI to produce insights and recommendations you see on your stock pages — and how {COPILOT_NAME} (your Trading Copilot) and the AI Analyst Agent help you dig deeper.
        </p>
        <div className="mb-10">
          <Link
            to="/architecture"
            className="inline-flex items-center rounded-md border border-gray-600 px-3 py-2 text-sm text-gray-300 hover:text-white hover:border-gray-400 transition-colors"
          >
            View Full Architecture Schematic
          </Link>
        </div>

        <div className="space-y-10 text-sm leading-relaxed">
          {/* What Flowdeck gives you */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">What You Get</h2>
            <p className="mb-3">
              Flowdeck brings together <strong className="text-white">live market data</strong>—prices, volume, and key ranges—with <strong className="text-white">AI-generated analysis</strong> for each stock. On the homepage you see at a glance how major stocks are doing and, when an analysis exists, whether our AI suggests BUY, SELL, or HOLD. When you open a stock, you get a full picture: current quote, detailed reports (market context, news, fundamentals, technicals, sentiment, and an investment plan), and a clear recommendation.
            </p>
            <p>
              The recommendation and all the report text are produced by our analysis engine. They are not simple price alerts or single-model outputs—they come from a structured process where several AI "perspectives" gather information, debate the case for and against the investment, and then pass through a risk check before we show you a final view. Below we explain how that process works so you can interpret the insights with confidence.
            </p>
          </section>

          {/* What information we use */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">What Information the AI Uses</h2>
            <p className="mb-3">
              Before any analysis runs, our system collects the same kinds of information an analyst would: <strong className="text-white">market data</strong> (current price, recent price history, volume, and ranges), <strong className="text-white">news</strong> about the company and its sector, <strong className="text-white">company and fundamental data</strong> (business description, financial statements, key ratios), and when relevant <strong className="text-white">technical indicators</strong> and broader <strong className="text-white">sentiment</strong>. This data comes from established market data providers. We do not train our AI on your personal data; we use it only to analyze the stock for the date you choose.
            </p>
            <p>
              So when you request an analysis for a ticker and a given date, the AI is working with up-to-date prices, recent news, and the latest fundamentals we can fetch for that moment. That way the reports and the BUY/SELL/HOLD view reflect the information available as of that date.
            </p>
          </section>

          {/* How the AI processes it - step by step */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">How the AI Processes Information: The Full Flow</h2>
            <p className="mb-4">
              Our analysis does not rely on a single "black box." It follows a clear sequence: specialized analysts write reports, then bull, bear, and neutral views debate, then a research manager weighs all sides and commits to the recommendation, and a trader perspective turns it into a concrete plan. Here is that flow in plain terms.
            </p>

            <h3 className="text-base font-medium text-white mt-4 mb-2">Step 1 — Specialized analysts</h3>
            <p className="mb-2">
              First, several <strong className="text-white">specialist analysts</strong> work one after another. Each focuses on a different angle—for example market context (price action, volume, trends), news (headlines and narratives), and fundamentals (financials and valuation). Each analyst uses the underlying data to write a short report and a score. So you get distinct views on "what the market is doing," "what the news is saying," and "what the numbers show," instead of one blended answer. These reports are the building blocks for everything that follows.
            </p>

            <h3 className="text-base font-medium text-white mt-4 mb-2">Step 2 — Bull / bear / neutral debate</h3>
            <p className="mb-2">
              Next, three research perspectives—a <strong className="text-white">bull</strong> (reasons to be positive), a <strong className="text-white">bear</strong> (risks and reasons to be cautious), and a <strong className="text-white">neutral</strong> voice (a balanced take that challenges both sides)—take turns arguing. They use all the analyst reports and build on each other's points over several rounds. The goal is to stress-test the idea: what could go right, what could go wrong, and where the truth most likely sits. This debate is designed to mimic how a thoughtful investor weighs every side before deciding.
            </p>

            <h3 className="text-base font-medium text-white mt-4 mb-2">Step 3 — Research manager decides</h3>
            <p className="mb-2">
              After the debate, a <strong className="text-white">research manager</strong> weighs the bull, bear, and neutral arguments and produces the <strong className="text-white">investment plan</strong>: a summary view, the final recommendation—<strong className="text-white">BUY</strong>, <strong className="text-white">SELL</strong>, or <strong className="text-white">HOLD</strong>—a conviction score (1–5) reflecting how strongly the debate supports that direction, and where relevant an idea of expected return and downside. This is the authoritative call you see in the app: the BUY/SELL/HOLD is not the first answer the AI had—it is the result of analysts weighing evidence and debating every side.
            </p>

            <h3 className="text-base font-medium text-white mt-4 mb-2">Step 4 — Trader plan and TPS</h3>
            <p className="mb-2">
              Finally, a <strong className="text-white">trader</strong> perspective turns the recommendation into a concrete, actionable stance given real-world execution and risk. As part of this step the system produces a <strong className="text-white">TPS (Trading Plan Specification)</strong> — a compact, structured JSON object that encodes the trade unambiguously: instrument, direction, entry zone, stop-loss, risk limit, and optional execution rules. You can find it in the <strong className="text-white">Trader tab</strong> of any AI Analysis report. <Link to="/how-it-works/tps" className="text-indigo-400 hover:text-indigo-300 underline underline-offset-2">Learn more about TPS →</Link>
            </p>

            <p className="mt-3">
              In short: the AI first gathers and structures information (analyst reports), then challenges it from three sides (bull / bear / neutral), then the research manager weighs the debate and commits to BUY, SELL, or HOLD, and finally a trader view turns that into an executable plan. That is the flow behind every insight you see on Flowdeck.
            </p>
          </section>

          {/* What you see in the app */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">What You See in the App</h2>
            <p className="mb-3">
              On the <strong className="text-white">homepage</strong>, stock widgets show live prices and, when an analysis exists for that stock and date, the AI recommendation (BUY/SELL/HOLD). When you open a <strong className="text-white">stock page</strong>, you see the current quote and key stats, a prominent recommendation banner, and a set of <strong className="text-white">report tabs</strong>—Market, News, Fundamentals, Technical, Sentiment, and Investment Plan. Each tab corresponds to one of the building blocks from the analysis (e.g. the market analyst's report, the news report, the investment plan from the research manager). You can read the full reasoning, not just the final label.
            </p>
            <p className="mb-3">
              If there is no analysis yet for the stock and date you have selected, you will see an option to <strong className="text-white">generate a report</strong>. Starting a report kicks off the full process above; it can take a few minutes. Once it finishes, the new recommendation and all report tabs will appear, and you can also come back later to see past analyses by changing the date when we have more than one.
            </p>
            <p>
              Prices and quote data update with the market. The recommendation and report text stay fixed for the analysis date they were generated for—so you always know exactly which "snapshot" of information the AI used. If you want a fresh view, you can generate a new report for today or another date.
            </p>
          </section>

          {/* Trading Copilot — {COPILOT_NAME} */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">{COPILOT_NAME} — Your Trading Copilot</h2>
            <p className="mb-3">
              <strong className="text-white">{COPILOT_NAME}</strong> (<Link to="/copilot" className="text-blue-400 hover:text-blue-300 underline underline-offset-2">/copilot</Link>) is your Trading Copilot — a three-panel workspace designed for active research. Instead of switching between tabs, you get everything in one view:
            </p>
            <ul className="list-disc list-inside space-y-1.5 mb-3 text-gray-300">
              <li><strong className="text-white">Left panel</strong> — your watchlist. Add any ticker with the search box; click to select it as your focus stock.</li>
              <li><strong className="text-white">Middle panel</strong> — full stock detail for the selected ticker: live quote, AI recommendation, all report tabs, fundamentals, news, and insider activity.</li>
              <li><strong className="text-white">Right panel</strong> — the {COPILOT_NAME} AI chat, pre-loaded with context about the selected ticker and your entire watchlist.</li>
            </ul>
            <p className="mb-3">
              The chat panel is context-aware. When you select a ticker, the AI automatically knows which stock you are looking at. You can ask <em>"What are the key risks here?"</em> or <em>"Summarize the latest report"</em> without specifying the ticker — the AI already knows. You can also ask cross-ticker questions like <em>"Compare NVDA and AMD fundamentals"</em> or <em>"Which of my watchlist stocks has the best recommendation right now?"</em>
            </p>
            <p>
              Each message in the {COPILOT_NAME} chat shows which data tools were accessed (e.g. Stock Quote, AI Reports, Fundamentals, Technical Indicators) and how many tokens were consumed, so you always know what information the AI used to form its answer.
            </p>
          </section>

          {/* AI Analyst Agent */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">The AI Analyst Agent</h2>
            <p className="mb-3">
              The standalone <strong className="text-white">AI Analyst Agent</strong> (<Link to="/chat" className="text-blue-400 hover:text-blue-300 underline underline-offset-2">/chat</Link>) gives you a full-page conversational interface for deep-dive research. It has live access to the same data sources as the {COPILOT_NAME} chat:
            </p>
            <ul className="list-disc list-inside space-y-1.5 mb-3 text-gray-300">
              <li>Live stock quotes and historical price data</li>
              <li>AI-generated reports and BUY/SELL/HOLD recommendations from Flowdeck's analysis engine</li>
              <li>Fundamentals: balance sheet, cash flow, income statement, key ratios</li>
              <li>Technical indicators (RSI, MACD, moving averages, and more)</li>
              <li>Insider transactions and insider sentiment</li>
              <li>Company news and global market news</li>
              <li>Your watchlist and portfolio context</li>
            </ul>
            <p className="mb-3">
              Responses stream token-by-token as the AI reasons through your question. You can see exactly which tools were called and how many tokens each message consumed. The AI Analyst is best for open-ended research: <em>"Walk me through the bull and bear case for TSLA"</em>, <em>"What does the technical picture look like for AAPL right now?"</em>, or <em>"Summarize the key themes across my watchlist this week."</em>
            </p>
            <p>
              Both the {COPILOT_NAME} chat and the AI Analyst Agent use tokens from your balance. Each message deducts tokens based on the complexity of the query and the number of data tools accessed. New users receive <strong className="text-white">1,000 free tokens</strong> on sign-up.
            </p>
          </section>

          {/* Summary for the investor */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">In a Nutshell</h2>
            <p>
              Flowdeck gives you AI-powered stock insights by (1) pulling in live market data, news, and fundamentals, (2) running that information through specialized analysts and a structured bull / bear / neutral debate judged by a research manager, and (3) showing you a clear BUY/SELL/HOLD plus detailed reports so you can see how the AI got there. <strong className="text-white">{COPILOT_NAME}</strong>, your Trading Copilot, lets you research and chat side by side, while the <strong className="text-white">AI Analyst Agent</strong> is available for deeper, open-ended conversations. The flow is designed to be transparent and multi-step — so you get a reasonable, in-depth explanation of how the AI processes information and arrives at the recommendation you see.
            </p>
          </section>
        </div>

        <div className="mt-12 pt-8 border-t border-gray-700 flex flex-wrap gap-6">
          <Link
            to="/copilot"
            className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors"
          >
            {COPILOT_NAME} →
          </Link>
          <Link
            to="/chat"
            className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors"
          >
            AI Analyst Agent →
          </Link>
          <Link
            to="/how-it-works/tps"
            className="inline-flex items-center text-sm text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            TPS Trading Plan Spec →
          </Link>
          <Link
            to="/terms"
            className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors"
          >
            Terms of Use →
          </Link>
          <Link
            to="/contact"
            className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors"
          >
            Contact →
          </Link>
          <Link
            to="/architecture"
            className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors"
          >
            Architecture →
          </Link>
        </div>
      </div>
    </div>
  );
}

// Made with Bob
