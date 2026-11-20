// True in the static-website build (manage.py export_static_site): no server, no prices.
export const STATIC_SITE = import.meta.env.VITE_STATIC === '1';
