import React from "react";
import { LegalShell } from "../marketing/LegalShell";

export default function Privacy() {
  return (
    <LegalShell title="Privacy Policy" lastUpdated="6 May 2026">
      <h2>1. Who is the data controller?</h2>
      <p>
        Lay-Hounds, based in Durham, United Kingdom, is the controller of any personal data
        collected via this website (lay-hounds.co.uk) and via the licence-issuance process.
        Contact: <a href="mailto:hello@lay-hounds.co.uk">hello@lay-hounds.co.uk</a>.
      </p>

      <h2>2. What data we collect</h2>
      <ul>
        <li><strong>Email address</strong> — when you contact us, subscribe, or activate a licence.</li>
        <li><strong>Payment metadata</strong> — billing email, country, last-four card digits, transaction ID. Payments are processed by Stripe and PayPal; we never see your full card number.</li>
        <li><strong>Licence key</strong> — issued on successful payment and tied to your email.</li>
        <li><strong>Anonymous usage analytics</strong> on this marketing site only (page views, source). The simulator app you self-host does not phone home.</li>
      </ul>

      <h2>3. What we explicitly do NOT collect</h2>
      <ul>
        <li>Your Betfair username, password, or App Key — these live only in your self-hosted .env file.</li>
        <li>Your bet results, P&amp;L history, or session data — this stays on your VPS, in your MongoDB.</li>
        <li>Card numbers, CVV, or any other payment-card data.</li>
      </ul>

      <h2>4. Why we process your data</h2>
      <ul>
        <li>To deliver the Service you've paid for (lawful basis: contract).</li>
        <li>To send transactional emails (licence keys, receipts, refund confirmations).</li>
        <li>To respond to support requests.</li>
        <li>To meet our UK tax / anti-fraud obligations (lawful basis: legal obligation).</li>
      </ul>

      <h2>5. Who we share data with</h2>
      <ul>
        <li><strong>Stripe</strong> (Stripe Payments UK Ltd) — payment processing.</li>
        <li><strong>PayPal</strong> (PayPal Europe S.à r.l.) — payment processing.</li>
        <li><strong>Email provider</strong> — for transactional emails only.</li>
      </ul>
      <p>We never sell your data. We never share it with marketing partners.</p>

      <h2>6. How long we keep it</h2>
      <p>
        Active-customer data: for the lifetime of your account. After cancellation we keep
        billing records for 6 years to comply with UK tax law, then delete them.
        Support emails are retained for 2 years.
      </p>

      <h2>7. Your rights under UK GDPR</h2>
      <p>You have the right to:</p>
      <ul>
        <li>access the personal data we hold about you;</li>
        <li>have inaccurate data corrected;</li>
        <li>have your data erased (subject to our tax-record retention obligation);</li>
        <li>object to or restrict processing;</li>
        <li>data portability (we'll export your data to JSON on request);</li>
        <li>complain to the UK Information Commissioner's Office (ICO) at <a href="https://ico.org.uk" target="_blank" rel="noreferrer">ico.org.uk</a>.</li>
      </ul>
      <p>
        To exercise any of these rights, email <a href="mailto:hello@lay-hounds.co.uk">hello@lay-hounds.co.uk</a>.
      </p>

      <h2>8. Cookies</h2>
      <p>
        This marketing site uses minimal cookies: a session cookie for the contact form and
        a privacy-respecting analytics cookie. We do not use ad-tracking cookies. The
        self-hosted simulator app uses no cookies at all.
      </p>

      <h2>9. International transfers</h2>
      <p>
        Stripe and PayPal may process payment data in the EU and US under standard contractual
        clauses approved by the UK ICO.
      </p>

      <h2>10. Changes</h2>
      <p>
        We'll post updates here with a new "last updated" date. Material changes will be
        emailed to active subscribers.
      </p>
    </LegalShell>
  );
}
