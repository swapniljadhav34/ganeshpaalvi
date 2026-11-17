// Entry point: wires up data caching, SEO tags, routing, smooth scroll and site-wide state.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MotionConfig } from 'framer-motion';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { HelmetProvider } from 'react-helmet-async';
import { BrowserRouter } from 'react-router-dom';

// Bootstrap: ONLY the grid + utilities. All visual styling is ours.
import 'bootstrap/dist/css/bootstrap-grid.min.css';
import 'bootstrap/dist/css/bootstrap-utilities.min.css';
import './theme/tokens.css';
import './theme/global.css';

import App from './App';
import { SiteProvider } from './context/SiteContext';
import { SmoothScrollProvider } from './hooks/useSmoothScroll';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, err) => err?.status !== 404 && err?.status !== 429 && count < 2,
      refetchOnWindowFocus: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HelmetProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          {/* reducedMotion="user" makes every Framer animation respect the OS setting */}
          <MotionConfig reducedMotion="user">
            <SiteProvider>
              <SmoothScrollProvider>
                <App />
              </SmoothScrollProvider>
            </SiteProvider>
          </MotionConfig>
        </BrowserRouter>
      </QueryClientProvider>
    </HelmetProvider>
  </React.StrictMode>,
);
