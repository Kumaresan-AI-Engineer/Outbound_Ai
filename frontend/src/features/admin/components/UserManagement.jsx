import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Plus, X, Loader2, UserCog, Trash2, Pencil, ShieldCheck, Phone } from 'lucide-react';
import { getUsers, createUser, updateUser, deleteUser as deleteUserRequest } from '../api';
import { useAuth } from '../../auth/context/authContextBase';

const ROLE_STYLES = {
  admin: 'bg-blue-50 text-blue-600',
  sales: 'bg-emerald-50 text-emerald-600',
};

const emptyForm = { name: '', email: '', password: '', role: 'sales' };

export default function UserManagement() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [editTarget, setEditTarget] = useState(null);
  const [editForm, setEditForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const fetchUsers = async () => {
    try {
      setUsers(await getUsers());
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };
  useEffect(() => { fetchUsers(); }, []);

  const addUser = async () => {
    if (!form.name || !form.email || !form.password) return;
    setSaving(true);
    setError('');
    try {
      const { ok, data } = await createUser(form);
      if (!ok) { setError(data.detail || 'Could not create user'); return; }
      setForm(emptyForm);
      setShowAdd(false);
      fetchUsers();
    } catch (err) { console.error(err); }
    finally { setSaving(false); }
  };

  const openEdit = (u) => {
    setEditTarget(u);
    setEditForm({ name: u.name, email: u.email, password: '', role: u.role });
    setError('');
  };

  const saveEdit = async () => {
    if (!editTarget) return;
    setSaving(true);
    setError('');
    try {
      const payload = { name: editForm.name, email: editForm.email, role: editForm.role };
      if (editForm.password) payload.password = editForm.password;
      const { ok, data } = await updateUser(editTarget.id, payload);
      if (!ok) { setError(data.detail || 'Could not update user'); return; }
      setEditTarget(null);
      fetchUsers();
    } catch (err) { console.error(err); }
    finally { setSaving(false); }
  };

  const toggleActive = async (u) => {
    await updateUser(u.id, { is_active: !u.is_active });
    fetchUsers();
  };

  const deleteUser = async (u) => {
    await deleteUserRequest(u.id);
    fetchUsers();
  };

  return (
    <div className="py-8 anim-enter">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-[26px] font-extrabold text-gray-900">Users</h2>
          <p className="text-gray-400 text-[14px] mt-1">Manage sales and admin accounts</p>
        </div>
        <button onClick={() => { setForm(emptyForm); setError(''); setShowAdd(true); }} className="btn-primary flex items-center gap-2 px-5 py-2.5 text-[15px]">
          <Plus className="w-4 h-4" />Add User
        </button>
      </div>

      {loading ? (
        <div className="card flex items-center justify-center py-24">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500 mr-3" />
          <span className="text-[15px] text-gray-400 font-medium">Loading users...</span>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Name</th>
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Email</th>
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Role</th>
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Assigned Number</th>
                <th className="text-left px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Status</th>
                <th className="text-right px-6 py-3.5 text-[12px] font-bold text-gray-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map((u) => (
                <tr key={u.id} className="row-hover group">
                  <td className="px-6 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
                        <UserCog className="w-4 h-4 text-blue-600" />
                      </div>
                      <span className="text-[15px] font-semibold text-gray-800">{u.name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-3.5 text-[14px] text-gray-500">{u.email}</td>
                  <td className="px-6 py-3.5">
                    <span className={`px-2.5 py-0.5 rounded-md text-[12px] font-semibold capitalize ${ROLE_STYLES[u.role]}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-[13px] text-gray-500 font-mono">
                    {u.assigned_numbers.length > 0 ? (
                      <div className="flex flex-col gap-0.5">
                        {u.assigned_numbers.map((n) => (
                          <span key={n.id} className="flex items-center gap-1.5">
                            <Phone className="w-3 h-3 text-gray-300" />{n.phone_number}
                          </span>
                        ))}
                      </div>
                    ) : '—'}
                  </td>
                  <td className="px-6 py-3.5">
                    <button
                      onClick={() => toggleActive(u)}
                      disabled={u.id === currentUser.id}
                      className={`px-2.5 py-0.5 rounded-md text-[12px] font-semibold transition-all disabled:opacity-40 ${
                        u.is_active ? 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100' : 'bg-gray-100 text-gray-400 hover:bg-gray-200'
                      }`}
                    >
                      {u.is_active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td className="px-6 py-3.5">
                    <div className="flex items-center justify-end gap-1.5">
                      <button onClick={() => openEdit(u)} className="p-2 text-gray-300 hover:text-blue-500 hover:bg-blue-50 rounded-lg transition-all opacity-0 group-hover:opacity-100">
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => deleteUser(u)}
                        disabled={u.id === currentUser.id}
                        className="p-2 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all opacity-0 group-hover:opacity-100 disabled:opacity-0"
                      >
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

      {(showAdd || editTarget) && createPortal(
        <div className="fixed inset-0 bg-gray-900/20 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-7 w-full max-w-md shadow-xl border border-gray-200 anim-modal">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-[17px] font-bold text-gray-900 flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-blue-500" />
                {editTarget ? 'Edit User' : 'New User'}
              </h3>
              <button onClick={() => { setShowAdd(false); setEditTarget(null); }} className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-all">
                <X className="w-4.5 h-4.5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-[13px] font-semibold text-gray-500 mb-1.5">Full Name</label>
                <input
                  type="text"
                  value={editTarget ? editForm.name : form.name}
                  onChange={(e) => editTarget ? setEditForm({ ...editForm, name: e.target.value }) : setForm({ ...form, name: e.target.value })}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-[15px] text-gray-800 focus:outline-none focus:border-blue-300 focus:ring-3 focus:ring-blue-100 transition-all"
                />
              </div>
              <div>
                <label className="block text-[13px] font-semibold text-gray-500 mb-1.5">Email</label>
                <input
                  type="email"
                  value={editTarget ? editForm.email : form.email}
                  onChange={(e) => editTarget ? setEditForm({ ...editForm, email: e.target.value }) : setForm({ ...form, email: e.target.value })}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-[15px] text-gray-800 focus:outline-none focus:border-blue-300 focus:ring-3 focus:ring-blue-100 transition-all"
                />
              </div>
              <div>
                <label className="block text-[13px] font-semibold text-gray-500 mb-1.5">
                  {editTarget ? 'New Password (leave blank to keep current)' : 'Password'}
                </label>
                <input
                  type="password"
                  value={editTarget ? editForm.password : form.password}
                  onChange={(e) => editTarget ? setEditForm({ ...editForm, password: e.target.value }) : setForm({ ...form, password: e.target.value })}
                  className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-[15px] text-gray-800 focus:outline-none focus:border-blue-300 focus:ring-3 focus:ring-blue-100 transition-all"
                />
              </div>
              <div>
                <label className="block text-[13px] font-semibold text-gray-500 mb-1.5">Role</label>
                <div className="flex gap-2">
                  {['sales', 'admin'].map((r) => (
                    <button
                      key={r}
                      type="button"
                      onClick={() => editTarget ? setEditForm({ ...editForm, role: r }) : setForm({ ...form, role: r })}
                      className={`px-3 py-1.5 rounded-lg text-[13px] font-semibold capitalize transition-all ${
                        (editTarget ? editForm.role : form.role) === r ? ROLE_STYLES[r] + ' ring-2 ring-offset-1 ring-blue-200' : 'bg-gray-50 text-gray-400 hover:bg-gray-100'
                      }`}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {error && (
              <p className="mt-4 text-[13px] text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">{error}</p>
            )}

            <div className="flex gap-3 mt-6">
              <button onClick={() => { setShowAdd(false); setEditTarget(null); }} className="flex-1 py-2.5 border border-gray-200 text-gray-500 rounded-xl text-[15px] font-semibold hover:bg-gray-50 transition-all text-center">
                Cancel
              </button>
              <button
                onClick={editTarget ? saveEdit : addUser}
                disabled={saving}
                className="flex-1 py-2.5 btn-primary text-[15px] text-center disabled:opacity-40"
              >
                <span className="flex items-center justify-center gap-2">
                  {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                  {editTarget ? 'Save Changes' : 'Create User'}
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
