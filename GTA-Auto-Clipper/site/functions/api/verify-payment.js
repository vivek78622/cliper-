import {
  constantTimeHexEqual, guideBytes, hmacHex, isPaymentCaptured, jsonResponse, razorpayAuth,
} from '../_lib/razorpay.mjs';

export async function onRequestPost({ request, env }) {
  if (!env.RAZORPAY_KEY_ID || !env.RAZORPAY_KEY_SECRET || !await guideBytes(env)) {
    return jsonResponse({ error: 'Guide delivery is being configured.' }, 503);
  }
  let body;
  try { body = await request.json(); } catch { return jsonResponse({ error: 'Invalid payment response.' }, 400); }
  const { razorpay_order_id: orderId, razorpay_payment_id: paymentId, razorpay_signature: signature } = body || {};
  if (![orderId, paymentId, signature].every((value) => typeof value === 'string' && value.length < 256)) {
    return jsonResponse({ error: 'Payment verification failed.' }, 400);
  }

  const expected = await hmacHex(env.RAZORPAY_KEY_SECRET, `${orderId}|${paymentId}`);
  if (!constantTimeHexEqual(expected, signature)) return jsonResponse({ error: 'Payment verification failed.' }, 400);

  try {
    const upstream = await fetch(`https://api.razorpay.com/v1/payments/${encodeURIComponent(paymentId)}`, {
      headers: { authorization: razorpayAuth(env) },
    });
    if (!upstream.ok || !isPaymentCaptured(await upstream.json(), orderId)) {
      return jsonResponse({ error: 'Payment is not confirmed yet. Contact support if your account was charged.' }, 402);
    }
  } catch {
    return jsonResponse({ error: 'Could not confirm payment. Please retry in a moment.' }, 502);
  }

  const expires = Math.floor(Date.now() / 1000) + 60 * 60 * 24;
  const payload = `${expires}.${crypto.randomUUID()}`;
  const token = `${payload}.${await hmacHex(env.RAZORPAY_KEY_SECRET, `guide-session|${payload}`)}`;
  return jsonResponse({ ok: true }, 200, {
    'set-cookie': `gta_guide=${token}; Max-Age=86400; Path=/api/download; Secure; HttpOnly; SameSite=Strict`,
  });
}
