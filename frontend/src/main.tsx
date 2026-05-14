import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { AuthProvider } from './contexts/AuthContext'
import { UploadTasksProvider } from './contexts/UploadTasksContext'

const style = document.createElement('style')
style.textContent = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body, #root { height: 100%; overflow: hidden; }
  html, body {
    font-size: 14px;
    line-height: 1.6;
  }
  body {
    font-family: Inter, -apple-system, system-ui, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: #ffffff;
    color: rgba(0,0,0,0.95);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  button { font-family: inherit; font-size: 14px; cursor: pointer; border: none; background: none; }
  input, textarea, select { font-family: inherit; font-size: 14px; outline: none; }
  a { color: #0075de; text-decoration: none; }
  a:hover { text-decoration: underline; }
  ::selection { background: rgba(0,117,222,0.15); }
  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes msgIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  @keyframes dotBounce {
    0%, 80%, 100% { transform: translateY(0); }
    40%           { transform: translateY(-6px); }
  }
  ::-webkit-scrollbar { width: 5px; height: 5px; }
  ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.1); border-radius: 3px; }
  ::-webkit-scrollbar-track { background: transparent; }
  *:focus-visible { outline: none; }
`
document.head.appendChild(style)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <UploadTasksProvider>
        <App />
      </UploadTasksProvider>
    </AuthProvider>
  </React.StrictMode>,
)
