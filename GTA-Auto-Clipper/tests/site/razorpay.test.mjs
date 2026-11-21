import test from 'node:test';
import assert from 'node:assert/strict';
import { gzipSync } from 'node:zlib';
import { GUIDE_AMOUNT_PAISE, isPaymentCaptured, constantTimeHexEqual } from '../../site/functions/_lib/razorpay.mjs';
import { onRequestPost as createOrder } from '../../site/functions/api/create-order.js';
import { onRequestPost as verifyPayment } from '../../site/functions/api/verify-payment.js';
import { onRequestGet as downloadGuide } from '../../site/functions/api/download.js';

test('the guide checkout amount is fixed at ₹149 on the server', () => {
  assert.equal(GUIDE_AMOUNT_PAISE, 14900);
});

test('payment unlock requires a captured payment for the matching order and amount', () => {
  assert.equal(isPaymentCaptured({ status: 'captured', order_id: 'order_ok', amount: 14900 }, 'order_ok'), true);
  assert.equal(isPaymentCaptured({ status: 'authorized', order_id: 'order_ok', amount: 14900 }, 'order_ok'), false);
  assert.equal(isPaymentCaptured({ status: 'captured', order_id: 'other', amount: 14900 }, 'order_ok'), false);
  assert.equal(isPaymentCaptured({ status: 'captured', order_id: 'order_ok', amount: 1 }, 'order_ok'), false);
});

test('hex signature comparison rejects malformed and unequal values', () => {
  assert.equal(constantTimeHexEqual('a0ff', 'a0ff'), true);
  assert.equal(constantTimeHexEqual('a0ff', 'a0fe'), false);
  assert.equal(constantTimeHexEqual('a0ff', 'a0ff00'), false);
  assert.equal(constantTimeHexEqual('not-hex', 'not-hex'), false);
});

test('checkout creates a fixed-price Razorpay order and unlocks only a verified capture', async () => {
  const previousFetch = globalThis.fetch;
  const secret = 'test_secret_never_for_production';
  const guide = Buffer.from(
    'UEsDBBQAAAAAADMVdF0q3jQ7CgAAAAoAAAAJAAAAZ3VpZGUudHh0dGVzdCBndWlkZVBLAQIUABQAAAAAADMVdF0q3jQ7CgAAAAoAAAAJAAAAAAAAAAAAAACAAQAAAABndWlkZS50eHRQSwUGAAAAAAEAAQA3AAAAMQAAAAAA',
    'base64',
  );
  const env = {
    RAZORPAY_KEY_ID: 'rzp_test_example',
    RAZORPAY_KEY_SECRET: secret,
    GUIDE_CONTENT_GZIP_BASE64: gzipSync(guide).toString('base64'),
  };
  let orderBody;
  globalThis.fetch = async (url, options = {}) => {
    if (String(url).endsWith('/orders')) {
      orderBody = JSON.parse(options.body);
      return Response.json({ id: 'order_test_1' });
    }
    return Response.json({ id: 'pay_test_1', status: 'captured', order_id: 'order_test_1', amount: 14900 });
  };

  try {
    const wrongFile = await createOrder({
      env: { ...env, GUIDE_CONTENT_GZIP_BASE64: gzipSync('%PDF-1.7\nPrivate buyer guide').toString('base64') },
      request: new Request('https://example.test/api/create-order', { method: 'POST', body: '{}' }),
    });
    assert.equal(wrongFile.status, 503);
    assert.equal(orderBody, undefined);

    const orderResponse = await createOrder({
      env,
      request: new Request('https://example.test/api/create-order', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ email: 'buyer@example.test', amount: 1 }),
      }),
    });
    assert.equal(orderResponse.status, 200);
    assert.equal(orderBody.amount, 14900);
    assert.equal(orderBody.currency, 'INR');
    assert.equal((await orderResponse.json()).amount, 14900);

    const signature = await (await import('../../site/functions/_lib/razorpay.mjs')).hmacHex(
      secret, 'order_test_1|pay_test_1',
    );
    const verified = await verifyPayment({
      env,
      request: new Request('https://example.test/api/verify-payment', {
        method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ razorpay_order_id: 'order_test_1', razorpay_payment_id: 'pay_test_1', razorpay_signature: signature }),
      }),
    });
    assert.equal(verified.status, 200);
    const cookie = verified.headers.get('set-cookie').split(';')[0];
    const file = await downloadGuide({
      env,
      request: new Request('https://example.test/api/download', { headers: { cookie } }),
    });
    assert.equal(file.status, 200);
    assert.equal(file.headers.get('content-type'), 'application/zip');
    assert.equal(file.headers.get('content-disposition'), 'attachment; filename="GTA-Clipping-Guide-Premium.zip"');
    assert.deepEqual(Buffer.from(await file.arrayBuffer()), guide);
  } finally {
    globalThis.fetch = previousFetch;
  }
});
