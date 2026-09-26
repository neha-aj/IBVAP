import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './index.css';

// M25 hardening pinned the API/cookie contract to the "127.0.0.1" host --
// "localhost" and "127.0.0.1" are different *sites* for SameSite/CORS
// purposes, so a page loaded on "localhost" gets every fetch silently
// blocked ("Failed to fetch"), no matter how correct the backend is.
// Browser autocomplete/history keeps re-suggesting "localhost" regardless,
// so self-correct here, before React (and therefore before any fetch) ever
// runs, rather than relying on typing the right URL every time.
if (window.location.hostname === 'localhost') {
  window.location.replace(window.location.href.replace('localhost', '127.0.0.1'));
} else {
  createRoot(document.getElementById('root')).render(<StrictMode><BrowserRouter><App /></BrowserRouter></StrictMode>);
}
