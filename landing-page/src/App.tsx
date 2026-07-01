import Hero from './components/Hero'
import Features from './components/Features'
import SecurityBadge from './components/SecurityBadge'

function App() {
  return (
    <>
      <nav style={{ padding: '24px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div className="container flex-between">
          <div style={{ fontSize: '20px', fontWeight: 800, letterSpacing: '-0.5px' }}>
            PC Link<span style={{ color: 'var(--accent-blue)' }}>.</span>
          </div>
          <div style={{ display: 'flex', gap: '24px' }}>
            <a href="#features" style={{ color: 'var(--text-secondary)', textDecoration: 'none', fontWeight: 500 }}>Features</a>
            <a href="#security" style={{ color: 'var(--text-secondary)', textDecoration: 'none', fontWeight: 500 }}>Security</a>
          </div>
        </div>
      </nav>

      <main>
        <Hero />
        <div id="features">
          <Features />
        </div>
        <div id="security">
          <SecurityBadge />
        </div>
      </main>

      <footer style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '14px', borderTop: '1px solid rgba(255,255,255,0.05)', marginTop: '40px' }}>
        <div className="container">
          <p>© 2026 PC Link. Telepathy for your IDE.</p>
        </div>
      </footer>
    </>
  )
}

export default App
