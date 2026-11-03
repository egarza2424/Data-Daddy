# DATA DADDY Pro — authentication development

This directory is an **unpublished development-only scaffold**. The live site's index.html and app.js are unchanged.

- `config.js` contains only the Supabase project URL and browser-safe publishable key.
- `auth.js` creates the Supabase browser client and exposes signup, login, logout, session and password-reset methods.
- The account interface, subscription database, server-enforced usage accounting, Stripe checkout, and premium gating are **not yet implemented**.
- Do **not** deploy a client-only paywall. The existing optimizer and comparison calculations run in browser JavaScript and would remain accessible without a backend enforcement design.
- Before testing confirmation and reset emails, add the exact URL of the eventual test page to Supabase Authentication > URL Configuration > Redirect URLs. The production URL currently configured does not cover arbitrary development preview URLs.
- Configure Row Level Security and narrowly scoped policies before adding any user profile or usage tables. Never commit database passwords or Supabase secret/service-role keys.
