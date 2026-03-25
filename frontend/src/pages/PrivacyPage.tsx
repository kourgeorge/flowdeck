import { Link } from 'react-router-dom';

export default function PrivacyPage() {
  const effectiveDate = '2026-03-25';

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-3xl mx-auto text-gray-300">
        <Link
          to="/"
          className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors mb-8"
        >
          ← Back to Flowdeck
        </Link>

        <h1 className="text-3xl font-bold text-white mb-2">Privacy Policy</h1>
        <p className="text-gray-500 text-sm mb-10">Effective date: {effectiveDate}</p>

        <div className="space-y-8 text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">1. Introduction</h2>
            <p>
              Flowdeck ("we," "us," or "our") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our website, applications, and services (collectively, the "Service"). By accessing or using the Service, you acknowledge that you have read, understood, and agree to be bound by this Privacy Policy. If you do not agree with this Privacy Policy, please do not use the Service.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">2. Who We Are</h2>
            <p className="mb-3">
              Flowdeck is the data controller responsible for your personal information. For privacy-related inquiries, please contact us at:
            </p>
            <ul className="list-none ml-4 space-y-1">
              <li><strong className="text-white">Email:</strong> privacy@flowdeck.biz</li>
              <li><strong className="text-white">Support:</strong> Via our <Link to="/contact" className="text-blue-400 hover:text-blue-300 underline">contact page</Link></li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">3. Information We Collect</h2>
            <p className="mb-3">
              We collect several types of information to provide and improve our Service:
            </p>
            
            <h3 className="text-base font-semibold text-white mb-2 mt-4">3.1 Personal Information</h3>
            <p className="mb-2">When you register, subscribe, or interact with our Service, we may collect:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Name and email address</li>
              <li>Account credentials (username, password hash)</li>
              <li>Profile information and preferences</li>
              <li>Payment and billing information (processed through third-party payment processors)</li>
              <li>Communication history with our support team</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">3.2 Financial and Trading Data</h3>
            <p className="mb-2">If you use portfolio tracking, watchlist, or research features, we may collect:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Stock tickers and securities you track or research</li>
              <li>Watchlists and portfolio compositions you create</li>
              <li>Investment preferences and risk profiles you provide</li>
              <li>Trading alerts and notification preferences</li>
              <li>Generated reports, analyses, and recommendations you request</li>
              <li>Custom notes and annotations you add to stocks or reports</li>
            </ul>
            <p className="mt-2 text-gray-400 italic">
              Note: We do not connect to or access your actual brokerage accounts. All portfolio and trading data is manually entered by you or derived from your interactions with our research tools.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">3.3 AI Interaction Data</h3>
            <p className="mb-2">When you use our AI-powered features (chat, copilot, analysis tools), we collect:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Your prompts, questions, and inputs to AI features</li>
              <li>AI-generated responses and recommendations</li>
              <li>Conversation history and context</li>
              <li>Feedback you provide on AI outputs (thumbs up/down, corrections)</li>
              <li>Usage patterns and feature interactions</li>
            </ul>
            <p className="mt-2 text-gray-400 italic">
              Important: Your AI conversation data may be reviewed by our team for quality assurance, support, and service improvement. We do not use your personal prompts or portfolio data to train third-party AI models. See Section 8 for more details.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">3.4 Usage and Technical Data</h3>
            <p className="mb-2">We automatically collect information about your use of the Service:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>IP address and approximate geographic location</li>
              <li>Device type, operating system, and browser information</li>
              <li>Pages visited, features used, and time spent on the Service</li>
              <li>Referral sources and navigation paths</li>
              <li>Error logs and diagnostic data</li>
              <li>Performance metrics and load times</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">3.5 Cookies and Tracking Technologies</h3>
            <p className="mb-2">
              We use cookies, local storage, and similar technologies to enhance your experience. See Section 9 for detailed information about cookies.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">4. Sources of Information</h2>
            <p className="mb-2">We collect information from the following sources:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li><strong className="text-white">Directly from you:</strong> When you register, use features, or contact us</li>
              <li><strong className="text-white">Automatically:</strong> Through cookies, analytics, and usage tracking</li>
              <li><strong className="text-white">Third-party data providers:</strong> Market data, news feeds, and financial information services</li>
              <li><strong className="text-white">Authentication providers:</strong> If you use social login (Google OAuth)</li>
              <li><strong className="text-white">Payment processors:</strong> Transaction and billing information</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">5. How We Use Your Information</h2>
            <p className="mb-3">
              We use the information we collect for the following purposes:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-4">
              <li><strong className="text-white">Service Delivery:</strong> To provide, maintain, and improve the Service, including personalized stock research, AI analysis, portfolio tracking, and alerts</li>
              <li><strong className="text-white">Account Management:</strong> To create and manage your account, authenticate access, and maintain your preferences</li>
              <li><strong className="text-white">Transaction Processing:</strong> To process payments, manage subscriptions, and send billing-related communications</li>
              <li><strong className="text-white">Communication:</strong> To send you service updates, security alerts, support messages, and respond to your inquiries</li>
              <li><strong className="text-white">Marketing:</strong> To send promotional content, feature announcements, and newsletters (with your consent where required by law)</li>
              <li><strong className="text-white">Personalization:</strong> To tailor content, recommendations, and research to your interests and portfolio</li>
              <li><strong className="text-white">Analytics:</strong> To understand usage patterns, measure feature effectiveness, and improve user experience</li>
              <li><strong className="text-white">AI Improvement:</strong> To improve our AI models, prompts, and response quality (using aggregated, anonymized data)</li>
              <li><strong className="text-white">Security:</strong> To detect, prevent, and address fraud, abuse, security vulnerabilities, and technical issues</li>
              <li><strong className="text-white">Legal Compliance:</strong> To comply with legal obligations, enforce our terms, and protect our rights</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">6. Lawful Bases for Processing (GDPR)</h2>
            <p className="mb-3">
              If you are located in the European Economic Area (EEA), United Kingdom, or Switzerland, we process your personal data based on the following lawful bases:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-4">
              <li><strong className="text-white">Contract Performance:</strong> Processing necessary to provide the Service you requested (account creation, feature access, subscription management)</li>
              <li><strong className="text-white">Consent:</strong> Where you have given explicit consent for marketing communications, optional cookies, or specific AI features</li>
              <li><strong className="text-white">Legitimate Interests:</strong> For analytics, service improvement, fraud prevention, and security measures, where not overridden by your rights</li>
              <li><strong className="text-white">Legal Obligation:</strong> To comply with applicable laws, regulations, and legal processes</li>
            </ul>
            <p className="mt-2">
              You have the right to object to processing based on legitimate interests. See Section 13 for information about your rights.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">7. How We Share Your Information</h2>
            <p className="mb-3">
              We do not sell your personal information. We may share your information with the following categories of recipients:
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">7.1 Service Providers and Processors</h3>
            <p className="mb-2">We share data with third-party vendors who perform services on our behalf:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li><strong className="text-white">Cloud Hosting:</strong> Infrastructure and data storage providers</li>
              <li><strong className="text-white">Payment Processing:</strong> Stripe and PayPal for payment and subscription management</li>
              <li><strong className="text-white">Authentication:</strong> Google OAuth for social login</li>
              <li><strong className="text-white">AI Model Providers:</strong> OpenAI, Anthropic, or other LLM providers for AI features</li>
              <li><strong className="text-white">Market Data:</strong> Alpha Vantage, Yahoo Finance, and other financial data providers</li>
              <li><strong className="text-white">Email Delivery:</strong> Transactional and marketing email services</li>
              <li><strong className="text-white">Analytics:</strong> Usage analytics and monitoring tools</li>
              <li><strong className="text-white">Customer Support:</strong> Help desk and communication platforms</li>
              <li><strong className="text-white">Security:</strong> Fraud detection and security monitoring services</li>
            </ul>
            <p className="mt-2 text-gray-400">
              A detailed list of subprocessors is available upon request by contacting privacy@flowdeck.biz.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">7.2 Business Transfers</h3>
            <p>
              If we are involved in a merger, acquisition, bankruptcy, reorganization, or sale of assets, your information may be transferred as part of that transaction. We will notify you via email and/or prominent notice on our Service of any change in ownership or use of your personal information.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">7.3 Legal Requirements and Protection</h3>
            <p className="mb-2">We may disclose your information when required by law or to:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Comply with legal obligations, court orders, or government requests</li>
              <li>Enforce our Terms of Use and other agreements</li>
              <li>Protect our rights, property, or safety, or that of our users or the public</li>
              <li>Detect, prevent, or address fraud, security, or technical issues</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">7.4 Aggregated and Anonymized Data</h3>
            <p>
              We may share aggregated, anonymized, or de-identified data that cannot reasonably be used to identify you for research, analytics, marketing, or other purposes.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">8. AI Features and Data Processing</h2>
            <p className="mb-3">
              Flowdeck uses artificial intelligence to provide stock analysis, research assistance, and personalized recommendations. Here's how we handle AI-related data:
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">8.1 What We Collect</h3>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Your questions, prompts, and inputs to AI chat and copilot features</li>
              <li>AI-generated responses, analyses, and recommendations</li>
              <li>Conversation context and history</li>
              <li>Feedback signals (ratings, corrections, follow-up questions)</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">8.2 How We Use AI Data</h3>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>To provide contextual, personalized responses to your queries</li>
              <li>To maintain conversation continuity within a session</li>
              <li>To improve prompt engineering and response quality</li>
              <li>For quality assurance and support purposes</li>
              <li>To develop and refine our AI features</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">8.3 Third-Party AI Providers</h3>
            <p className="mb-2">
              We use third-party AI model providers (such as OpenAI or Anthropic) to power our AI features. When you interact with AI features:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Your prompts and context may be sent to these providers for processing</li>
              <li>These providers process data according to their own privacy policies and terms</li>
              <li>We have agreements with providers that prohibit them from using your data to train their general models</li>
              <li>Conversation data is typically processed in real-time and not permanently stored by the AI provider</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">8.4 Model Training</h3>
            <p>
              <strong className="text-white">We do not use your personal prompts, portfolio data, or identifiable information to train third-party AI models.</strong> We may use aggregated, anonymized interaction patterns to improve our own prompt templates and feature design.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">8.5 Human Review</h3>
            <p>
              Our team may review AI conversations for quality assurance, debugging, safety monitoring, and customer support. Access is limited to authorized personnel and subject to confidentiality obligations.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">8.6 Automated Decision-Making</h3>
            <p>
              Our AI features provide research, analysis, and recommendations but do not make automated decisions with legal or similarly significant effects. All AI outputs are informational only and should not be relied upon as financial advice. You retain full control over your investment decisions.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">9. Cookies and Tracking Technologies</h2>
            <p className="mb-3">
              We use cookies, local storage, and similar technologies to provide and improve the Service. Here's what we use and why:
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">9.1 Essential Cookies</h3>
            <p className="mb-2">Required for the Service to function properly:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Authentication and session management</li>
              <li>Security and fraud prevention</li>
              <li>Load balancing and performance</li>
              <li>User preferences and settings</li>
            </ul>
            <p className="mt-2 text-gray-400 italic">These cookies cannot be disabled without affecting Service functionality.</p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">9.2 Analytics Cookies</h3>
            <p className="mb-2">Help us understand how users interact with the Service:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Page views and navigation patterns</li>
              <li>Feature usage and engagement metrics</li>
              <li>Error tracking and performance monitoring</li>
              <li>A/B testing and optimization</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">9.3 Advertising Cookies</h3>
            <p>
              <strong className="text-white">We do not currently use advertising or marketing cookies from third-party ad networks.</strong> If this changes, we will update this policy and provide opt-out controls.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">9.4 Managing Cookies</h3>
            <p className="mb-2">You can control cookies through:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Your browser settings (most browsers allow you to refuse or delete cookies)</li>
              <li>Our cookie preferences (if available in your account settings)</li>
              <li>Third-party opt-out tools for analytics services</li>
            </ul>
            <p className="mt-2 text-gray-400">
              Note: Disabling essential cookies may prevent you from using certain features of the Service.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">9.5 Do Not Track</h3>
            <p>
              We do not currently respond to "Do Not Track" (DNT) browser signals. We will update this policy if our approach changes.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">10. Data Retention</h2>
            <p className="mb-3">
              We retain your personal information for as long as necessary to fulfill the purposes outlined in this Privacy Policy, unless a longer retention period is required or permitted by law.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">10.1 Retention by Data Type</h3>
            <ul className="list-disc list-inside space-y-2 ml-4">
              <li><strong className="text-white">Account Data:</strong> Retained while your account is active and for up to 90 days after account deletion (unless required for legal or security purposes)</li>
              <li><strong className="text-white">Billing Records:</strong> Retained for 7 years to comply with tax and accounting regulations</li>
              <li><strong className="text-white">Portfolio and Watchlist Data:</strong> Retained while your account is active; deleted within 90 days of account deletion</li>
              <li><strong className="text-white">AI Conversation History:</strong> Retained for up to 12 months for service improvement and support; may be retained longer in anonymized form</li>
              <li><strong className="text-white">Support Tickets:</strong> Retained for 3 years for quality assurance and legal purposes</li>
              <li><strong className="text-white">Analytics and Usage Logs:</strong> Retained for up to 24 months; aggregated data may be retained indefinitely</li>
              <li><strong className="text-white">Security Logs:</strong> Retained for up to 12 months for fraud prevention and security monitoring</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">10.2 Account Deletion</h3>
            <p>
              When you delete your account, we will delete or anonymize your personal information within 90 days, except where we are required to retain it for legal, regulatory, security, or fraud prevention purposes.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">11. International Data Transfers</h2>
            <p className="mb-3">
              Your information may be transferred to and processed in countries other than your country of residence. These countries may have data protection laws that differ from those in your jurisdiction.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">11.1 Primary Hosting</h3>
            <p>
              Our primary infrastructure is hosted in the United States and may utilize cloud services in other regions for redundancy and performance.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">11.2 Safeguards for EU/EEA/UK Transfers</h3>
            <p className="mb-2">
              For transfers of personal data from the European Economic Area, United Kingdom, or Switzerland to countries without adequate data protection laws, we implement appropriate safeguards, including:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Standard Contractual Clauses (SCCs) approved by the European Commission</li>
              <li>Data Processing Agreements with service providers</li>
              <li>Technical and organizational security measures</li>
              <li>Adequacy decisions where applicable</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">11.3 AI Provider Locations</h3>
            <p>
              Third-party AI model providers may process data in the United States or other jurisdictions. We ensure these providers implement appropriate safeguards for international transfers.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">12. Data Security</h2>
            <p className="mb-3">
              We implement reasonable administrative, technical, and physical security measures to protect your information from unauthorized access, use, disclosure, alteration, or destruction.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">12.1 Security Measures</h3>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Encryption of data in transit (TLS/SSL) and at rest</li>
              <li>Secure authentication and password hashing</li>
              <li>Access controls and role-based permissions</li>
              <li>Regular security audits and vulnerability assessments</li>
              <li>Monitoring and logging of security events</li>
              <li>Incident response and breach notification procedures</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">12.2 Payment Security</h3>
            <p>
              We do not store credit card numbers or payment card details. All payment processing is handled by PCI-DSS compliant third-party processors (Stripe, PayPal). We only store billing addresses and transaction metadata necessary for subscription management.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">12.3 Limitations</h3>
            <p>
              No method of transmission over the Internet or electronic storage is 100% secure. While we strive to use commercially acceptable means to protect your information, we cannot guarantee absolute security. You are responsible for maintaining the confidentiality of your account credentials.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">12.4 Security Breach Notification</h3>
            <p>
              In the event of a data breach that affects your personal information, we will notify you and relevant authorities as required by applicable law. Notification will be provided via email, account notification, or prominent notice on our Service, depending on the nature and severity of the breach.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">13. Your Rights and Choices</h2>
            <p className="mb-3">
              Depending on your location, you may have certain rights regarding your personal information. We are committed to honoring these rights in accordance with applicable law.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">13.1 Rights Under GDPR (EU/EEA/UK)</h3>
            <p className="mb-2">If you are located in the European Economic Area, United Kingdom, or Switzerland, you have the following rights:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li><strong className="text-white">Right of Access:</strong> Request a copy of your personal data</li>
              <li><strong className="text-white">Right to Rectification:</strong> Correct inaccurate or incomplete data</li>
              <li><strong className="text-white">Right to Erasure:</strong> Request deletion of your data (subject to legal exceptions)</li>
              <li><strong className="text-white">Right to Restriction:</strong> Limit how we process your data</li>
              <li><strong className="text-white">Right to Data Portability:</strong> Receive your data in a structured, machine-readable format</li>
              <li><strong className="text-white">Right to Object:</strong> Object to processing based on legitimate interests or for direct marketing</li>
              <li><strong className="text-white">Right to Withdraw Consent:</strong> Withdraw consent for processing based on consent</li>
              <li><strong className="text-white">Right to Lodge a Complaint:</strong> File a complaint with your local data protection authority</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">13.2 Rights Under CCPA (California)</h3>
            <p className="mb-2">If you are a California resident, you have the following rights:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li><strong className="text-white">Right to Know:</strong> Request information about data collection, use, and sharing</li>
              <li><strong className="text-white">Right to Delete:</strong> Request deletion of your personal information</li>
              <li><strong className="text-white">Right to Opt-Out:</strong> Opt out of the sale of personal information (we do not sell personal information)</li>
              <li><strong className="text-white">Right to Non-Discrimination:</strong> Not be discriminated against for exercising your rights</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">13.3 How to Exercise Your Rights</h3>
            <p className="mb-2">To exercise any of these rights, please contact us at:</p>
            <ul className="list-none ml-4 space-y-1">
              <li><strong className="text-white">Email:</strong> privacy@flowdeck.biz</li>
              <li><strong className="text-white">Subject Line:</strong> "Privacy Rights Request"</li>
              <li><strong className="text-white">Include:</strong> Your name, email address, and specific request</li>
            </ul>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">13.4 Identity Verification</h3>
            <p>
              To protect your privacy and security, we will verify your identity before processing rights requests. We may ask you to provide additional information or log in to your account to confirm your identity.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">13.5 Response Time</h3>
            <p>
              We will respond to your request within 30 days (or as required by applicable law). If we need additional time, we will notify you of the extension and the reason for the delay.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">13.6 Limitations and Exceptions</h3>
            <p>
              Certain rights may be limited by legal obligations, ongoing investigations, or technical constraints. We will explain any limitations when responding to your request.
            </p>

            <h3 className="text-base font-semibold text-white mb-2 mt-4">13.7 Marketing Opt-Out</h3>
            <p>
              You can opt out of marketing communications at any time by:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-4 mt-2">
              <li>Clicking the "unsubscribe" link in marketing emails</li>
              <li>Updating your email preferences in your account settings</li>
              <li>Contacting us at privacy@flowdeck.biz</li>
            </ul>
            <p className="mt-2 text-gray-400 italic">
              Note: You will still receive transactional emails related to your account and subscriptions.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">14. Complaints and Supervisory Authorities</h2>
            <p className="mb-3">
              If you have concerns about how we handle your personal information, please contact us first at privacy@flowdeck.biz. We will investigate and respond to your complaint.
            </p>
            <p className="mb-3">
              If you are not satisfied with our response, you have the right to lodge a complaint with your local data protection authority:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li><strong className="text-white">EU/EEA:</strong> Contact your national data protection authority (list available at <a href="https://edpb.europa.eu/about-edpb/board/members_en" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">edpb.europa.eu</a>)</li>
              <li><strong className="text-white">UK:</strong> Information Commissioner's Office (ICO) at <a href="https://ico.org.uk" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">ico.org.uk</a></li>
              <li><strong className="text-white">Switzerland:</strong> Federal Data Protection and Information Commissioner (FDPIC)</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">15. Children's Privacy</h2>
            <p className="mb-3">
              The Service is not intended for individuals under the age of 18. We do not knowingly collect personal information from children under 18. If you are under 18, please do not use the Service or provide any personal information.
            </p>
            <p className="mb-3">
              If we become aware that we have collected personal information from a child under 18 without parental consent, we will take steps to delete that information as soon as possible.
            </p>
            <p>
              If you believe we have collected information from a child under 18, please contact us immediately at privacy@flowdeck.biz.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">16. Business Transfers and Corporate Changes</h2>
            <p className="mb-3">
              If Flowdeck is involved in a merger, acquisition, bankruptcy, reorganization, partnership, asset sale, or other business transaction, your personal information may be transferred, sold, or assigned as part of that transaction.
            </p>
            <p className="mb-3">
              In such cases:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>We will notify you via email and/or prominent notice on the Service before your information is transferred</li>
              <li>The acquiring entity will be bound by this Privacy Policy or will provide notice of any changes</li>
              <li>You will have the opportunity to delete your account before the transfer if you do not agree to the new terms</li>
              <li>Your rights under applicable data protection laws will continue to apply</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">17. Third-Party Services and Links</h2>
            <p className="mb-3">
              The Service may contain links to third-party websites, applications, or services that are not operated by us. We are not responsible for the privacy practices of these third parties.
            </p>
            <p className="mb-3">
              When you use third-party services through our platform (such as payment processors or authentication providers), their privacy policies and terms apply. We encourage you to review the privacy policies of any third-party services you access.
            </p>
            <p>
              Key third-party services we integrate with:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-4 mt-2">
              <li><strong className="text-white">Stripe:</strong> Payment processing (<a href="https://stripe.com/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">privacy policy</a>)</li>
              <li><strong className="text-white">PayPal:</strong> Payment processing (<a href="https://www.paypal.com/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">privacy policy</a>)</li>
              <li><strong className="text-white">Google:</strong> OAuth authentication (<a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">privacy policy</a>)</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">18. Financial Services Disclaimer</h2>
            <p className="mb-3">
              <strong className="text-white">Flowdeck is a research and information platform, not a financial advisor or broker.</strong> The Service provides stock research, analysis, and educational content for informational purposes only.
            </p>
            <p className="mb-3">
              Regarding your data:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>We do not access or connect to your actual brokerage accounts</li>
              <li>Portfolio and watchlist data is manually entered by you</li>
              <li>We do not execute trades or manage investments on your behalf</li>
              <li>AI-generated recommendations are informational only and not financial advice</li>
              <li>We do not share your portfolio data with brokers or trading platforms</li>
            </ul>
            <p className="mt-3">
              Any investment decisions you make are your sole responsibility. See our <Link to="/terms" className="text-blue-400 hover:text-blue-300 underline">Terms of Use</Link> for complete disclaimers.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">19. Automated Profiling and Personalization</h2>
            <p className="mb-3">
              We use automated processing to personalize your experience on Flowdeck. This includes:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Recommending stocks based on your watchlists and research history</li>
              <li>Tailoring news and market updates to your interests</li>
              <li>Customizing AI responses based on your portfolio and preferences</li>
              <li>Prioritizing content and alerts relevant to your tracked securities</li>
            </ul>
            <p className="mt-3 mb-3">
              <strong className="text-white">This personalization does not have legal or similarly significant effects.</strong> It is designed to improve your research experience, not to make automated decisions about you.
            </p>
            <p>
              You can reduce personalization by:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-4 mt-2">
              <li>Clearing your watchlists and portfolio data</li>
              <li>Using the Service without logging in (limited features)</li>
              <li>Contacting us to opt out of certain personalization features</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">20. Changes to This Privacy Policy</h2>
            <p className="mb-3">
              We may update this Privacy Policy from time to time to reflect changes in our practices, technology, legal requirements, or other factors. We will indicate the effective date of any material changes at the top of this policy.
            </p>
            <p className="mb-3">
              For material changes that significantly affect your rights or how we use your information:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>We will notify you via email (if you have provided an email address)</li>
              <li>We will display a prominent notice on the Service</li>
              <li>We may require you to acknowledge the updated policy before continuing to use the Service</li>
            </ul>
            <p className="mt-3">
              Your continued use of the Service after the effective date of the revised Privacy Policy constitutes your acceptance of the changes. If you do not agree to the revised policy, you must stop using the Service and may delete your account.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">21. Contact Us</h2>
            <p className="mb-3">
              If you have any questions, concerns, or requests regarding this Privacy Policy or our privacy practices, please contact us:
            </p>
            <ul className="list-none ml-4 space-y-2">
              <li><strong className="text-white">Privacy Inquiries:</strong> privacy@flowdeck.biz</li>
              <li><strong className="text-white">General Support:</strong> Via our <Link to="/contact" className="text-blue-400 hover:text-blue-300 underline">contact page</Link></li>
              <li><strong className="text-white">Data Protection Officer:</strong> Available upon request for GDPR-related matters</li>
            </ul>
            <p className="mt-4 text-gray-400">
              When contacting us about privacy matters, please include "Privacy Request" in the subject line and provide sufficient detail for us to understand and respond to your inquiry.
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

// Made with Bob
