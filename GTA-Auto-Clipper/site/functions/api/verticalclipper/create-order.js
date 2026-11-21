import { jsonResponse, razorpayAuth } from '../../_lib/razorpay.mjs';
import { VERTICAL_CLIPPER_AMOUNT_PAISE, sameOrigin, verticalClipperBytes } from '../../_lib/verticalclipper.mjs';

export async function onRequestPost({ request, env }) {
  if (!sameOrigin(request)) return jsonResponse({ error: 'Checkout request was not accepted.' }, 403);
  if (!env.RAZORPAY_KEY_ID || !env.RAZORPAY_KEY_SECRET || !await verticalClipperBytes(env)) {
    return jsonResponse({ error: 'Checkout is being configured. Please try again later.' }, 503);
  }
  const receipt = `vclip${crypto.randomUUID().replaceAll('-', '').slice(0, 28)}`;
  try {
    const response = await fetch('https://api.razorpay.com/v1/orders', {
      method: 'POST',
      headers: { authorization: razorpayAuth(env), 'content-type': 'application/json' },
      body: JSON.stringify({ amount: VERTICAL_CLIPPER_AMOUNT_PAISE, currency: 'INR', receipt, notes: { product: 'gta-face-clipper-complete-toolkit' } }),
    });
    if (!response.ok) return jsonResponse({ error: 'Could not start checkout. Please try again.' }, 502);
    const order = await response.json();
    if (order.amount !== VERTICAL_CLIPPER_AMOUNT_PAISE || order.currency !== 'INR') return jsonResponse({ error: 'Payment order details did not match.' }, 502);
    return jsonResponse({ keyId: env.RAZORPAY_KEY_ID, orderId: order.id, amount: VERTICAL_CLIPPER_AMOUNT_PAISE, currency: 'INR' });
  } catch {
    return jsonResponse({ error: 'Payment service is temporarily unavailable.' }, 502);
  }
}
