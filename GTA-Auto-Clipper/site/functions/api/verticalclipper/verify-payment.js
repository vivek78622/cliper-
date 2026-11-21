import { constantTimeHexEqual, hmacHex, isPaymentCaptured, jsonResponse, razorpayAuth } from '../../_lib/razorpay.mjs';
import { VERTICAL_CLIPPER_AMOUNT_PAISE, sameOrigin, verticalClipperBytes } from '../../_lib/verticalclipper.mjs';

export async function onRequestPost({ request, env }) {
  if (!sameOrigin(request)) return jsonResponse({ error: 'Payment verification was not accepted.' }, 403);
  if (!env.RAZORPAY_KEY_ID || !env.RAZORPAY_KEY_SECRET || !await verticalClipperBytes(env)) {
    return jsonResponse({ error: 'Prompt delivery is being configured.' }, 503);
  }
  let body;
  try { body = await request.json(); } catch { return jsonResponse({ error: 'Invalid payment response.' }, 400); }
  const { razorpay_order_id: orderId, razorpay_payment_id: paymentId, razorpay_signature: signature } = body || {};
  if (![orderId, paymentId, signature].every((value) => typeof value === 'string' && value.length > 0 && value.length < 256)) {
    return jsonResponse({ error: 'Payment verification failed.' }, 400);
  }
  const expected = await hmacHex(env.RAZORPAY_KEY_SECRET, `${orderId}|${paymentId}`);
  if (!constantTimeHexEqual(expected, signature)) return jsonResponse({ error: 'Payment verification failed.' }, 400);
  try {
    const response = await fetch(`https://api.razorpay.com/v1/payments/${encodeURIComponent(paymentId)}`, { headers: { authorization: razorpayAuth(env) } });
    if (!response.ok || !isPaymentCaptured(await response.json(), orderId, VERTICAL_CLIPPER_AMOUNT_PAISE)) return jsonResponse({ error: 'Payment is not confirmed yet. Contact support if your account was charged.' }, 402);
  } catch {
    return jsonResponse({ error: 'Could not confirm payment. Please retry in a moment.' }, 502);
  }
  const expires = Math.floor(Date.now() / 1000) + 86400;
  const payload = `${expires}.${crypto.randomUUID()}`;
  const token = `${payload}.${await hmacHex(env.RAZORPAY_KEY_SECRET, `verticalclipper-session|${payload}`)}`;
  return jsonResponse({ ok: true }, 200, { 'set-cookie': `verticalclipper=${token}; Max-Age=86400; Path=/api/verticalclipper/download; Secure; HttpOnly; SameSite=Strict` });
}
