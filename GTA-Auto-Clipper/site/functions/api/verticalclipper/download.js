import { constantTimeHexEqual, hmacHex } from '../../_lib/razorpay.mjs';
import { verticalClipperBytes } from '../../_lib/verticalclipper.mjs';

export async function onRequestGet({ request, env }) {
  if (!env.RAZORPAY_KEY_SECRET) return new Response('A verified purchase is required to download this product.', { status: 401 });
  const token = (request.headers.get('cookie') || '').split('; ').find((item) => item.startsWith('verticalclipper='))?.slice('verticalclipper='.length);
  const parts = token?.split('.') || [];
  if (parts.length !== 3 || !/^\d+$/.test(parts[0]) || Number(parts[0]) < Math.floor(Date.now() / 1000)) return new Response('A verified purchase is required to download this product.', { status: 401 });
  const expected = await hmacHex(env.RAZORPAY_KEY_SECRET, `verticalclipper-session|${parts[0]}.${parts[1]}`);
  if (!constantTimeHexEqual(expected, parts[2])) return new Response('A verified purchase is required to download this product.', { status: 401 });
  const pack = await verticalClipperBytes(env);
  if (!pack) return new Response('Prompt pack delivery is temporarily unavailable.', { status: 503 });
  return new Response(pack, { headers: { 'content-type': 'application/zip', 'content-disposition': 'attachment; filename="GTA-Face-Clipper-Complete-Tool-Pack.zip"', 'cache-control': 'private, no-store' } });
}
