import React, { useState, useEffect } from 'react';
import { ShieldCheck, LogOut, User as UserIcon, CheckCircle2, Database, Cpu } from 'lucide-react';
import { api, User, RateCard } from './api/client';
import { SignIn } from './pages/SignIn';

export const App: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [rateCards, setRateCards] = useState<RateCard[]>([]);
  const [rateCardsLoading, setRateCardsLoading] = useState<boolean>(false);

  useEffect(() => {
    checkSession();
  }, []);

  const checkSession = async () => {
    try {
      const user = await api.getMe();
      setCurrentUser(user);
      loadRateCards();
    } catch {
      setCurrentUser(null);
    } finally {
      setLoading(false);
    }
  };

  const loadRateCards = async () => {
    setRateCardsLoading(true);
    try {
      const cards = await api.listRateCards();
      setRateCards(cards);
    } catch (err) {
      console.error('Failed to load rate cards', err);
    } finally {
      setRateCardsLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
    } finally {
      setCurrentUser(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-slate-400 tracking-wider">INITIALIZING LEAKCHECK...</span>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return <SignIn onLoginSuccess={(user) => {
      setCurrentUser(user);
      loadRateCards();
    }} />;
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans">
      {/* Top Navigation */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <span className="text-lg font-semibold tracking-tight text-white font-mono">
                Leak<span className="text-sky-400">Check</span>
              </span>
              <span className="ml-2 px-1.5 py-0.5 text-[10px] font-mono rounded bg-slate-800 text-slate-400 border border-slate-700">
                Phase 1 Foundation
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-xs">
              <UserIcon className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-slate-300 font-mono">{currentUser.email}</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider font-semibold ${
                currentUser.role === 'finance_exec'
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                  : 'bg-sky-500/10 text-sky-400 border border-sky-500/30'
              }`}>
                {currentUser.role === 'finance_exec' ? 'Finance Exec' : 'Co-founder'}
              </span>
            </div>

            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 text-xs border border-slate-700 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Banner */}
        <div className="bg-gradient-to-r from-slate-800/80 via-slate-800/60 to-slate-900 border border-slate-700/80 rounded-xl p-6 shadow-xl mb-8">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-semibold text-white tracking-tight">
                Foundation Verification & System Health
              </h1>
              <p className="mt-1 text-sm text-slate-400">
                Core database schema, authentication, RBAC authorization, and calibrated rate cards are live.
              </p>
            </div>
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              All Systems Operational
            </span>
          </div>

          {/* Grid of Verified Foundation Capabilities */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
            <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4">
              <div className="flex items-center gap-2 text-sky-400 text-xs font-mono uppercase tracking-wider mb-2">
                <Database className="w-4 h-4" />
                <span>PostgreSQL 18 & Ledger</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Relational schema with <code className="text-sky-300">btree_gist</code> date range constraints, trigger-enforced append-only ledgers, and two-phase lineage locks.
              </p>
            </div>

            <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4">
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-mono uppercase tracking-wider mb-2">
                <ShieldCheck className="w-4 h-4" />
                <span>API-Level RBAC</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                HttpOnly SameSite=Lax session cookies, CSRF protection on state-changing endpoints, and role-based gating (<code className="text-emerald-300">finance_exec</code> vs <code className="text-sky-300">cofounder</code>).
              </p>
            </div>

            <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-4">
              <div className="flex items-center gap-2 text-amber-400 text-xs font-mono uppercase tracking-wider mb-2">
                <Cpu className="w-4 h-4" />
                <span>Rate Card Engine</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                Half-open <code className="text-amber-300">[)</code> date interval semantics calibrated for exact reproduction of the 3 client financial samples.
              </p>
            </div>
          </div>
        </div>

        {/* Live Seeded Rate Cards Display */}
        <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl overflow-hidden shadow-xl">
          <div className="px-6 py-4 border-b border-slate-700/80 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-white tracking-tight">
                Seeded Contractual Rate Cards
              </h2>
              <p className="text-xs text-slate-400">
                Contractual parameters calibrated for exact client samples (Section 9.8)
              </p>
            </div>
            <span className="text-xs font-mono text-slate-400">
              {rateCards.length} Active Cards Loaded
            </span>
          </div>

          {rateCardsLoading ? (
            <div className="p-8 text-center text-xs font-mono text-slate-400">
              Loading rate cards...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-900/80 text-slate-400 font-mono uppercase tracking-wider text-[11px] border-b border-slate-700/60">
                  <tr>
                    <th className="py-3 px-6">Partner</th>
                    <th className="py-3 px-6">Channel</th>
                    <th className="py-3 px-6">Rule Type</th>
                    <th className="py-3 px-6">Effective Window</th>
                    <th className="py-3 px-6">Parameters & Tariff Summary</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60 text-slate-300">
                  {rateCards.map((card) => (
                    <tr key={card.id} className="hover:bg-slate-700/30 transition-colors">
                      <td className="py-3.5 px-6 font-mono font-medium text-white">
                        {card.partner_id}
                      </td>
                      <td className="py-3.5 px-6">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider bg-slate-900 border border-slate-700 text-slate-300">
                          {card.channel}
                        </span>
                      </td>
                      <td className="py-3.5 px-6 font-mono text-sky-400">
                        {card.rule_type}
                      </td>
                      <td className="py-3.5 px-6 font-mono text-[11px] text-slate-400">
                        [{card.valid_from} &rarr; {card.valid_until || '&infin;'})
                      </td>
                      <td className="py-3.5 px-6">
                        <div className="font-mono text-[11px] text-slate-300 bg-slate-900/60 p-2 rounded border border-slate-800">
                          {JSON.stringify(card.params_json)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
