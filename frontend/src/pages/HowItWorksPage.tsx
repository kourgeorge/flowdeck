import { Link } from 'react-router-dom';

export default function HowItWorksPage() {
  return (
    <div className="min-h-screen p-8">
      <div className="max-w-3xl mx-auto text-gray-300">
        <Link
          to="/"
          className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors mb-8"
        >
          ← Back to Flowdeck
        </Link>

        <h1 className="text-3xl font-bold text-white mb-2">How Flowdeck Works</h1>
        <p className="text-gray-500 text-sm mb-10">
          How we use AI to produce insights and recommendations you see on your stock pages.
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
              The recommendation and all the report text are produced by our analysis engine. They are not simple price alerts or single-model outputs—they come from a structured process where several AI “perspectives” gather information, debate the case for and against the investment, and then pass through a risk check before we show you a final view. Below we explain how that process works so you can interpret the insights with confidence.
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
              Our analysis does not rely on a single “black box.” It follows a clear sequence: specialized analysts write reports, then bull and bear views debate, then a research manager and a trader perspective shape the plan, and finally a risk debate produces the recommendation you see. Here is that flow in plain terms.
            </p>

            <h3 className="text-base font-medium text-white mt-4 mb-2">Step 1 — Specialized analysts</h3>
            <p className="mb-2">
              First, several <strong className="text-white">specialist analysts</strong> work one after another. Each focuses on a different angle—for example market context (price action, volume, trends), news (headlines and narratives), and fundamentals (financials and valuation). Each analyst uses the underlying data to write a short report and a score. So you get distinct views on “what the market is doing,” “what the news is saying,” and “what the numbers show,” instead of one blended answer. These reports are the building blocks for everything that follows.
            </p>

            <h3 className="text-base font-medium text-white mt-4 mb-2">Step 2 — Bull vs. bear debate</h3>
            <p className="mb-2">
              Next, two research perspectives—a <strong className="text-white">bull</strong> (focused on reasons to be positive) and a <strong className="text-white">bear</strong> (focused on risks and reasons to be cautious)—take turns arguing. They use all the analyst reports and build on each other’s points over several rounds. The goal is to stress-test the idea: what could go right, and what could go wrong? This debate is designed to mimic how a thoughtful investor might weigh both sides before deciding.
            </p>

            <h3 className="text-base font-medium text-white mt-4 mb-2">Step 3 — Research manager and trader view</h3>
            <p className="mb-2">
              After the debate, a <strong className="text-white">research manager</strong> step weighs the bull and bear arguments and produces an <strong className="text-white">investment plan</strong>: a summary view, a recommendation score (e.g. 1–10), and where relevant an idea of expected return and downside. Then a <strong className="text-white">trader</strong> perspective turns that into a concrete stance—how to act on the plan given real-world execution and risk. So by this point the AI has moved from “raw reports” to “plan” to “actionable view.”
            </p>

            <h3 className="text-base font-medium text-white mt-4 mb-2">Step 4 — Risk debate and final recommendation</h3>
            <p className="mb-2">
              Before we show you a recommendation, the system runs a <strong className="text-white">risk debate</strong>. Three angles—more aggressive (emphasizing upside), more cautious (emphasizing downside), and neutral—discuss how much risk the investment carries and whether the plan is appropriate. A final <strong className="text-white">risk judge</strong> considers this discussion and decides the outcome. Only then does the system produce the final recommendation you see: <strong className="text-white">BUY</strong>, <strong className="text-white">SELL</strong>, or <strong className="text-white">HOLD</strong>. So the BUY/SELL/HOLD is not the first answer the AI had—it is the result of analysts, debate, plan, and risk check.
            </p>

            <p className="mt-3">
              In short: the AI first gathers and structures information (analyst reports), then challenges it (bull vs. bear), then turns it into a plan and a trader view, and finally subjects it to a risk discussion before committing to BUY, SELL, or HOLD. That is the flow behind every insight you see on Flowdeck.
            </p>
          </section>

          {/* What you see in the app */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">What You See in the App</h2>
            <p className="mb-3">
              On the <strong className="text-white">homepage</strong>, stock widgets show live prices and, when an analysis exists for that stock and date, the AI recommendation (BUY/SELL/HOLD). When you open a <strong className="text-white">stock page</strong>, you see the current quote and key stats, a prominent recommendation banner, and a set of <strong className="text-white">report tabs</strong>—Market, News, Fundamentals, Technical, Sentiment, and Investment Plan. Each tab corresponds to one of the building blocks from the analysis (e.g. the market analyst’s report, the news report, the investment plan from the research manager). You can read the full reasoning, not just the final label.
            </p>
            <p className="mb-3">
              If there is no analysis yet for the stock and date you have selected, you will see an option to <strong className="text-white">generate a report</strong>. Starting a report kicks off the full process above; it can take a few minutes. Once it finishes, the new recommendation and all report tabs will appear, and you can also come back later to see past analyses by changing the date when we have more than one.
            </p>
            <p>
              Prices and quote data update with the market. The recommendation and report text stay fixed for the analysis date they were generated for—so you always know exactly which “snapshot” of information the AI used. If you want a fresh view, you can generate a new report for today or another date.
            </p>
          </section>

          {/* Summary for the investor */}
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">In a Nutshell</h2>
            <p>
              Flowdeck gives you AI-powered stock insights by (1) pulling in live market data, news, and fundamentals, (2) running that information through specialized analysts and a structured bull/bear and risk debate, and (3) showing you a clear BUY/SELL/HOLD plus detailed reports so you can see how the AI got there. The flow is designed to be transparent and multi-step—so you get a reasonable, in-depth explanation of how the AI processes information and arrives at the recommendation you see.
            </p>
          </section>
        </div>

        <div className="mt-12 pt-8 border-t border-gray-700 flex flex-wrap gap-6">
          <Link
            to="/"
            className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors"
          >
            ← Back to Flowdeck
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
