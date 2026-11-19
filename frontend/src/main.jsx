// Entry point: wires up data caching, SEO tags, routing, smooth scroll and site-wide state.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import ReactDOM from 'react-dom/client';
import { HelmetProvider } from 'react-helmet-async';
import { BrowserRouter } from 'react-router-dom';

// Self-hosted fonts (no third-party requests, no render-blocking stylesheet).
import '@fontsource/instrument-serif/400.css';
import '@fontsource/instrument-serif/400-italic.css';
import '@fontsource/manrope/400.css';
import '@fontsource/manrope/500.css';
import '@fontsource/manrope/600.css';
import '@fontsource/manrope/700.css';
import './theme/tokens.css';
import './theme/global.css';

import App from './App';
import { SiteProvider } from './context/SiteContext';
import { I18nProvider } from './i18n/I18n';
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
          <SiteProvider>
            <I18nProvider>
              <SmoothScrollProvider>
                <App />
              </SmoothScrollProvider>
            </I18nProvider>
          </SiteProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </HelmetProvider>
  </React.StrictMode>,
);
