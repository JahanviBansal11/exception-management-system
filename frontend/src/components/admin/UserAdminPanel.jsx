import React from 'react'

export function UserAdminPanel({
  adminSearch, setAdminSearch,
  adminRoleFilter, setAdminRoleFilter,
  adminStatusFilter, setAdminStatusFilter,
  adminSortKey, setAdminSortKey,
  adminPageSize, setAdminPageSize,
  adminRoles,
  totalAdminPages,
  adminPage, setAdminPage,
  pagedAdminUsers,
  adminError,
  updateManagedUser,
  updateAdminUserLocal,
  newUserForm, setNewUserForm,
  createManagedUser,
  loadingAdminUsers
}) {
  return (
    <>
      <div className="panel" style={{ marginBottom: '20px' }}>
        <div className="panel-header">
          <h3>User Directory Filters</h3>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
          <div>
            <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Search Username/Email/Role</label>
            <input
              type="text"
              placeholder="Search..."
              value={adminSearch}
              onChange={(e) => setAdminSearch(e.target.value)}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Filter by Role</label>
            <select
              value={adminRoleFilter}
              onChange={(e) => setAdminRoleFilter(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="all">All Roles</option>
              {adminRoles.map(role => <option key={role} value={role}>{role}</option>)}
            </select>
          </div>
          <div>
            <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Filter by Status</label>
            <select
              value={adminStatusFilter}
              onChange={(e) => setAdminStatusFilter(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="all">All Statuses</option>
              <option value="active">Active Only</option>
              <option value="inactive">Inactive Only</option>
            </select>
          </div>
          <div>
            <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Sort By</label>
            <select
              value={adminSortKey}
              onChange={(e) => setAdminSortKey(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="username_asc">Username (A-Z)</option>
              <option value="username_desc">Username (Z-A)</option>
              <option value="role_asc">Role (A-Z)</option>
              <option value="active_first">Active First</option>
              <option value="inactive_first">Inactive First</option>
            </select>
          </div>
          <div>
            <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Page Size</label>
            <select
              value={adminPageSize}
              onChange={(e) => setAdminPageSize(Number(e.target.value))}
              style={{ width: '100%' }}
            >
              <option value={10}>10 per page</option>
              <option value={25}>25 per page</option>
              <option value={50}>50 per page</option>
              <option value={100}>100 per page</option>
            </select>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
        <div className="panel" style={{ flex: '1' }}>
          <div className="panel-header">
            <h3>Managed Users</h3>
            <div className="meta">
              Page {Math.min(adminPage, totalAdminPages)} of {totalAdminPages}
            </div>
          </div>
          {adminError && (
            <div style={{ margin: '0 1.5rem', padding: '0.75rem 1rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '0.375rem', color: '#991b1b', fontSize: '0.875rem' }}>
              {adminError}
            </div>
          )}
          {loadingAdminUsers ? (
            <div className="meta" style={{ padding: '1rem' }}>Loading users...</div>
          ) : (
            <>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #e5e7eb', backgroundColor: '#f9fafb' }}>
                      <th style={{ padding: '10px', textAlign: 'left', fontWeight: 'bold' }}>ID</th>
                      <th style={{ padding: '10px', textAlign: 'left', fontWeight: 'bold' }}>Username</th>
                      <th style={{ padding: '10px', textAlign: 'left', fontWeight: 'bold' }}>Email</th>
                      <th style={{ padding: '10px', textAlign: 'left', fontWeight: 'bold' }}>Role</th>
                      <th style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold' }}>Active</th>
                      <th style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagedAdminUsers.map((userItem) => (
                      <tr key={userItem.id} style={{ borderBottom: '1px solid #e5e7eb', backgroundColor: '#fff' }}>
                        <td style={{ padding: '10px', fontWeight: 'bold' }}>{userItem.id}</td>
                        <td style={{ padding: '10px' }}>{userItem.username}</td>
                        <td style={{ padding: '10px' }}>
                          <input
                            type="email"
                            value={userItem.email || ''}
                            onChange={(e) => updateAdminUserLocal(userItem.id, { email: e.target.value })}
                            style={{ padding: '4px', fontSize: '0.8rem', width: '100%' }}
                          />
                        </td>
                        <td style={{ padding: '10px' }}>
                          <select
                            value={(userItem.roles && userItem.roles[0]) || ''}
                            onChange={(e) => updateAdminUserLocal(userItem.id, { roles: [e.target.value] })}
                            style={{ padding: '4px', fontSize: '0.8rem', width: '100%' }}
                          >
                            <option value="">No Role</option>
                            {adminRoles.map(r => <option key={r} value={r}>{r}</option>)}
                          </select>
                        </td>
                        <td style={{ padding: '10px', textAlign: 'center' }}>
                          <input
                            type="checkbox"
                            checked={userItem.is_active}
                            onChange={(e) => updateAdminUserLocal(userItem.id, { is_active: e.target.checked })}
                          />
                        </td>
                        <td style={{ padding: '10px', textAlign: 'center' }}>
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '0.75rem', width: 'auto' }}
                            onClick={() => updateManagedUser(userItem)}
                          >
                            Save
                          </button>
                        </td>
                      </tr>
                    ))}
                    {pagedAdminUsers.length === 0 && (
                      <tr>
                        <td colSpan="6" style={{ padding: '10px', textAlign: 'center', color: '#64748b' }}>
                          No users match the current filters.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              {totalAdminPages > 1 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => setAdminPage(Math.max(1, adminPage - 1))}
                    disabled={adminPage <= 1}
                    style={{ width: 'auto' }}
                  >
                    ← Previous
                  </button>
                  <span className="meta">
                    Page {adminPage} of {totalAdminPages}
                  </span>
                  <button
                    className="btn btn-secondary"
                    onClick={() => setAdminPage(Math.min(totalAdminPages, adminPage + 1))}
                    disabled={adminPage >= totalAdminPages}
                    style={{ width: 'auto' }}
                  >
                    Next →
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        <div className="panel" style={{ width: '300px', flexShrink: 0 }}>
          <div className="panel-header">
            <h3>Create New User</h3>
          </div>
          <form onSubmit={createManagedUser} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Username *</label>
              <input
                type="text"
                required
                value={newUserForm.username}
                onChange={(e) => setNewUserForm({ ...newUserForm, username: e.target.value })}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Password *</label>
              <input
                type="password"
                required
                value={newUserForm.password}
                onChange={(e) => setNewUserForm({ ...newUserForm, password: e.target.value })}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Email</label>
              <input
                type="email"
                value={newUserForm.email}
                onChange={(e) => setNewUserForm({ ...newUserForm, email: e.target.value })}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label className="meta" style={{ display: 'block', marginBottom: '4px' }}>Initial Role</label>
              <select
                value={newUserForm.role}
                onChange={(e) => setNewUserForm({ ...newUserForm, role: e.target.value })}
                style={{ width: '100%' }}
              >
                {adminRoles.map(role => <option key={role} value={role}>{role}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                type="checkbox"
                id="new_user_active"
                checked={newUserForm.is_active}
                onChange={(e) => setNewUserForm({ ...newUserForm, is_active: e.target.checked })}
              />
              <label className="meta" htmlFor="new_user_active">Active Account</label>
            </div>
            <button type="submit" className="btn" style={{ marginTop: '8px' }}>
              Create User
            </button>
          </form>
        </div>
      </div>
    </>
  )
}
