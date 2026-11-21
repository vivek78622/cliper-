import { jsonResponse } from '../../_lib/razorpay.mjs';
import { verticalClipperBytes } from '../../_lib/verticalclipper.mjs';

export async function onRequestGet({ env }) {
  const enabled = Boolean(env.RAZORPAY_KEY_ID && env.RAZORPAY_KEY_SECRET && await verticalClipperBytes(env));
  return jsonResponse({ enabled, keyId: enabled ? env.RAZORPAY_KEY_ID : null, mode: env.PAYMENT_MODE === 'live' ? 'live' : 'test' });
}
