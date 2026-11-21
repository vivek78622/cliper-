export const GUIDE_AMOUNT_PAISE = 14900;

export function isPaymentCaptured(payment, orderId, expectedAmount = GUIDE_AMOUNT_PAISE) {
  return payment?.status === 'captured'
    && payment?.order_id === orderId
    && Number(payment?.amount) === expectedAmount;
}

export function constantTimeHexEqual(left, right) {
  if (typeof left !== 'string' || typeof right !== 'string'
      || !/^[a-f0-9]+$/i.test(left) || !/^[a-f0-9]+$/i.test(right)
      || left.length !== right.length || left.length % 2 !== 0) return false;
  let diff = 0;
  for (let i = 0; i < left.length; i += 1) {
    diff |= left.charCodeAt(i) ^ right.charCodeAt(i);
  }
  return diff === 0;
}

export async function hmacHex(secret, value) {
  const key = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  );
  const signature = new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(value)));
  return [...signature].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

export function jsonResponse(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...headers },
  });
}

export function razorpayAuth(env) {
  return `Basic ${btoa(`${env.RAZORPAY_KEY_ID}:${env.RAZORPAY_KEY_SECRET}`)}`;
}

export async function guideBytes(env) {
  if (!env.GUIDE_CONTENT_GZIP_BASE64) return null;
  try {
    const bytes = Uint8Array.from(atob(env.GUIDE_CONTENT_GZIP_BASE64), (char) => char.charCodeAt(0));
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    const guide = new Uint8Array(await new Response(stream).arrayBuffer());
    const hasZipHeader = guide[0] === 0x50 && guide[1] === 0x4b && guide[2] === 0x03 && guide[3] === 0x04;
    return hasZipHeader ? guide : null;
  } catch {
    return null;
  }
}
