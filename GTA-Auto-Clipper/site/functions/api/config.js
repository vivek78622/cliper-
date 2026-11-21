import { jsonResponse, guideBytes } from '../_lib/razorpay.mjs';

export async function onRequestGet({ env }) {
  const configured = Boolean(env.RAZORPAY_KEY_ID && env.RAZORPAY_KEY_SECRET && await guideBytes(env));
  return jsonResponse({
    enabled: configured,
    keyId: configured ? env.RAZORPAY_KEY_ID : null,
    mode: env.PAYMENT_MODE === 'live' ? 'live' : 'test',
  });
}
