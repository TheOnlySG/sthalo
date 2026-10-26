import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { AppShell } from './components/AppShell'
import { AdminListingsPage } from './pages/AdminListingsPage'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { OwnerListingEditorPage } from './pages/OwnerListingEditorPage'
import { OwnerListingsPage } from './pages/OwnerListingsPage'
import { ProfilePage } from './pages/ProfilePage'
import { PublicListingPage } from './pages/PublicListingPage'
import { RegisterPage } from './pages/RegisterPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { VehiclesPage } from './pages/VehiclesPage'
import { VerifyEmailPage } from './pages/VerifyEmailPage'

const SearchPage = lazy(async () => {
  const module = await import('./pages/SearchPage')
  return { default: module.SearchPage }
})

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<HomePage />} />
            <Route path="login" element={<LoginPage />} />
            <Route path="register" element={<RegisterPage />} />
            <Route path="verify-email" element={<VerifyEmailPage />} />
            <Route path="reset-password" element={<ResetPasswordPage />} />
            <Route
              path="search"
              element={
                <Suspense
                  fallback={
                    <p className="status-message" role="status">
                      Loading the parking map…
                    </p>
                  }
                >
                  <SearchPage />
                </Suspense>
              }
            />
            <Route path="parking/:listingId" element={<PublicListingPage />} />
            <Route element={<RequireAuth />}>
              <Route path="account/profile" element={<ProfilePage />} />
              <Route path="account/vehicles" element={<VehiclesPage />} />
              <Route path="account/listings" element={<OwnerListingsPage />} />
              <Route path="account/listings/new" element={<OwnerListingEditorPage />} />
              <Route path="account/listings/:listingId/edit" element={<OwnerListingEditorPage />} />
              <Route path="admin/listings" element={<AdminListingsPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
