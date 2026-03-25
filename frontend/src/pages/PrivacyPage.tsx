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
              Flowdeck ("we," "us," or "our") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our website, applications, and services (collectively, the "Service"). By accessing or using the Service, you agree to the terms of this Privacy Policy. If you do not agree with this Privacy Policy, please do not use the Service.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">2. Information We Collect</h2>
            <p className="mb-3">
              We may collect the following types of information:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-4">
              <li>
                <strong className="text-white">Personal Information:</strong> When you register for an account, subscribe to our services, or contact us, we may collect personal information such as your name, email address, payment information, and other contact details.
              </li>
              <li>
                <strong className="text-white">Usage Data:</strong> We automatically collect information about your interactions with the Service, including IP address, browser type, device information, pages visited, time spent on pages, and other diagnostic data.
              </li>
              <li>
                <strong className="text-white">Cookies and Tracking Technologies:</strong> We use cookies, web beacons, and similar technologies to track activity on our Service and store certain information. You can instruct your browser to refuse all cookies or to indicate when a cookie is being sent.
              </li>
              <li>
                <strong className="text-white">Financial and Trading Data:</strong> If you use features that involve tracking portfolios or watchlists, we may collect information about your stock preferences, trading interests, and related financial data you choose to provide.
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">3. How We Use Your Information</h2>
            <p className="mb-3">
              We use the information we collect for the following purposes:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-4">
              <li>To provide, maintain, and improve the Service</li>
              <li>To process transactions and send related information, including confirmations and invoices</li>
              <li>To send you technical notices, updates, security alerts, and support messages</li>
              <li>To respond to your comments, questions, and customer service requests</li>
              <li>To send you marketing and promotional communications (with your consent where required)</li>
              <li>To monitor and analyze usage trends and preferences</li>
              <li>To detect, prevent, and address technical issues, fraud, and security vulnerabilities</li>
              <li>To personalize your experience and deliver content relevant to your interests</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">4. How We Share Your Information</h2>
            <p className="mb-3">
              We may share your information in the following circumstances:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-4">
              <li>
                <strong className="text-white">Service Providers:</strong> We may share your information with third-party vendors, consultants, and service providers who perform services on our behalf, such as payment processing, data analysis, email delivery, hosting services, and customer support.
              </li>
              <li>
                <strong className="text-white">Business Transfers:</strong> If we are involved in a merger, acquisition, or sale of assets, your information may be transferred as part of that transaction.
              </li>
              <li>
                <strong className="text-white">Legal Requirements:</strong> We may disclose your information if required to do so by law or in response to valid requests by public authorities (e.g., a court or government agency).
              </li>
              <li>
                <strong className="text-white">Protection of Rights:</strong> We may disclose your information when we believe it is necessary to protect our rights, your safety, or the safety of others, investigate fraud, or respond to a government request.
              </li>
            </ul>
            <p className="mt-3">
              We do not sell your personal information to third parties.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">5. Data Security</h2>
            <p>
              We implement reasonable administrative, technical, and physical security measures to protect your information from unauthorized access, use, or disclosure. However, no method of transmission over the Internet or electronic storage is 100% secure. While we strive to use commercially acceptable means to protect your information, we cannot guarantee its absolute security.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">6. Data Retention</h2>
            <p>
              We retain your personal information for as long as necessary to fulfill the purposes outlined in this Privacy Policy, unless a longer retention period is required or permitted by law. When we no longer need your information, we will securely delete or anonymize it.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">7. Your Rights and Choices</h2>
            <p className="mb-3">
              Depending on your location, you may have certain rights regarding your personal information, including:
            </p>
            <ul className="list-disc list-inside space-y-2 ml-4">
              <li>
                <strong className="text-white">Access and Correction:</strong> You may request access to or correction of your personal information.
              </li>
              <li>
                <strong className="text-white">Deletion:</strong> You may request deletion of your personal information, subject to certain exceptions.
              </li>
              <li>
                <strong className="text-white">Opt-Out:</strong> You may opt out of receiving marketing communications from us by following the unsubscribe instructions in those communications or by contacting us.
              </li>
              <li>
                <strong className="text-white">Data Portability:</strong> You may request a copy of your personal information in a structured, commonly used format.
              </li>
              <li>
                <strong className="text-white">Withdraw Consent:</strong> If we process your information based on your consent, you may withdraw that consent at any time.
              </li>
            </ul>
            <p className="mt-3">
              To exercise these rights, please contact us using the information provided in Section 12.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">8. Third-Party Links and Services</h2>
            <p>
              The Service may contain links to third-party websites, applications, or services that are not operated by us. We are not responsible for the privacy practices of these third parties. We encourage you to review the privacy policies of any third-party services you access through the Service.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">9. Children's Privacy</h2>
            <p>
              The Service is not intended for individuals under the age of 18. We do not knowingly collect personal information from children under 18. If we become aware that we have collected personal information from a child under 18 without parental consent, we will take steps to delete that information.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">10. International Data Transfers</h2>
            <p>
              Your information may be transferred to and maintained on computers located outside of your state, province, country, or other governmental jurisdiction where data protection laws may differ. By using the Service, you consent to the transfer of your information to such locations.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">11. Changes to This Privacy Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. We will notify you of any material changes by posting the new Privacy Policy on this page and updating the effective date. Your continued use of the Service after the effective date of the revised Privacy Policy constitutes your acceptance of the changes.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-semibold text-white mb-3">12. Contact Us</h2>
            <p>
              If you have any questions, concerns, or requests regarding this Privacy Policy or our privacy practices, please contact us through the contact information provided on the Flowdeck website or via our <Link to="/contact" className="text-blue-400 hover:text-blue-300 underline">contact page</Link>.
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
