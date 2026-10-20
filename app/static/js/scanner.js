/**
 * Scanner module for Courier Tracking System
 * Supports both Camera and USB/HID scanners
 */

let html5QrcodeScanner = null;
let isUsbScannerActive = false;
let usbScanBuffer = "";
let usbScanTimeout = null;
let lastScanTime = 0;
const SCAN_DEBOUNCE_MS = 2000;

document.addEventListener('DOMContentLoaded', () => {
  initUsbScannerListener();
  
  const startCameraBtn = document.getElementById('start-camera-btn');
  if (startCameraBtn) {
    startCameraBtn.addEventListener('click', () => {
      initCameraScanner('scanner-viewport');
    });
  }

  const manualForm = document.getElementById('manual-scan-form');
  if (manualForm) {
    manualForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const input = document.getElementById('manual-tracking-number');
      if (input && input.value) {
        processScan(input.value.trim());
        input.value = '';
      }
    });
  }
});

// --- Camera Scanner (html5-qrcode) ---
function initCameraScanner(containerId) {
  if (!document.getElementById(containerId)) return;
  
  // Hide placeholder, show scanner
  const viewport = document.getElementById(containerId);
  viewport.innerHTML = ''; 
  viewport.style.display = 'block';

  html5QrcodeScanner = new Html5Qrcode(containerId);
  
  const config = { fps: 10, qrbox: { width: 250, height: 250 } };
  
  html5QrcodeScanner.start(
    { facingMode: "environment" }, 
    config, 
    onScanSuccess, 
    onScanFailure
  ).catch(err => {
    showToast("Camera access denied or unavailable", "error");
    console.error("Camera start error", err);
    viewport.innerHTML = '<div class="empty-state">Camera unavailable</div>';
  });
}

function stopCameraScanner() {
  if (html5QrcodeScanner) {
    html5QrcodeScanner.stop().then(() => {
      html5QrcodeScanner.clear();
    }).catch(err => console.error("Failed to stop scanner", err));
  }
}

function onScanSuccess(decodedText, decodedResult) {
  processScan(decodedText);
}

function onScanFailure(error) {
  // Ignore continuous failures during scanning
}

// --- USB/External Scanner Support ---
function initUsbScannerListener() {
  document.addEventListener('keydown', (e) => {
    // Ignore if user is typing in an input field
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    
    // USB scanners usually send characters rapidly and end with Enter
    if (e.key === 'Enter') {
      if (usbScanBuffer.length > 3) {
        isUsbScannerActive = true;
        processScan(usbScanBuffer);
        usbScanBuffer = ""; // Clear buffer
      }
    } else if (e.key.length === 1) { // Normal character
      usbScanBuffer += e.key;
      
      // Reset buffer if typing is too slow (differentiates human typing from scanner)
      clearTimeout(usbScanTimeout);
      usbScanTimeout = setTimeout(() => {
        usbScanBuffer = "";
        isUsbScannerActive = false;
      }, 100); // Scanners usually input very fast (<50ms between keys)
    }
  });
}

// --- Core Scan Processing ---
function processScan(trackingNumber) {
  const now = Date.now();
  if (now - lastScanTime < SCAN_DEBOUNCE_MS) {
    return; // Debounce to prevent duplicate processing
  }
  lastScanTime = now;
  
  console.log("Scanned:", trackingNumber);
  updateScannerStatus("Processing...", "info");
  
  // Simulated API Call
  // apiFetch(`/api/scan/${trackingNumber}`)
  //   .then(data => handleScanResult(data))
  //   .catch(err => handleScanError(err));

  // Mock implementation for UI demonstration
  setTimeout(() => {
    const mockData = {
      tracking_number: trackingNumber,
      status: 'in_transit',
      sender: 'Acme Corp',
      receiver: 'John Doe',
      description: 'Electronics Package',
      history: [
        { status: 'pending', branch: 'Origin Facility', time: new Date(Date.now() - 86400000).toISOString() }
      ]
    };
    handleScanResult(mockData);
  }, 500);
}

function handleScanResult(data) {
  playSuccessBeep();
  flashScanArea('success');
  showParcelDetails(data);
}

function handleScanError(error) {
  playErrorBeep();
  flashScanArea('error');
  updateScannerStatus("Scan Failed: " + error.message, "error");
  showToast("Parcel not found or error occurred", "error");
}

// --- Audio Feedback ---
function playBeep(frequency, type, duration) {
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const oscillator = audioCtx.createOscillator();
  const gainNode = audioCtx.createGain();
  
  oscillator.type = type;
  oscillator.frequency.value = frequency;
  
  oscillator.connect(gainNode);
  gainNode.connect(audioCtx.destination);
  
  oscillator.start();
  gainNode.gain.exponentialRampToValueAtTime(0.00001, audioCtx.currentTime + duration);
  setTimeout(() => {
    oscillator.stop();
  }, duration * 1000);
}

function playSuccessBeep() {
  playBeep(800, 'sine', 0.1);
  setTimeout(() => playBeep(1200, 'sine', 0.15), 100);
}

function playErrorBeep() {
  playBeep(300, 'sawtooth', 0.5);
}

// --- Visual Feedback ---
function flashScanArea(type) {
  const viewport = document.querySelector('.scanner-viewport');
  if (!viewport) return;
  
  const color = type === 'success' ? 'var(--accent-green)' : 'var(--accent-red)';
  viewport.style.borderColor = color;
  viewport.style.boxShadow = `0 0 20px ${color}`;
  
  setTimeout(() => {
    viewport.style.borderColor = 'rgba(79, 142, 247, 0.3)';
    viewport.style.boxShadow = 'none';
  }, 500);
}

function updateScannerStatus(message, type = 'info') {
  const resultDiv = document.getElementById('scan-result-panel');
  if (resultDiv) {
    resultDiv.classList.add('active');
  }
  // This could update a status text element inside the panel
}

function showParcelDetails(parcelData) {
  const resultPanel = document.getElementById('scan-result-panel');
  if (!resultPanel) return;
  
  resultPanel.classList.add('active');
  resultPanel.innerHTML = `
    <div class="card-header">
      <h3 class="card-title">Parcel Scanned</h3>
      <span class="badge badge-${parcelData.status}">${getStatusLabel(parcelData.status)}</span>
    </div>
    <div class="tracking-number">${parcelData.tracking_number}</div>
    <div class="form-grid" style="margin-bottom: 20px;">
      <div>
        <div class="form-label">Sender</div>
        <div>${parcelData.sender}</div>
      </div>
      <div>
        <div class="form-label">Receiver</div>
        <div>${parcelData.receiver}</div>
      </div>
    </div>
    <div class="divider"></div>
    <h4>Action Required</h4>
    <div class="form-grid-3" style="margin-top: 12px;">
      <button class="btn btn-primary" onclick="submitAction('${parcelData.tracking_number}', 'in_transit')">
        Scan at Branch
      </button>
      <button class="btn btn-success" onclick="submitAction('${parcelData.tracking_number}', 'delivered')">
        Mark Delivered
      </button>
      <button class="btn btn-danger" onclick="submitAction('${parcelData.tracking_number}', 'failed')">
        Report Issue
      </button>
    </div>
  `;
}

function clearScanResult() {
  const resultPanel = document.getElementById('scan-result-panel');
  if (resultPanel) {
    resultPanel.classList.remove('active');
    resultPanel.innerHTML = '';
  }
}

// --- Action Submission ---
function submitAction(trackingNumber, action, notes = '') {
  confirmAction(`Are you sure you want to update status to ${getStatusLabel(action)}?`, () => {
    // Simulated submission
    showToast(`Status updated to ${getStatusLabel(action)}`, 'success');
    
    // apiFetch('/api/scan/process', 'POST', { tracking_number: trackingNumber, status: action, notes })
    // .then(() => { showToast('Updated successfully', 'success'); })
    
    setTimeout(clearScanResult, 2000);
  });
}
