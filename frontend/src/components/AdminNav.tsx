import { NavLink } from 'react-router-dom'

const adminNavClassName = ({ isActive }: { isActive: boolean }) =>
  isActive ? 'admin-tab admin-tab-active' : 'admin-tab'

export function AdminNav() {
  return (
    <nav className="admin-tabs" aria-label="Admin sections">
      <NavLink className={adminNavClassName} to="/admin" end>
        Overview
      </NavLink>
      <NavLink className={adminNavClassName} to="/admin/listings">
        Listings
      </NavLink>
      <NavLink className={adminNavClassName} to="/admin/reservations">
        Reservations
      </NavLink>
      <NavLink className={adminNavClassName} to="/admin/audit">
        Audit log
      </NavLink>
    </nav>
  )
}
