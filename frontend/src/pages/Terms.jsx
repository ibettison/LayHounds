import React from "react";
import { LegalShell } from "../marketing/LegalShell";

export default function Terms() {
  return (
    <LegalShell title="Terms of Service" lastUpdated="6 May 2026">
      <h2>1. Who we are</h2>
      <p>
        These Terms of Service ("<strong>Terms</strong>") govern your use of the Lay-Hounds
        software ("<strong>Service</strong>"), provided by Lay-Hounds, an unincorporated trading
        name based in Durham, United Kingdom ("<strong>we</strong>", "<strong>us</strong>").
        By installing or using the Service you agree to these Terms.
      </p>

      <h2>2. What the Service is</h2>
      <p>
        Lay-Hounds is a self-hosted strategy-testing tool for greyhound lay-betting on the
        Betfair exchange. The Service includes (a) a free Simulator that operates on
        synthetic race data, and (b) a paid Live Unlock that enables Paper-Live and Live
        modes connecting to your own Betfair account via the official Betfair API.
      </p>

      <h2>3. Eligibility</h2>
      <p>
        You must be at least 18 years old and legally permitted to gamble in your jurisdiction.
        You are solely responsible for ensuring your use of the Service complies with local law.
      </p>

      <h2>4. Your Betfair account &amp; credentials</h2>
      <p>
        Live and Paper-Live modes require you to enter your own Betfair App Key and credentials
        into your self-hosted installation. We never receive or store these credentials.
        You are responsible for keeping your server, credentials and Betfair account secure.
      </p>

      <h2>5. Subscription &amp; billing</h2>
      <ul>
        <li>The Live Unlock costs £19.99 per month, billed via Stripe or PayPal.</li>
        <li>Subscriptions auto-renew monthly until cancelled. You can cancel at any time from your billing portal.</li>
        <li>On cancellation you retain Live access until the end of the current paid period, then revert to the free Simulator.</li>
      </ul>

      <h2>6. Refunds</h2>
      <p>
        See our <a href="/refund">Refund Policy</a>. We offer a 14-day money-back guarantee on
        the first payment of any new subscription.
      </p>

      <h2>7. No financial advice. No guarantee of profit.</h2>
      <p>
        The Service is a software tool. Nothing in the Service constitutes financial, investment
        or gambling advice. <strong>Past performance, simulated or real, does not guarantee
        future results.</strong> You alone are responsible for any bets you place and any losses
        you incur. We are not a regulated betting operator and we never hold or handle your
        betting funds.
      </p>

      <h2>8. Acceptable use</h2>
      <p>You agree not to:</p>
      <ul>
        <li>resell, sublicense, or redistribute the Service without our written permission;</li>
        <li>reverse-engineer the licence-key validation;</li>
        <li>use the Service to violate Betfair's terms or any applicable law;</li>
        <li>share a single Live Unlock licence across multiple installations or users.</li>
      </ul>

      <h2>9. Intellectual property</h2>
      <p>
        All source code, brand assets and documentation are the property of Lay-Hounds and
        protected by UK copyright. Your subscription grants you a personal, non-transferable
        licence to run one self-hosted instance for your own use.
      </p>

      <h2>10. Limitation of liability</h2>
      <p>
        To the maximum extent permitted by law, our total liability to you for any claim
        arising from the Service is limited to the amount you have paid us in the 12 months
        preceding the claim. We are not liable for any betting losses, missed opportunities,
        Betfair downtime, or third-party service interruptions.
      </p>

      <h2>11. Termination</h2>
      <p>
        We may suspend or terminate your licence if you breach these Terms, with refund pro-rata
        for any unused paid time. You may stop using the Service at any time.
      </p>

      <h2>12. Changes to these Terms</h2>
      <p>
        We may update these Terms from time to time. Material changes will be announced via
        email to active subscribers and posted on this page with a new "last updated" date.
      </p>

      <h2>13. Governing law</h2>
      <p>
        These Terms are governed by the laws of England and Wales. Disputes will be resolved
        in the courts of England and Wales.
      </p>

      <h2>14. Contact</h2>
      <p>
        Questions? Email <a href="mailto:hello@lay-hounds.co.uk">hello@lay-hounds.co.uk</a> or
        write to us at: Lay-Hounds, Durham, United Kingdom.
      </p>
    </LegalShell>
  );
}
