# Supabase Auth setup

The website remains static on the existing Vercel setup. Auth is optional: guests
can use Data Analyzer and Health Prediction. No prediction history table is created
and no health input is sent to Supabase in this change.

## Configure the project

1. Create a Supabase project. From its Connect dialog / API settings, copy the
   Project URL and **publishable key** (recommended), or the legacy **anon** key.
   See [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys).
2. Set both values in `supabase-config.js`:

   ```js
   const SUPABASE_URL = "YOUR_SUPABASE_URL";
   const SUPABASE_ANON_KEY = "YOUR_SUPABASE_ANON_KEY";
   ```

   `SUPABASE_ANON_KEY` accepts either public key format. Browser credentials are
   public by design. Never put service_role, secret keys, database passwords,
   signing keys, or SMTP credentials in this file. The client also rejects
   non-public key formats before loading the SDK.
3. In Authentication settings, enable the Email provider and email/password
   signups. Keep email confirmation enabled. Set the minimum password length to
   at least 8 characters; frontend validation is not a substitute for server rules.
   [Password security](https://supabase.com/docs/guides/auth/password-security).
4. In Authentication → URL Configuration, set **Site URL** to
   `https://data-science-portfolio-steel.vercel.app`. Add these exact **Redirect URLs**:

   ```text
   https://data-science-portfolio-steel.vercel.app/login.html?confirmed=1
   https://data-science-portfolio-steel.vercel.app/reset-password.html
   ```

   Confirmation and reset emails always return to the public website, including
   registrations submitted from Live Server. The `confirmed=1` flag displays a
   success notice on login and is removed without reloading; it does not create
   an authenticated session. Existing login return-page behavior is unchanged. See
   [Redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls).
5. Configure **Custom SMTP** in Supabase for sending confirmation/recovery emails
   to public users. Supabase's default email service is intended for project-team
   testing and restricts recipients. SMTP credentials belong only in Supabase's
   Dashboard. See [Custom SMTP](https://supabase.com/docs/guides/auth/auth-smtp).
6. Use the standard confirmation and reset email templates with the Supabase
   confirmation link (`{{ .ConfirmationURL }}`). If you customized templates,
   ensure they honor the requested redirect URL. The reset flow is a browser
   implicit recovery flow; do not replace it with a server `/auth/confirm` route
   that this static project does not have.

No Vercel environment variables, npm build, server endpoints, rewrites, or deploy
configuration changes are needed. No commit, push, deployment, external user
registration or email sending is performed automatically.

## Test manually with Live Server

Open `index.html` using Live Server, not `file://`.

- **Before configuration:** account pages show the configuration message and
  disabled request buttons. You can test form validation on login/register/forgot
  pages; no SDK or Auth requests are sent. Public tools keep working.
- **Register:** use an email you control, a password of at least 8 characters and
  matching confirmation. Check the confirmation email and follow its link. An
  account created with an immediate session returns to the requested public page.
  Obfuscated existing-account responses get neutral wording; only explicit
  provider errors get the already-registered message.
- **Login:** try `login.html?return=health-prediction.html`. Successful login returns
  there. Refresh: navbar shows email / logout. Wrong email/password share one
  message. Outside-domain returns and auth-page loops fall back to `index.html`.
- **Logout:** click the navbar button. Email disappears immediately on success;
  public tools remain accessible. This signs out the current browser session.
- **Forgot/reset:** submit an email; the page uses neutral wording. Open the email
  recovery link. The reset form activates only after the SDK reports
  `PASSWORD_RECOVERY`, and `getUser()` verifies the session before `updateUser()`.
  Opening reset directly, with a normal saved login, or with an expired link does
  not authorize a password update. After success, sign in with the new password.
- **UX:** test empty fields, malformed email, short register/reset passwords and
  mismatched confirmation. Errors are inline; requests disable the form and reject
  double submit. Password toggles are keyboard-accessible. Check 320/390/768/1440px.

Actual signup/email/recovery integration must be tested after URL/key and Dashboard
settings are supplied. Local automated tests use a Supabase SDK mock only inside
the test harness, never a fake production auth implementation.

## Shared user access for future modules

Include `supabase-config.js` followed by `auth.js`, both with `defer`. Then:

```js
await window.PortfolioAuth.ready;
const user = window.PortfolioAuth.getUser();
if (user) {
    // user.id is Supabase's user UUID; user.email is a display value.
}
window.addEventListener("portfolio:authchange", event => {
    const user = event.detail.user; // null when signed out
});
```

Supabase manages sessions; app code does not store passwords or manufacture IDs.
`getUser()` exposes current browser state for UI, not server authorization. Future
`health_prediction_history.user_id` access must be enforced by RLS using
`auth.uid() = user_id`. Do not use email or hidden buttons as an authorization rule.
Data Analyzer files and all Health Prediction model/inference code remain unchanged.

## Automated tests

```powershell
python tests/test_auth.py
python tests/test_health_prediction.py
```

Tests use a temporary local HTTP server and Edge/Chrome/Chromium headless. No real
account or email is created. Profiles/test pages are temporary. Set
`HEALTH_TEST_BROWSER` to the browser executable if it is installed elsewhere.
