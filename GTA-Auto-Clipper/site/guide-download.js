const downloadLink = document.querySelector('#download-link');
const downloadStatus = document.querySelector('#download-status');
let downloading = false;

downloadLink.addEventListener('click', async (event) => {
  event.preventDefault();
  if (downloading) return;
  downloading = true;
  downloadStatus.textContent = 'Preparing your ZIP…';

  try {
    const response = await fetch(downloadLink.href, { cache: 'no-store' });
    if (response.status === 401) {
      downloadStatus.textContent = 'We couldn’t find your purchase in this browser. Contact us below with your Razorpay payment reference. Please don’t pay again.';
      return;
    }
    if (!response.ok || response.headers.get('content-type')?.split(';')[0] !== 'application/zip') {
      throw new Error('ZIP unavailable');
    }

    const zip = await response.blob();
    const header = new Uint8Array(await zip.slice(0, 4).arrayBuffer());
    if (header.join(',') !== '80,75,3,4') throw new Error('Invalid ZIP');

    const url = URL.createObjectURL(zip);
    const saveLink = document.createElement('a');
    saveLink.href = url;
    saveLink.download = 'GTA-Clipping-Guide-Premium.zip';
    document.body.append(saveLink);
    saveLink.click();
    saveLink.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
    downloadStatus.textContent = 'Check your browser’s downloads for the ZIP.';
  } catch {
    downloadStatus.textContent = 'We couldn’t download your ZIP. Try the button again or contact us below with your Razorpay payment reference.';
  } finally {
    downloading = false;
  }
});
