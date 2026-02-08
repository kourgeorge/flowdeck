import { Link } from 'react-router-dom';

export default function TermsOfUsePage() {
  const effectiveDate = '2025-02-06';

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-3xl mx-auto text-gray-300">
        <Link
          to="/"
          className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors mb-8"
        >
          ← Back to Flowdeck
        </Link>

        <h1 className="text-3xl font-bold text-white mb-2">Terms of Use</h1>
        <p className="text-gray-500 text-sm mb-10">Effective date: {effectiveDate}</p>

        <div className="space-y-8 text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">1. Agreement to Terms</h2>
            <p>
              These Terms of Use (“Terms”) constitute a legally binding agreement between you (“User,” “you,” or “your”) and Flowdeck (“we,” “us,” or “our”) governing your access to and use of the Flowdeck website, applications, and any related services (collectively, the “Service”). By accessing or using the Service, you acknowledge that you have read, understood, and agree to be bound by these Terms. If you do not agree to these Terms, you must not access or use the Service.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">2. Not Financial, Investment, or Trading Advice</h2>
            <p className="mb-3">
              <strong className="text-white">THE SERVICE IS FOR INFORMATIONAL AND EDUCATIONAL PURPOSES ONLY.</strong> Nothing on the Service constitutes, or is intended to constitute, financial advice, investment advice, trading advice, or a recommendation or solicitation to buy, sell, or hold any security, financial product, or instrument. All content, data, analysis, reports, recommendations, and outputs (including any BUY/SELL/HOLD or similar indicators) are provided solely for general information and must not be relied upon for any investment or trading decision.
            </p>
            <p>
              You should consult a qualified financial, legal, or tax professional before making any investment or trading decision. Past performance, simulated or hypothetical results, and any analysis or models do not guarantee future results. You are solely responsible for your own research and decisions.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">3. No Warranties; “As Is”</h2>
            <p>
              THE SERVICE AND ALL CONTENT, DATA, AND MATERIALS ARE PROVIDED ON AN “AS IS” AND “AS AVAILABLE” BASIS WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT, OR ACCURACY. We do not warrant that the Service will be uninterrupted, error-free, secure, or free of viruses or other harmful components. We do not warrant the accuracy, completeness, timeliness, or reliability of any market data, third-party data, or AI-generated content. Use of the Service is at your sole risk.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">4. Limitation of Liability</h2>
            <p className="mb-3">
              TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, IN NO EVENT SHALL FLOWDECK, ITS AFFILIATES, OFFICERS, DIRECTORS, EMPLOYEES, AGENTS, LICENSORS, OR SUPPLIERS BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, PUNITIVE, OR EXEMPLARY DAMAGES, INCLUDING BUT NOT LIMITED TO LOSS OF PROFITS, LOSS OF DATA, LOSS OF GOODWILL, TRADING LOSSES, INVESTMENT LOSSES, OR ANY OTHER PECUNIARY LOSS, ARISING OUT OF OR IN CONNECTION WITH YOUR USE OF OR INABILITY TO USE THE SERVICE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
            </p>
            <p>
              IN NO EVENT SHALL OUR AGGREGATE LIABILITY FOR ANY CLAIMS ARISING OUT OF OR RELATED TO THESE TERMS OR THE SERVICE EXCEED THE GREATER OF (A) ONE HUNDRED UNITED STATES DOLLARS (USD $100) OR (B) THE AMOUNT YOU PAID US, IF ANY, IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM. Some jurisdictions do not allow the exclusion or limitation of certain damages; in such jurisdictions, our liability shall be limited to the maximum extent permitted by law.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">5. Third-Party Data and Sources</h2>
            <p>
              The Service may display or incorporate data, quotes, news, and other content from third-party sources. We do not control, endorse, or guarantee the accuracy, completeness, or timeliness of any third-party content. Delays, errors, or omissions in market or other data may occur. Your reliance on any such content is at your own risk.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">6. Acceptable Use</h2>
            <p className="mb-3">
              You agree not to: (a) use the Service for any illegal purpose or in violation of any applicable laws or regulations; (b) attempt to gain unauthorized access to the Service, other accounts, or any systems or networks; (c) use the Service to transmit malware, spam, or any harmful or disruptive code; (d) scrape, crawl, or use automated means to access the Service without our prior written consent; (e) reverse engineer, decompile, or disassemble any part of the Service; (f) use the Service in any manner that could damage, disable, or overburden our infrastructure; or (g) use the Service to distribute or facilitate any form of market manipulation or insider trading.
            </p>
            <p>
              We reserve the right to suspend or terminate your access to the Service, without notice, for any conduct we believe violates these Terms or is harmful to the Service or others.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">7. Intellectual Property</h2>
            <p>
              The Service and all content, features, and functionality (including but not limited to text, graphics, logos, software, and design) are owned by Flowdeck or its licensors and are protected by copyright, trademark, and other intellectual property laws. You may not copy, modify, distribute, sell, or create derivative works from the Service or any part thereof without our prior written consent.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">8. Indemnification</h2>
            <p>
              You agree to indemnify, defend, and hold harmless Flowdeck and its affiliates, officers, directors, employees, agents, and licensors from and against any and all claims, damages, losses, costs, and expenses (including reasonable attorneys’ fees) arising out of or related to: (a) your use of the Service; (b) your violation of these Terms or any applicable law; (c) your violation of any third-party right; or (d) any trading, investment, or other financial decision you make in reliance on or in connection with the Service.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">9. Modifications to the Service and Terms</h2>
            <p>
              We may modify, suspend, or discontinue the Service (or any part thereof) at any time without notice or liability. We may also update these Terms from time to time. We will indicate the effective date of any material changes. Your continued use of the Service after the effective date of revised Terms constitutes your acceptance of the revised Terms. If you do not agree to the revised Terms, you must stop using the Service.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">10. Governing Law and Disputes</h2>
            <p>
              These Terms shall be governed by and construed in accordance with the laws of the jurisdiction in which Flowdeck operates, without regard to its conflict of law provisions. Any dispute arising out of or relating to these Terms or the Service shall be resolved exclusively in the courts of that jurisdiction, and you consent to the personal jurisdiction of such courts. You waive any right to participate in a class action or representative proceeding.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">11. Severability</h2>
            <p>
              If any provision of these Terms is held to be invalid, illegal, or unenforceable, the remaining provisions shall continue in full force and effect. The invalid or unenforceable provision shall be modified to the minimum extent necessary to make it valid and enforceable while preserving the parties’ intent.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">12. Entire Agreement</h2>
            <p>
              These Terms, together with any other policies or guidelines we publish on the Service, constitute the entire agreement between you and Flowdeck regarding the Service and supersede any prior agreements or understandings. Our failure to enforce any right or provision of these Terms shall not constitute a waiver of such right or provision.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">13. Contact</h2>
            <p>
              For questions about these Terms of Use, please contact us through the contact information provided on the Flowdeck website.
            </p>
          </section>
        </div>

        <div className="mt-12 pt-8 border-t border-gray-700">
          <Link
            to="/"
            className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors"
          >
            ← Back to Flowdeck
          </Link>
        </div>
      </div>
    </div>
  );
}
