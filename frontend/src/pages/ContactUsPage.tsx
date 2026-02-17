import { Link } from 'react-router-dom';

export default function ContactUsPage() {
  return (
    <div className="min-h-screen p-8">
      <div className="max-w-3xl mx-auto text-gray-300">
        <Link
          to="/"
          className="inline-flex items-center text-sm text-gray-400 hover:text-white transition-colors mb-8"
        >
          ← Back to Flowdeck
        </Link>

        <h1 className="text-3xl font-bold text-white mb-2">Contact Us</h1>
        <p className="text-gray-500 text-sm mb-10">
          Have a question, feedback, or need support? We’d love to hear from you.
        </p>

        <div className="space-y-8 text-sm leading-relaxed">
          <section>
            <h2 className="text-lg font-semibold text-white mb-3">Get in touch</h2>
            <p className="mb-4">
              For general inquiries, product feedback, or partnership opportunities, reach out using the form below or email us directly.
            </p>
            <p>
              <a
                href="mailto:support@flowdeck.com"
                className="text-blue-400 hover:text-blue-300 transition-colors"
              >
                support@flowdeck.com
              </a>
            </p>
          </section>

          <section className="bg-gray-800/50 rounded-lg border border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Send a message</h2>
            <form
              action="mailto:support@flowdeck.com"
              method="get"
              className="space-y-4"
            >
              <input type="hidden" name="subject" value="Flowdeck – Contact form" />
              <div>
                <label htmlFor="contact-name" className="block text-gray-400 text-xs font-medium mb-1">
                  Name
                </label>
                <input
                  id="contact-name"
                  name="name"
                  type="text"
                  placeholder="Your name"
                  className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label htmlFor="contact-email" className="block text-gray-400 text-xs font-medium mb-1">
                  Email
                </label>
                <input
                  id="contact-email"
                  name="email"
                  type="email"
                  placeholder="you@example.com"
                  required
                  className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label htmlFor="contact-message" className="block text-gray-400 text-xs font-medium mb-1">
                  Message
                </label>
                <textarea
                  id="contact-message"
                  name="body"
                  rows={4}
                  placeholder="How can we help?"
                  className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
                />
              </div>
              <button
                type="submit"
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
              >
                Send message
              </button>
            </form>
            <p className="text-gray-500 text-xs mt-3">
              Submitting will open your email client. For a direct link, use{' '}
              <a href="mailto:support@flowdeck.com" className="text-blue-400 hover:text-blue-300">
                support@flowdeck.com
              </a>
              .
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
