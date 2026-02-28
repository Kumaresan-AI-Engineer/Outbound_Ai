import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
  Plus, Search, Trash2, X, PhoneCall, Loader2, Phone, Users, Building2, TrendingUp
} from 'lucide-react';

const STATUS_STYLES = {
  new: 'bg-blue-50 text-blue-600',
  called: 'bg-emerald-50 text-emerald-600',
  follow_up: 'bg-amber-50 text-amber-600',
  closed: 'bg-gray-100 text-gray-500',
};
const STATUS_LABELS = { new: 'New', called: 'Called', follow_up: 'Follow Up', closed: 'Closed' };

export default function ContactTable({ onCallContact, makeCall, deviceReady }) {
  const [contacts, setContacts] = useState([]);
  const [search, setSearch] = useState('');
  const [showAdd, setShowAdd] = useState(false);
  const [loading, setLoading] = useState(true);
  const [callingId, setCallingId] = useState(null);
  const [form, setForm] = useState({ name: '', phone: '', company: '', notes: '' });
  const [callTarget, setCallTarget] = useState(null);
  const [viewMode, setViewMode] = useState('table');

  const fetchContacts = async () => {
    try { const res = await fetch('/contacts/'); setContacts(await res.json()); }
    catch (err) { console.error(err); }
    finally { setLoading(false); }
  };
  useEffect(() => { fetchContacts(); }, []);

  const addContact = async () => {
    if (!form.name || !form.phone) return;
    try {
      const res = await fetch('/contacts/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) });
      if (res.ok) { setForm({ name: '', phone: '', company: '', notes: '' }); setShowAdd(false); fetchContacts(); }
    } catch (err) { console.error(err); }
  };

  const deleteContact = async (id) => {
    try { await fetch(`/contacts/${id}`, { method: 'DELETE' }); fetchContacts(); }
    catch (err) { console.error(err); }
  };

  const confirmCall = async () => {
    if (!callTarget) return;
    const contact = callTarget;
    setCallTarget(null);
    setCallingId(contact.id);
    try {
      const res = await fetch('/calls/initiate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ contact_id: contact.id, phone: contact.phone }) });
      if (res.ok) { const data = await res.json(); await makeCall({ To: contact.phone, callId: data.call_id }); onCallContact(contact, data.call_id); }
    } catch (err) { console.error(err); }
    finally { setCallingId(null); }
  };

  const filtered = contacts.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.phone.includes(search) ||
    c.company.toLowerCase().includes(search.toLowerCase())
  );

  const stats = {
    total: contacts.length,
    new: contacts.filter(c => c.status === 'new').length,
    called: contacts.filter(c => c.status === 'called').length,
    followUp: contacts.filter(c => c.status === 'follow_up').length,
  };

  return (
    <div className="py-8 anim-enter">
      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4 mb-8 anim-enter">
        {[
          { label: 'Total Contacts', value: stats.total, icon: Users, color: 'blue' },
          { label: 'New Leads', value: stats.new, icon: TrendingUp, color: 'blue' },
          { label: 'Called', value: stats.called, icon: Phone, color: 'emerald' },
          { label: 'Follow Up', value: stats.followUp, icon: Building2, color: 'amber' },
        ].map((stat, i) => (
          <div key={stat.label} className={`card hover-glow p-5 anim-enter delay-${i+1}`}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-[13px] font-semibold text-gray-400 uppercase tracking-wider">{stat.label}</span>
              <div className={`w-8 h-8 rounded-lg bg-${stat.color}-50 flex items-center justify-center`}>
                <stat.icon className={`w-4 h-4 text-${stat.color}-500`} />
              </div>
            </div>
            <p className="text-[30px] font-extrabold text-gray-900 leading-none">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search contacts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-11 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-[15px] text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-blue-300 focus:ring-3 focus:ring-blue-100 transition-all"
          />
        </div>
        <div className="flex items-center gap-3">
          {/* View toggle */}
          <div className="flex bg-gray-100 rounded-lg p-0.5">
            <button onClick={() => setViewMode('table')} className={`px-3 py-1.5 rounded-md text-[13px] font-semibold transition-all ${viewMode === 'table' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-400'}`}>
              Table
            </button>
            <button onClick={() => setViewMode('cards')} className={`px-3 py-1.5 rounded-md text-[13px] font-semibold transition-all ${viewMode === 'cards' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-400'}`}>
              Cards
            </button>
          </div>
          <button onClick={() => setShowAdd(true)} className="btn-primary flex items-center gap-2 px-5 py-2.5 text-[15px]">
            <Plus className="w-4 h-4" />Add Contact
          </button>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="card flex items-center justify-center py-24">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500 mr-3" />
          <span className="text-[15px] text-gray-400 font-medium">Loading contacts...</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-24">
          <Users className="w-12 h-12 text-gray-200 mb-4" />
          <p className="text-[15px] text-gray-400 font-medium">{contacts.length === 0 ? 'No contacts yet. Add your first!' : 'No results found.'}</p>
        </div>
      ) : viewMode === 'cards' ? (
        /* Card View */
        <div className="grid grid-cols-3 gap-4">
          {filtered.map((contact, i) => (
            <div key={contact.id} className={`card card-hover hover-glow p-5 anim-enter delay-${Math.min(i % 6 + 1, 4)}`}>
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-11 h-11 rounded-xl bg-blue-50 flex items-center justify-center">
                    <span className="text-[15px] font-bold text-blue-600">{contact.name.charAt(0).toUpperCase()}</span>
                  </div>
                  <div>
                    <p className="text-[15px] font-bold text-gray-900">{contact.name}</p>
                    <p className="text-[13px] text-gray-400 font-mono">{contact.phone}</p>
                  </div>
                </div>
                <span className={`px-2 py-0.5 rounded-md text-[12px] font-semibold ${STATUS_STYLES[contact.status]}`}>
                  {STATUS_LABELS[contact.status]}
                </span>
              </div>
              {contact.company && (
                <p className="text-[13px] text-gray-500 mb-4 flex items-center gap-1.5">
                  <Building2 className="w-3 h-3" />{contact.company}
                </p>
              )}
              <div className="flex items-center gap-2 pt-3 border-t border-gray-100">
                <button
                  onClick={() => setCallTarget(contact)}
                  disabled={callingId === contact.id || !deviceReady}
                  className="flex-1 flex items-center justify-center gap-2 py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg text-[13px] font-semibold transition-all disabled:opacity-40"
                >
                  {callingId === contact.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PhoneCall className="w-3.5 h-3.5" />}
                  Call
                </button>
                <button onClick={() => deleteContact(contact.id)} className="p-2 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Table View */
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Name</th>
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Phone</th>
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Company</th>
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Status</th>
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Last Called</th>
                <th className="text-right px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((contact) => (
                <tr key={contact.id} className="row-hover group cursor-default">
                  <td className="px-6 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
                        <span className="text-[13px] font-bold text-blue-600">{contact.name.charAt(0).toUpperCase()}</span>
                      </div>
                      <span className="text-[15px] font-semibold text-gray-800">{contact.name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-3.5 text-[13px] text-gray-500 font-mono">{contact.phone}</td>
                  <td className="px-6 py-3.5 text-[15px] text-gray-500">{contact.company || '—'}</td>
                  <td className="px-6 py-3.5">
                    <span className={`px-2.5 py-0.5 rounded-md text-[12px] font-semibold ${STATUS_STYLES[contact.status]}`}>
                      {STATUS_LABELS[contact.status]}
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-[13px] text-gray-400">
                    {contact.last_called ? new Date(contact.last_called).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-6 py-3.5">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        onClick={() => setCallTarget(contact)}
                        disabled={callingId === contact.id || !deviceReady}
                        className="flex items-center gap-1.5 px-3.5 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-lg text-[13px] font-semibold transition-all disabled:opacity-40"
                      >
                        {callingId === contact.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PhoneCall className="w-3.5 h-3.5" />}
                        Call
                      </button>
                      <button onClick={() => deleteContact(contact.id)} className="p-2 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all opacity-0 group-hover:opacity-100">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Contact Modal */}
      {showAdd && createPortal(
        <div className="fixed inset-0 bg-gray-900/20 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-7 w-full max-w-md shadow-xl border border-gray-200 anim-modal">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-[17px] font-bold text-gray-900">New Contact</h3>
              <button onClick={() => setShowAdd(false)} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-all">
                <X className="w-4.5 h-4.5" />
              </button>
            </div>
            <div className="space-y-4">
              {[
                { label: 'Full Name', key: 'name', placeholder: 'John Doe', req: true },
                { label: 'Phone Number', key: 'phone', placeholder: '+1234567890', req: true },
                { label: 'Company', key: 'company', placeholder: 'Acme Corp' },
              ].map((f) => (
                <div key={f.key}>
                  <label className="block text-[13px] font-semibold text-gray-500 mb-1.5">
                    {f.label}{f.req && <span className="text-blue-500 ml-0.5">*</span>}
                  </label>
                  <input
                    type="text"
                    value={form[f.key]}
                    onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                    placeholder={f.placeholder}
                    className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-[15px] text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-blue-300 focus:ring-3 focus:ring-blue-100 transition-all"
                  />
                </div>
              ))}
              <div>
                <label className="block text-[13px] font-semibold text-gray-500 mb-1.5">Notes</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  placeholder="Any notes..."
                  rows={2}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-[15px] text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-blue-300 focus:ring-3 focus:ring-blue-100 transition-all resize-none"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowAdd(false)} className="flex-1 py-2.5 border border-gray-200 text-gray-500 rounded-xl text-[15px] font-semibold hover:bg-gray-50 transition-all text-center">
                Cancel
              </button>
              <button onClick={addContact} className="flex-1 py-2.5 btn-primary text-[15px] text-center">
                Add Contact
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Call Confirmation */}
      {callTarget && createPortal(
        <div className="fixed inset-0 bg-gray-900/20 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-7 w-full max-w-sm shadow-xl border border-gray-200 anim-modal">
            <h3 className="text-[17px] font-bold text-gray-900 mb-5">Start Call</h3>
            <div className="mb-6 flex items-center gap-4 p-4 bg-blue-50 rounded-xl">
              <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
                <PhoneCall className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-[15px] font-bold text-gray-900">{callTarget.name}</p>
                <p className="text-[15px] text-gray-500 font-mono">{callTarget.phone}</p>
              </div>
            </div>
            <p className="text-[13px] text-gray-400 mb-6">Call will use your browser mic and speakers.</p>
            <div className="flex gap-3">
              <button onClick={() => setCallTarget(null)} className="flex-1 py-2.5 border border-gray-200 text-gray-500 rounded-xl text-[15px] font-semibold hover:bg-gray-50 transition-all text-center">
                Cancel
              </button>
              <button onClick={confirmCall} className="flex-1 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-white rounded-xl text-[15px] font-semibold transition-all text-center shadow-md shadow-emerald-500/20 hover:shadow-emerald-500/30">
                <span className="flex items-center justify-center gap-2"><PhoneCall className="w-4 h-4" />Call Now</span>
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
