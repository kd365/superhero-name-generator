import { useState } from 'react'
import { generateName, getRemainingCalls } from './services/apiService'

function App() {
  const [seed, setSeed] = useState('')
  const [classicResult, setClassicResult] = useState(null)
  const [bedrockResult, setBedrockResult] = useState(null)
  const [classicLoading, setClassicLoading] = useState(false)
  const [bedrockLoading, setBedrockLoading] = useState(false)
  const [error, setError] = useState('')
  const [remaining, setRemaining] = useState(getRemainingCalls())

  const handleGenerate = async () => {
    if (!seed.trim()) {
      setError('Please enter a seed word')
      return
    }

    setError('')
    setClassicResult(null)
    setBedrockResult(null)
    setClassicLoading(true)
    setBedrockLoading(true)

    // Fire both requests simultaneously
    const classicPromise = generateName(seed, 'classic')
      .then(data => {
        setClassicResult(data)
        setClassicLoading(false)
      })
      .catch(err => {
        setClassicResult({ error: err.message })
        setClassicLoading(false)
      })

    const bedrockPromise = generateName(seed, 'bedrock')
      .then(data => {
        setBedrockResult(data)
        setBedrockLoading(false)
      })
      .catch(err => {
        setBedrockResult({ error: err.message })
        setBedrockLoading(false)
      })

    await Promise.all([classicPromise, bedrockPromise])
    setRemaining(getRemainingCalls())
  }

  const limitReached = remaining <= 0

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>SUPERHERO NAME GENERATOR</h1>
        <p style={styles.subtitle}>Classic ML vs Foundation Model — Side by Side</p>
      </header>

      <main style={styles.main}>
        <div style={styles.inputSection}>
          <label style={styles.label} htmlFor="seed">Enter a seed word</label>
          <div style={styles.inputRow}>
            <input
              id="seed"
              type="text"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !limitReached && handleGenerate()}
              placeholder="e.g. Shadow, Thunder, Nova..."
              style={styles.input}
              disabled={limitReached}
              maxLength={100}
            />
            <button
              onClick={handleGenerate}
              disabled={limitReached || classicLoading || bedrockLoading}
              style={{
                ...styles.button,
                ...(limitReached ? styles.buttonDisabled : {}),
              }}
            >
              {classicLoading || bedrockLoading ? 'Generating...' : limitReached ? 'Demo Limit Reached' : 'Generate'}
            </button>
          </div>
          <div style={styles.meta}>
            {remaining !== Infinity && (
              <span style={styles.remaining}>
                {remaining} generation{remaining !== 1 ? 's' : ''} remaining
              </span>
            )}
          </div>
          {error && <p style={styles.error}>{error}</p>}
        </div>

        <div style={styles.cards}>
          {/* Classic ML Card */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <h2 style={styles.cardTitle}>Classic ML</h2>
              <span style={styles.badge}>SageMaker</span>
            </div>
            <p style={styles.cardDesc}>TensorFlow LSTM trained on 9,000+ superhero names</p>

            <div style={styles.resultArea}>
              {classicLoading && (
                <div style={styles.loading}>
                  <div style={styles.spinner} />
                  <p>Generating with LSTM model...</p>
                  <p style={styles.coldStart}>First call may take 30-60s (cold start)</p>
                </div>
              )}
              {classicResult && !classicResult.error && (
                <div style={styles.result}>
                  <p style={styles.resultLabel}>Generated Name</p>
                  <p style={styles.heroName}>{classicResult.name}</p>
                </div>
              )}
              {classicResult?.error && (
                <p style={styles.resultError}>{classicResult.error}</p>
              )}
              {!classicLoading && !classicResult && (
                <p style={styles.placeholder}>Enter a seed word and click Generate</p>
              )}
            </div>

            <div style={styles.poweredBy}>
              Powered by TensorFlow LSTM on Amazon SageMaker
            </div>
          </div>

          {/* Bedrock Card */}
          <div style={styles.card}>
            <div style={styles.cardHeader}>
              <h2 style={styles.cardTitle}>Foundation Model</h2>
              <span style={{ ...styles.badge, background: 'linear-gradient(135deg, #f59e0b, #ef4444)' }}>Bedrock</span>
            </div>
            <p style={styles.cardDesc}>Amazon Nova Lite + Titan Image Generator</p>

            <div style={styles.resultArea}>
              {bedrockLoading && (
                <div style={styles.loading}>
                  <div style={{ ...styles.spinner, borderTopColor: '#f59e0b' }} />
                  <p>Generating with Bedrock...</p>
                </div>
              )}
              {bedrockResult && !bedrockResult.error && (
                <div style={styles.result}>
                  <p style={styles.resultLabel}>Generated Name</p>
                  <p style={styles.heroName}>{bedrockResult.name}</p>
                  <p style={styles.resultLabel}>Backstory</p>
                  <p style={styles.backstory}>{bedrockResult.backstory}</p>
                  {bedrockResult.imageData && (
                    <>
                      <p style={styles.resultLabel}>Hero Portrait</p>
                      <img
                        src={`data:image/png;base64,${bedrockResult.imageData}`}
                        alt={bedrockResult.name}
                        style={styles.heroImage}
                      />
                    </>
                  )}
                </div>
              )}
              {bedrockResult?.error && (
                <p style={styles.resultError}>{bedrockResult.error}</p>
              )}
              {!bedrockLoading && !bedrockResult && (
                <p style={styles.placeholder}>Enter a seed word and click Generate</p>
              )}
            </div>

            <div style={styles.poweredBy}>
              Powered by Amazon Nova Lite + Titan Image Generator on Bedrock
            </div>
          </div>
        </div>
      </main>

      <footer style={styles.footer}>
        <p>Built with React, AWS Lambda, SageMaker & Bedrock</p>
        <p>
          <a href="https://github.com/kd365/superhero-name-generator" style={styles.link} target="_blank" rel="noopener noreferrer">GitHub</a>
          {' · '}
          <a href="https://khilldata.com" style={styles.link} target="_blank" rel="noopener noreferrer">khilldata.com</a>
        </p>
      </footer>
    </div>
  )
}

const styles = {
  container: {
    maxWidth: 1100,
    margin: '0 auto',
    padding: '24px 20px',
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    textAlign: 'center',
    marginBottom: 32,
  },
  title: {
    fontFamily: "'Bangers', cursive",
    fontSize: 'clamp(2rem, 5vw, 3.5rem)',
    letterSpacing: '0.05em',
    background: 'linear-gradient(135deg, #fbbf24, #ef4444, #8b5cf6)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    marginBottom: 4,
  },
  subtitle: {
    color: '#94a3b8',
    fontSize: '1rem',
  },
  main: {
    flex: 1,
  },
  inputSection: {
    maxWidth: 600,
    margin: '0 auto 32px',
    textAlign: 'center',
  },
  label: {
    display: 'block',
    marginBottom: 8,
    fontSize: '0.95rem',
    color: '#cbd5e1',
    fontWeight: 500,
  },
  inputRow: {
    display: 'flex',
    gap: 12,
  },
  input: {
    flex: 1,
    padding: '12px 16px',
    fontSize: '1rem',
    border: '2px solid #475569',
    borderRadius: 10,
    background: 'rgba(255,255,255,0.05)',
    color: '#e2e8f0',
    outline: 'none',
    transition: 'border-color 0.2s',
  },
  button: {
    padding: '12px 28px',
    fontSize: '1rem',
    fontWeight: 600,
    border: 'none',
    borderRadius: 10,
    background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
    color: '#fff',
    cursor: 'pointer',
    transition: 'transform 0.1s, opacity 0.2s',
    whiteSpace: 'nowrap',
  },
  buttonDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  meta: {
    marginTop: 8,
    fontSize: '0.85rem',
  },
  remaining: {
    color: '#94a3b8',
  },
  error: {
    color: '#f87171',
    marginTop: 8,
    fontSize: '0.9rem',
  },
  cards: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
    gap: 24,
  },
  card: {
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 16,
    padding: 24,
    display: 'flex',
    flexDirection: 'column',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  cardTitle: {
    fontSize: '1.25rem',
    fontWeight: 700,
  },
  badge: {
    padding: '4px 12px',
    borderRadius: 20,
    fontSize: '0.75rem',
    fontWeight: 600,
    background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
    color: '#fff',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  cardDesc: {
    color: '#94a3b8',
    fontSize: '0.85rem',
    marginBottom: 16,
  },
  resultArea: {
    flex: 1,
    minHeight: 120,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  loading: {
    textAlign: 'center',
    color: '#94a3b8',
  },
  spinner: {
    width: 32,
    height: 32,
    border: '3px solid rgba(255,255,255,0.1)',
    borderTopColor: '#8b5cf6',
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
    margin: '0 auto 12px',
  },
  coldStart: {
    fontSize: '0.8rem',
    color: '#64748b',
    marginTop: 4,
  },
  result: {
    width: '100%',
  },
  resultLabel: {
    fontSize: '0.75rem',
    color: '#64748b',
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    marginBottom: 4,
    marginTop: 16,
  },
  heroName: {
    fontFamily: "'Bangers', cursive",
    fontSize: '1.8rem',
    color: '#fbbf24',
    letterSpacing: '0.03em',
  },
  backstory: {
    color: '#cbd5e1',
    fontSize: '0.95rem',
    lineHeight: 1.6,
  },
  heroImage: {
    width: '100%',
    maxWidth: 400,
    borderRadius: 12,
    marginTop: 8,
    border: '2px solid rgba(255,255,255,0.1)',
  },
  resultError: {
    color: '#f87171',
    fontSize: '0.9rem',
  },
  placeholder: {
    color: '#64748b',
    fontSize: '0.9rem',
    fontStyle: 'italic',
  },
  poweredBy: {
    marginTop: 16,
    paddingTop: 12,
    borderTop: '1px solid rgba(255,255,255,0.08)',
    fontSize: '0.75rem',
    color: '#64748b',
    textAlign: 'center',
  },
  footer: {
    textAlign: 'center',
    marginTop: 40,
    padding: '20px 0',
    borderTop: '1px solid rgba(255,255,255,0.08)',
    color: '#64748b',
    fontSize: '0.85rem',
  },
  link: {
    color: '#8b5cf6',
    textDecoration: 'none',
  },
}

export default App
