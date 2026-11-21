const buyButton = document.querySelector('#buy-button');
const statusLine = document.querySelector('#payment-status');
document.querySelector('#year').textContent = new Date().getFullYear();

function setStatus(message, error = false) {
  statusLine.textContent = message;
  statusLine.classList.toggle('payment-error', error);
}

let paymentConfig = null;
fetch('/api/config').then((response) => response.json()).then((config) => {
  paymentConfig = config;
  if (config.enabled) {
    buyButton.disabled = false;
    buyButton.innerHTML = 'Get the guide · ₹149 <span>→</span>';
    setStatus(config.mode === 'test' ? 'Test checkout is active. No real payment will be collected.' : 'Secure checkout · Download button appears after payment.');
  } else {
    buyButton.disabled = true;
    buyButton.textContent = 'Checkout is not active yet';
    setStatus('Razorpay checkout is not active yet. For purchase help, contact anintellectualcompany.contact@gmail.com.');
  }
}).catch(() => setStatus('Checkout status could not be loaded.', true));

buyButton.addEventListener('click', async () => {
  if (!paymentConfig?.enabled || !window.Razorpay) return;
  buyButton.disabled = true;
  setStatus('Starting secure checkout…');
  try {
    const response = await fetch('/api/create-order', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({}),
    });
    const order = await response.json();
    if (!response.ok) throw new Error(order.error || 'Could not start checkout.');
    const checkout = new Razorpay({
      key: order.keyId,
      amount: order.amount,
      currency: order.currency,
      name: 'GTA Auto Clipper',
      description: 'AI Workflow + Prompt Pack',
      order_id: order.orderId,
      theme: { color: '#b9e66b' },
      handler: async (payment) => {
        try {
          setStatus('Verifying payment securely…');
          const verified = await fetch('/api/verify-payment', {
            method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify(payment),
          });
          const result = await verified.json();
          if (!verified.ok) throw new Error(result.error || 'Payment verification failed.');
          window.location.replace('/download-ready');
        } catch (error) {
          setStatus(error.message || 'Payment verification failed. Contact support if you were charged.', true);
          buyButton.disabled = false;
        }
      },
      modal: { ondismiss: () => { buyButton.disabled = false; setStatus('Checkout closed. You can try again whenever you are ready.'); } },
    });
    checkout.on('payment.failed', (event) => {
      setStatus(event.error?.description || 'Payment did not complete. No guide was unlocked.', true);
      buyButton.disabled = false;
    });
    checkout.open();
  } catch (error) {
    setStatus(error.message || 'Checkout failed. Please retry.', true);
    buyButton.disabled = false;
  }
});
