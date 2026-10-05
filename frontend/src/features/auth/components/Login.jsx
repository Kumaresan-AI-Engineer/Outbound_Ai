import { useState } from 'react';
import { Headphones, Loader2 } from 'lucide-react';
import { useAuth } from '../context/authContextBase';

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-4">
      <div className="card w-full max-w-sm p-8 anim-enter">
        <div className="flex items-center gap-3 mb-8 justify-center">
          <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center shadow-md shadow-blue-600/20">
            <Headphones className="w-4 h-4 text-white" />
          </div>
          <span className="text-[18px] font-extrabold text-gray-900 tracking-tight">
            Outbound<span className="text-blue-600">AI</span>
          </span>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[13px] font-semibold text-gray-600 mb-1.5">Email</label>
            <input
              type="email"
              required
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-lg border border-gray-200 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"
              placeholder="you@company.com"
            />
          </div>
          <div>
            <label className="block text-[13px] font-semibold text-gray-600 mb-1.5">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-lg border border-gray-200 text-[14px] focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"
              placeholder="••••••••"
            />
          </div>

          {error && (
            <p className="text-[13px] text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold text-[14px] py-2.5 rounded-lg transition-colors"
          >
            {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
            Sign in
          </button>
        </form>
      </div>
    </div>
  );
}
