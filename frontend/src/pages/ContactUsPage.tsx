import { useState } from 'react';
import { Link } from 'react-router-dom';
import { contactApi } from '../services/api';

export default function ContactUsPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState<'idle' | 'sending' | 'success' | 'error'>('idle');
  const [errorDetail, setErrorDetail] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus('sending');
    setErrorDetail('');
    try {
      await contactApi.submit({ name, email, message });
      setStatus('success');
      setName('');
      setEmail('');
      setMessage('');
    } catch (err: unknown) {
      setStatus('error');
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : '';
      setErrorDetail(typeof msg === 'string' ? msg : 'Failed to send. Please try again or email us directly.');
    }
  }

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
              For general inquiries, product feedback, or partnership opportunities, reach out using the form below.
            </p>
          </section>

          <section className="bg-gray-800/50 rounded-lg border border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Send a message</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="contact-name" className="block text-gray-400 text-xs font-medium mb-1">
                  Name
                </label>
                <input
                  id="contact-name"
                  name="name"
                  type="text"
                  placeholder="Your name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
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
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              <div>
                <label htmlFor="contact-message" className="block text-gray-400 text-xs font-medium mb-1">
                  Message
                </label>
                <textarea
                  id="contact-message"
                  name="message"
                  rows={4}
                  placeholder="How can we help?"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  className="w-full px-4 py-2 rounded-lg bg-gray-700 border border-gray-600 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-y"
                />
              </div>
              {status === 'success' && (
                <p className="text-green-400 text-sm">Message sent successfully. We'll get back to you soon.</p>
              )}
              {status === 'error' && (
                <p className="text-red-400 text-sm">{errorDetail}</p>
              )}
              <button
                type="submit"
                disabled={status === 'sending'}
                className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
              >
                {status === 'sending' ? 'Sending…' : 'Send message'}
              </button>
            </form>
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
