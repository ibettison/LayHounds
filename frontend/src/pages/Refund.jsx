import React from "react";
import { LegalShell } from "../marketing/LegalShell";

export default function Refund() {
  return (
    <LegalShell title="Refund Policy" lastUpdated="6 May 2026">
      <h2>14-day money-back guarantee</h2>
      <p>
        We want you to be confident in the Service. If Lay-Hounds isn't a fit, you can request
        a full refund of your <strong>first</strong> Live Unlock payment within
        <strong> 14 calendar days</strong> of the charge. No forms, no questions, no win-back call.
      </p>

      <h2>How to request a refund</h2>
      <p>
        Email <a href="mailto:hello@lay-hounds.co.uk">hello@lay-hounds.co.uk</a> from the address
        you used to subscribe, including either:
      </p>
      <ul>
        <li>your Stripe receipt number, or</li>
        <li>your PayPal transaction ID.</li>
      </ul>
      <p>
        Refunds are issued back to the original payment method within 5 business days.
        Your licence key is deactivated at the same time and you revert to the free Simulator.
      </p>

      <h2>Renewals after the first 14 days</h2>
      <p>
        Subscription renewals (after the initial 14 days) are non-refundable, but you can
        cancel future renewals at any time and you keep Live access until the end of the
        current paid period.
      </p>

      <h2>Pro-rata refunds</h2>
      <p>
        We will issue pro-rata refunds in the following exceptional cases:
      </p>
      <ul>
        <li>If we permanently shut down the Service.</li>
        <li>If a verified bug introduced by us prevents you from using Live mode for more than 7 consecutive days.</li>
      </ul>

      <h2>Chargebacks</h2>
      <p>
        Please contact us before raising a chargeback — we will almost always resolve the issue
        faster and more fully than your bank can. Chargebacks raised without prior contact may
        result in permanent suspension of future purchases.
      </p>

      <h2>What we cannot refund</h2>
      <ul>
        <li>Losses incurred while betting — Lay-Hounds is a tool, not a fund manager.</li>
        <li>Costs of your VPS, domain, or third-party services (Stripe fees, etc.).</li>
        <li>Subscriptions paid by gift card or vouchers (where applicable).</li>
      </ul>

      <h2>Statutory rights</h2>
      <p>
        Nothing in this policy affects your statutory rights as a consumer under the UK
        Consumer Rights Act 2015 or the Consumer Contracts Regulations 2013.
      </p>
    </LegalShell>
  );
}
