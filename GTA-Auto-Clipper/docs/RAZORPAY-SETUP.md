# Razorpay setup for the guide

The Cloudflare Pages Functions keep `RAZORPAY_KEY_SECRET` server-side. The browser receives only the key ID when checkout is enabled. The server fixes the order amount at ₹149, checks the Razorpay signature, fetches the payment, confirms the captured amount/order, then issues a short-lived signed download cookie.

The product ZIP, containing the PDF and prompt, is stored in `GUIDE_CONTENT_GZIP_BASE64`. Keep the archive outside the public source repository and static site.

## Add the guide secret

From the repository's `site` directory, compress the local private guide and pipe it directly to Wrangler so it is not printed in the terminal:

```powershell
$packedGuide = node -e "const fs=require('node:fs');const z=require('node:zlib');process.stdout.write(z.gzipSync(fs.readFileSync('../private/GTA-Clipping-Guide-Premium.zip')).toString('base64'))"
$packedGuide | npx wrangler pages secret put GUIDE_CONTENT_GZIP_BASE64 --project-name gta-auto-clipper
Remove-Variable packedGuide
```

The local `private/GTA-Clipping-Guide-Premium.zip` file is ignored by Git. Keep it backed up privately.

## Enable test checkout

Generate Razorpay **Test Mode** keys from the merchant dashboard. Add them as Pages secrets:

```powershell
npx wrangler pages secret put RAZORPAY_KEY_ID --project-name gta-auto-clipper
npx wrangler pages secret put RAZORPAY_KEY_SECRET --project-name gta-auto-clipper
```

Use the test key ID and secret when Wrangler prompts; never add either to source control. Test the complete successful and failed checkout flows on the Pages URL. Confirm an unpaid/failed order cannot download the guide, and a captured ₹149 test order can. The test-mode label is shown by the site.

To switch to live checkout, only after the Razorpay account is approved and the business details/policies match the merchant profile, replace both secrets with Live Mode keys and set the Pages secret `PAYMENT_MODE` to `live`. Deploy the current site revision after changing production secrets if Cloudflare requires a new deployment for the environment update.

## Merchant information required on the site

Before requesting merchant verification or accepting live money, replace the seller and contact placeholders in `site/index.html`, `site/terms.html`, `site/privacy.html`, and `site/refunds.html`. State the actual refund/cancellation terms and delivery method. Keep pricing, the digital guide description, customer support, and merchant dashboard details consistent.
