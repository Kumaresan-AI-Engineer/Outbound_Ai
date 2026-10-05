import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Plus, X, Loader2, Phone, Trash2, UserCog } from 'lucide-react';
import {
  getTwilioNumbers,
  getUsers,
  createTwilioNumber,
  assignTwilioNumber,
  updateTwilioNumber,
  deleteTwilioNumber,
} from '../api';

export default function TwilioNumbersPanel() {
  const [numbers, setNumbers] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ phone_number: '', label: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [openAssignFor, setOpenAssignFor] = useState(null); // number id, or null
  const [assignMenuPos, setAssignMenuPos] = useState(null); // {top, left} of the open menu
  const assignMenuRef = useRef(null);

  useEffect(() => {
    if (!openAssignFor) return;
    const close = () => { setOpenAssignFor(null); setAssignMenuPos(null); };
    const handleClickOutside = (e) => {
      if (assignMenuRef.current && !assignMenuRef.current.contains(e.target)) close();
    };
    document.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('scroll', close, true);
      window.removeEventListener('resize', close);
    };
  }, [openAssignFor]);

  const openAssignMenu = (e, numberId) => {
    if (openAssignFor === numberId) {
      setOpenAssignFor(null);
      setAssignMenuPos(null);
      return;
    }
    const rect = e.currentTarget.getBoundingClientRect();
    setAssignMenuPos({ top: rect.bottom + 6, left: rect.left });
    setOpenAssignFor(numberId);
  };

  const fetchAll = async () => {
    try {
      const [numbersData, usersData] = await Promise.all([
        getTwilioNumbers(),
        getUsers(),
      ]);
      setNumbers(numbersData);
      setUsers(usersData);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };
  useEffect(() => { fetchAll(); }, []);

  const addNumber = async () => {
    if (!form.phone_number) return;
    setSaving(true);
    setError('');
    try {
      const { ok, data } = await createTwilioNumber(form);
      if (!ok) { setError(data.detail || 'Could not add number'); return; }
      setForm({ phone_number: '', label: '' });
      setShowAdd(false);
      fetchAll();
    } catch (err) { console.error(err); }
    finally { setSaving(false); }
  };

  const toggleAssign = async (numberId, userId, isCurrentlyAssigned) => {
    await assignTwilioNumber(numberId, userId, isCurrentlyAssigned ? 'remove' : 'add');
    fetchAll();
  }

  const toggleActive = async (n) => {
    await updateTwilioNumber(n.id, { is_active: !n.is_active });
    fetchAll();
  };

  const deleteNumber = async (n) => {
    await deleteTwilioNumber(n.id);
    fetchAll();
  };

  const salesUsers = users.filter((u) => u.role === 'sales' && u.is_active);
  const activeAssignNumber = numbers.find((n) => n.id === openAssignFor) || null;

  return (
    <div className="py-8 anim-enter">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-[26px] font-extrabold text-gray-900">Twilio Numbers</h2>
          <p className="text-gray-400 text-[14px] mt-1">
            Manage the pool of outbound numbers and assign one to each salesperson
          </p>
        </div>
        <button onClick={() => { setForm({ phone_number: '', label: '' }); setError(''); setShowAdd(true); }} className="btn-primary flex items-center gap-2 px-5 py-2.5 text-[15px]">
          <Plus className="w-4 h-4" />Add Number
        </button>
      </div>

      {loading ? (
        <div className="card flex items-center justify-center py-24">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500 mr-3" />
          <span className="text-[15px] text-gray-400 font-medium">Loading numbers...</span>
        </div>
      ) : numbers.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-24">
          <Phone className="w-12 h-12 text-gray-200 mb-4" />
          <p className="text-[15px] text-gray-400 font-medium">No Twilio numbers yet. Add one to get started.</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Number</th>
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Label</th>
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Assigned To</th>
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Status</th>
                <th className="text-right px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {numbers.map((n) => (
                <tr key={n.id} className="row-hover group">
                  <td className="px-6 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
                        <Phone className="w-4 h-4 text-blue-600" />
                      </div>
                      <span className="text-[15px] font-semibold text-gray-800 font-mono">{n.phone_number}</span>
                    </div>
                  </td>
                  <td className="px-6 py-3.5 text-[14px] text-gray-500">{n.label || '—'}</td>
                  <td className="px-6 py-3.5">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {n.assigned_users.length === 0 && (
                        <span className="text-[13px] text-gray-300">Unassigned</span>
                      )}
                      {n.assigned_users.map((u) => (
                        <span
                          key={u.id}
                          className="flex items-center gap-1 pl-2.5 pr-1.5 py-1 bg-blue-50 text-blue-600 rounded-full text-[12px] font-semibold"
                        >
                          {u.name}
                          <button
                            onClick={() => toggleAssign(n.id, u.id, true)}
                            className="p-0.5 rounded-full text-blue-400 hover:text-blue-700 hover:bg-blue-100 transition-colors"
                          >
                            <X className="w-2.5 h-2.5" />
                          </button>
                        </span>
                      ))}
                      <button
                        onClick={(e) => openAssignMenu(e, n.id)}
                        className={`flex items-center gap-1 px-2 py-1 rounded-full text-[12px] font-semibold border border-dashed transition-all ${
                          openAssignFor === n.id
                            ? 'border-blue-300 bg-blue-50 text-blue-600'
                            : 'border-gray-200 text-gray-400 hover:border-blue-300 hover:text-blue-500 hover:bg-blue-50/50'
                        }`}
                      >
                        <UserCog className="w-3 h-3" />
                        Assign
                      </button>
                    </div>
                  </td>
                  <td className="px-6 py-3.5">
                    <button
                      onClick={() => toggleActive(n)}
                      className={`px-2.5 py-0.5 rounded-md text-[12px] font-semibold transition-all ${
                        n.is_active ? 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100' : 'bg-gray-100 text-gray-400 hover:bg-gray-200'
                      }`}
                    >
                      {n.is_active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td className="px-6 py-3.5">
                    <div className="flex items-center justify-end gap-1.5">
                      <button onClick={() => deleteNumber(n)} className="p-2 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all opacity-0 group-hover:opacity-100">
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

      {openAssignFor && assignMenuPos && activeAssignNumber && createPortal(
        <div
          ref={assignMenuRef}
          style={{ top: assignMenuPos.top, left: assignMenuPos.left }}
          className="fixed z-50 w-56 bg-white border border-gray-100 rounded-xl shadow-xl shadow-gray-200/60 p-1.5 anim-modal"
        >
          <p className="px-2.5 py-1.5 text-[11px] font-bold text-gray-400 uppercase tracking-wider">
            Assign salespeople
          </p>
          <div className="max-h-52 overflow-y-auto">
            {salesUsers.length === 0 ? (
              <p className="px-2.5 py-2 text-[13px] text-gray-300">No sales users yet</p>
            ) : salesUsers.map((u) => {
              const assigned = activeAssignNumber.assigned_users.some((au) => au.id === u.id);
              return (
                <label
                  key={u.id}
                  className="flex items-center gap-2.5 px-2.5 py-2 text-[13px] text-gray-700 hover:bg-gray-50 rounded-lg cursor-pointer transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={assigned}
                    onChange={() => toggleAssign(activeAssignNumber.id, u.id, assigned)}
                    className="w-3.5 h-3.5 rounded accent-blue-600 cursor-pointer"
                  />
                  <span className={assigned ? 'font-semibold text-gray-800' : ''}>{u.name}</span>
                </label>
              );
            })}
          </div>
        </div>,
        document.body
      )}

      {showAdd && createPortal(
        <div className="fixed inset-0 bg-gray-900/20 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-7 w-full max-w-md shadow-xl border border-gray-200 anim-modal">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-[17px] font-bold text-gray-900">Add Twilio Number</h3>
              <button onClick={() => setShowAdd(false)} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-all">
                <X className="w-4.5 h-4.5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-[13px] font-semibold text-gray-500 mb-1.5">Phone Number</label>
                <input
                  type="text"
                  value={form.phone_number}
                  onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
                  placeholder="+1XXXXXXXXXX"
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-[15px] text-gray-800 font-mono focus:outline-none focus:border-blue-300 focus:ring-3 focus:ring-blue-100 transition-all"
                />
              </div>
              <div>
                <label className="block text-[13px] font-semibold text-gray-500 mb-1.5">Label (optional)</label>
                <input
                  type="text"
                  value={form.label}
                  onChange={(e) => setForm({ ...form, label: e.target.value })}
                  placeholder="e.g. East Coast Sales"
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-[15px] text-gray-800 focus:outline-none focus:border-blue-300 focus:ring-3 focus:ring-blue-100 transition-all"
                />
              </div>
            </div>

            {error && (
              <p className="mt-4 text-[13px] text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</p>
            )}

            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowAdd(false)} className="flex-1 py-2.5 border border-gray-200 text-gray-500 rounded-xl text-[15px] font-semibold hover:bg-gray-50 transition-all text-center">
                Cancel
              </button>
              <button onClick={addNumber} disabled={saving} className="flex-1 py-2.5 btn-primary text-[15px] text-center disabled:opacity-40">
                <span className="flex items-center justify-center gap-2">
                  {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                  Add Number
                </span>
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
