const button = document.querySelector('#buy-button');
const status = document.querySelector('#payment-status');
function setStatus(message, error = false) {
  status.textContent = message;
  status.classList.toggle('payment-error', error);
}

button.disabled = false;
button.innerHTML = 'Get the tool pack · ₹199 <b>→</b>';
setStatus('Secure Razorpay checkout · private download after payment.');

button.addEventListener('click', async () => {
  if (!window.Razorpay) {
    setStatus('Razorpay checkout did not load. Refresh the page and try again.', true);
    return;
  }
  button.disabled = true;
  setStatus('Starting secure checkout…');
  try {
    const created = await fetch('/api/verticalclipper/create-order', {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({}),
    });
    const order = await created.json();
    if (!created.ok) throw new Error(order.error || 'Could not start checkout.');
    const checkout = new Razorpay({
      key: order.keyId,
      amount: order.amount,
      currency: order.currency,
      name: 'GTA Face Clipper',
      description: 'GTA Face Clipper Complete Tool + PDF + Master Prompt',
      order_id: order.orderId,
      theme: { color: '#d83b2d' },
      handler: async (payment) => {
        try {
          setStatus('Verifying payment securely…');
          const verified = await fetch('/api/verticalclipper/verify-payment', {
            method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payment),
          });
          const result = await verified.json();
          if (!verified.ok) throw new Error(result.error || 'Payment verification failed.');
          setStatus('Payment confirmed. Your complete tool pack is downloading.');
          window.location.assign('/api/verticalclipper/download');
        } catch (error) {
          setStatus(error.message || 'Payment verification failed. Contact support if you were charged.', true);
          button.disabled = false;
        }
      },
      modal: { ondismiss: () => { button.disabled = false; setStatus('Checkout closed. You can try again whenever you are ready.'); } },
    });
    checkout.on('payment.failed', (event) => {
      setStatus(event.error?.description || 'Payment did not complete. No download was released.', true);
      button.disabled = false;
    });
    checkout.open();
  } catch (error) {
    setStatus(error.message || 'Checkout failed. Please retry.', true);
    button.disabled = false;
  }
});
