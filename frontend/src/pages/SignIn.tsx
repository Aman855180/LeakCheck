import React, { useState } from 'react';
import { ShieldCheck, Lock, Mail, AlertCircle, ArrowRight, UserCheck, ShieldAlert } from 'lucide-react';
import { api, User } from '../api/client';

interface SignInProps {
  onLoginSuccess: (user: User) => void;
}

export const SignIn: React.FC<SignInProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await api.login(email, password);
      onLoginSuccess(response.user);
    } catch (err: any) {
      if (err.status === 429) {
        setError('Too many failed login attempts. Your IP is locked for 15 minutes.');
      } else if (err.status === 401) {
        setError('Invalid email or password. Please verify your credentials.');
      } else {
        setError(err.message || 'Authentication failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFill = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword('Password123!');
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center items-center gap-2 mb-2">
          <div className="w-10 h-10 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <span className="text-2xl font-semibold tracking-tight text-white font-mono">
            Leak<span className="text-sky-400">Check</span>
          </span>
        </div>
        <p className="text-center text-xs font-mono text-slate-400 uppercase tracking-widest">
          Payment Reconciliation & Leakage Detection
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-slate-800/90 border border-slate-700/80 rounded-xl py-8 px-6 shadow-2xl backdrop-blur-sm sm:px-10">
          <form className="space-y-5" onSubmit={handleSubmit}>
            {error && (
              <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-3.5 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                <div className="text-xs text-rose-200 leading-relaxed font-medium">
                  {error}
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-300 uppercase tracking-wider mb-1.5">
                Work Email
              </label>
              <div className="relative rounded-lg shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company-a.com"
                  className="block w-full pl-9 pr-3 py-2 bg-slate-900/80 border border-slate-700 rounded-lg text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 uppercase tracking-wider mb-1.5">
                Password
              </label>
              <div className="relative rounded-lg shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="block w-full pl-9 pr-3 py-2 bg-slate-900/80 border border-slate-700 rounded-lg text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-colors font-mono"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-sky-600 hover:bg-sky-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-sky-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all font-sans"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Demo Account Quick Fill */}
          <div className="mt-8 pt-6 border-t border-slate-700/60">
            <p className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-3 text-center">
              Quick Sign-In with Demo Accounts
            </p>
            <div className="grid grid-cols-1 gap-2.5">
              <button
                type="button"
                onClick={() => handleQuickFill('finance_exec@company-a.com')}
                className="flex items-center justify-between px-3.5 py-2.5 rounded-lg bg-slate-900/60 hover:bg-slate-900 border border-slate-700/60 text-left transition-colors group"
              >
                <div className="flex items-center gap-2.5">
                  <UserCheck className="w-4 h-4 text-emerald-400" />
                  <div>
                    <div className="text-xs font-medium text-slate-200">Finance Executive</div>
                    <div className="text-[11px] font-mono text-slate-400">finance_exec@company-a.com</div>
                  </div>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                  Full Access
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleQuickFill('cofounder@company-a.com')}
                className="flex items-center justify-between px-3.5 py-2.5 rounded-lg bg-slate-900/60 hover:bg-slate-900 border border-slate-700/60 text-left transition-colors group"
              >
                <div className="flex items-center gap-2.5">
                  <ShieldAlert className="w-4 h-4 text-sky-400" />
                  <div>
                    <div className="text-xs font-medium text-slate-200">Finance Co-founder</div>
                    <div className="text-[11px] font-mono text-slate-400">cofounder@company-a.com</div>
                  </div>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20">
                  Review & Audit
                </span>
              </button>
            </div>
          </div>
        </div>

        <div className="mt-6 text-center text-xs text-slate-500 font-mono">
          Security: HttpOnly Session Cookies • CSRF Protected • DPDP Act 2023 Compliant
        </div>
      </div>
    </div>
  );
};
