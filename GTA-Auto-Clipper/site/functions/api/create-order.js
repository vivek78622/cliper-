import { GUIDE_AMOUNT_PAISE, guideBytes, jsonResponse, razorpayAuth } from '../_lib/razorpay.mjs';

export async function onRequestPost({ request, env }) {
  if (!env.RAZORPAY_KEY_ID || !env.RAZORPAY_KEY_SECRET || !await guideBytes(env)) {
    return jsonResponse({ error: 'Checkout is being configured. Please try again later.' }, 503);
  }

  let input;
  try { input = await request.json(); } catch { return jsonResponse({ error: 'Invalid request.' }, 400); }

  const receipt = `gta${crypto.randomUUID().replaceAll('-', '').slice(0, 32)}`;
  try {
    const upstream = await fetch('https://api.razorpay.com/v1/orders', {
      method: 'POST',
      headers: { authorization: razorpayAuth(env), 'content-type': 'application/json' },
      body: JSON.stringify({
        amount: GUIDE_AMOUNT_PAISE,
        currency: 'INR',
        receipt,
        notes: { product: 'gta-auto-clipper-guide' },
      }),
    });
    if (!upstream.ok) return jsonResponse({ error: 'Could not start checkout. Please try again.' }, 502);
    const order = await upstream.json();
    return jsonResponse({ keyId: env.RAZORPAY_KEY_ID, orderId: order.id, amount: GUIDE_AMOUNT_PAISE, currency: 'INR' });
  } catch {
    return jsonResponse({ error: 'Payment service is temporarily unavailable.' }, 502);
  }
}
