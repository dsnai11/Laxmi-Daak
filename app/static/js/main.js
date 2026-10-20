/**
 * Main JavaScript for Courier Tracking System
 */

// Global fetch interceptor to automatically add CSRF Token for security
const originalFetch = window.fetch;
window.fetch = function (url, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
    options.headers = options.headers || {};
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    if (csrfMeta) {
      const token = csrfMeta.getAttribute('content');
      if (options.headers instanceof Headers) {
        options.headers.set('X-CSRFToken', token);
      } else {
        options.headers['X-CSRFToken'] = token;
      }
    }
  }
  return originalFetch(url, options);
};

document.addEventListener('DOMContentLoaded', () => {
  initSidebar();
  initActiveNav();
  initPageAnimations();
  initModals();
});

// Sidebar Toggle for Mobile
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  if (sidebar) {
    const isOpen = sidebar.classList.toggle('open');
    if (backdrop) {
      if (isOpen) {
        backdrop.style.display = 'block';
        requestAnimationFrame(() => { backdrop.classList.add('active'); });
      } else {
        backdrop.classList.remove('active');
        setTimeout(() => { if (!sidebar.classList.contains('open')) backdrop.style.display = 'none'; }, 260);
      }
    }
  }
}

function initSidebar() {
  const toggleBtn = document.querySelector('.sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  const backdrop = document.getElementById('sidebarBackdrop');
  
  if (backdrop) {
    backdrop.addEventListener('click', () => {
      if (sidebar && sidebar.classList.contains('open')) {
        toggleSidebar();
      }
    });
  }
  
  // Also close sidebar on mobile when navigating to another section
  document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
    item.addEventListener('click', () => {
      if (window.innerWidth <= 1024 && sidebar && sidebar.classList.contains('open')) {
        toggleSidebar();
      }
    });
  });

  // Preserve sidebar scroll position across navigation
  const sidebarNav = document.querySelector('.sidebar-nav');
  if (sidebarNav) {
    const savedPos = sessionStorage.getItem('sidebar_scroll_pos');
    if (savedPos !== null) {
      sidebarNav.scrollTop = parseInt(savedPos, 10);
    }
    sidebarNav.addEventListener('scroll', () => {
      sessionStorage.setItem('sidebar_scroll_pos', sidebarNav.scrollTop);
    }, { passive: true });

    const activeItem = sidebarNav.querySelector('.nav-item.active');
    if (activeItem && savedPos === null) {
      activeItem.scrollIntoView({ block: 'nearest' });
    }
  }
}

// Active Nav Item based on URL
function initActiveNav() {
  const currentPath = window.location.pathname;
  const navItems = document.querySelectorAll('.nav-item');
  
  navItems.forEach(item => {
    const href = item.getAttribute('href');
    if (href && currentPath.startsWith(href) && href !== '/') {
      item.classList.add('active');
    } else if (href === '/' && currentPath === '/') {
      item.classList.add('active');
    }
  });
}

// Toast Notifications System
function showToast(message, type = 'success') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let icon = '✓';
  if (type === 'error') icon = '✕';
  if (type === 'info') icon = 'ℹ';
  if (type === 'warning') icon = '⚠';

  toast.innerHTML = `
    <span class="toast-icon">${icon}</span>
    <span class="toast-message">${message}</span>
  `;

  container.appendChild(toast);

  // Auto remove after 4 seconds
  setTimeout(() => {
    toast.style.animation = 'slideInRight 0.3s ease-in reverse forwards';
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }, 4000);
}

// Modal System
function initModals() {
  const closeBtns = document.querySelectorAll('.modal-close, [data-dismiss="modal"]');
  closeBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const modalId = e.target.closest('.modal-overlay').id;
      closeModal(modalId);
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const activeModal = document.querySelector('.modal-overlay.active');
      if (activeModal) {
        closeModal(activeModal.id);
      }
    }
  });

  const overlays = document.querySelectorAll('.modal-overlay');
  overlays.forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeModal(overlay.id);
      }
    });
  });
}

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add('active');
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('active');
  }
}

// Confirm Dialog
function confirmAction(message, callback) {
  // Create confirmation modal dynamically
  const modalHtml = `
    <div class="modal-overlay active" id="confirm-modal">
      <div class="modal">
        <div class="modal-header">
          <h3 class="modal-title">Confirm Action</h3>
          <button class="modal-close" onclick="closeModal('confirm-modal'); document.getElementById('confirm-modal').remove();">&times;</button>
        </div>
        <div class="modal-body">
          <p>${message}</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" onclick="closeModal('confirm-modal'); document.getElementById('confirm-modal').remove();">Cancel</button>
          <button class="btn btn-primary" id="confirm-btn-yes">Confirm</button>
        </div>
      </div>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', modalHtml);
  
  document.getElementById('confirm-btn-yes').addEventListener('click', () => {
    closeModal('confirm-modal');
    setTimeout(() => {
      document.getElementById('confirm-modal').remove();
      callback();
    }, 300);
  });
}

// AJAX Helper
async function apiFetch(url, method = 'GET', data = null) {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    }
  };

  if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
    options.body = JSON.stringify(data);
  }

  try {
    const response = await fetch(url, options);
    const result = await response.json();
    
    if (!response.ok) {
      showToast(result.message || 'An error occurred', 'error');
      throw new Error(result.message || 'API Error');
    }
    
    return result;
  } catch (error) {
    console.error('API Fetch Error:', error);
    showToast(error.message, 'error');
    throw error;
  }
}

// Table Search Filter
function filterTable(tableId, searchInput) {
  const input = document.getElementById(searchInput);
  const filter = input.value.toLowerCase();
  const table = document.getElementById(tableId);
  if (!table) return;
  const trs = table.getElementsByTagName('tr');

  for (let i = 1; i < trs.length; i++) { // Skip header row
    const tds = trs[i].getElementsByTagName('td');
    let display = false;
    for (let j = 0; j < tds.length; j++) {
      if (tds[j]) {
        const txtValue = tds[j].textContent || tds[j].innerText;
        if (txtValue.toLowerCase().indexOf(filter) > -1) {
          display = true;
          break;
        }
      }
    }
    trs[i].style.display = display ? '' : 'none';
  }
}

// Form Validation
function validateForm(formElement) {
  let isValid = true;
  const requiredFields = formElement.querySelectorAll('[required]');
  
  requiredFields.forEach(field => {
    if (!field.value.trim()) {
      isValid = false;
      field.style.borderColor = 'var(--accent-red)';
      // Basic inline error showing
      let errorMsg = field.nextElementSibling;
      if (!errorMsg || !errorMsg.classList.contains('error-text')) {
        errorMsg = document.createElement('span');
        errorMsg.className = 'error-text';
        errorMsg.style.color = 'var(--accent-red)';
        errorMsg.style.fontSize = '12px';
        errorMsg.innerText = 'This field is required';
        field.parentNode.insertBefore(errorMsg, field.nextSibling);
      }
    } else {
      field.style.borderColor = '';
      const errorMsg = field.nextElementSibling;
      if (errorMsg && errorMsg.classList.contains('error-text')) {
        errorMsg.remove();
      }
    }
  });
  
  return isValid;
}

// Photo Upload Preview
function initPhotoUpload(dropzoneId, previewGridId, inputId) {
  const dropzone = document.getElementById(dropzoneId);
  const input = document.getElementById(inputId);
  const previewGrid = document.getElementById(previewGridId);
  
  if (!dropzone || !input || !previewGrid) return;

  dropzone.addEventListener('click', () => input.click());
  
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
  
  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('dragover');
  });
  
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      handleFiles(input.files);
    }
  });
  
  input.addEventListener('change', () => {
    handleFiles(input.files);
  });
  
  function handleFiles(files) {
    previewGrid.innerHTML = '';
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!file.type.startsWith('image/')) continue;
      
      const reader = new FileReader();
      reader.onload = (e) => {
        const item = document.createElement('div');
        item.className = 'photo-preview-item';
        item.innerHTML = `
          <img src="${e.target.result}" alt="Preview">
          <button type="button" class="photo-remove-btn" onclick="this.parentNode.remove()">&times;</button>
        `;
        previewGrid.appendChild(item);
      };
      reader.readAsDataURL(file);
    }
  }
}

// Auto-refresh Dashboard Stats Setup
function setupAutoRefresh(callback, intervalSeconds = 30) {
  setInterval(callback, intervalSeconds * 1000);
}

// Copy to Clipboard
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copied to clipboard!', 'success');
  }).catch(err => {
    console.error('Could not copy text: ', err);
    showToast('Failed to copy', 'error');
  });
}

// Print QR
function printQR(trackingNumber) {
  // Logic to open a print window for the QR code
  const printWindow = window.open(`/print-qr/${trackingNumber}`, '_blank', 'width=600,height=600');
  if(printWindow) {
    printWindow.onload = function() {
      printWindow.print();
    };
  } else {
      showToast('Please allow popups to print', 'warning');
  }
}

// Status Helpers
function getStatusColor(status) {
  const map = {
    'pending': 'var(--accent-orange)',
    'in_transit': 'var(--accent-blue)',
    'delivered': 'var(--accent-green)',
    'failed': 'var(--accent-red)',
    'returned': 'var(--text-muted)'
  };
  return map[status] || 'var(--text-primary)';
}

function getStatusLabel(status) {
  return status.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

// Date Formatters
function formatDate(dateString) {
  const d = new Date(dateString);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

function formatRelativeTime(dateString) {
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  const daysDifference = Math.round((new Date(dateString).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
  
  if (daysDifference === 0) return 'Today';
  if (daysDifference === -1) return 'Yesterday';
  return rtf.format(daysDifference, 'day');
}

// Page Load Animations (Staggered glass cards)
function initPageAnimations() {
  const cards = document.querySelectorAll('.glass-card, .stat-card');
  cards.forEach((card, index) => {
    card.style.opacity = '0';
    card.style.animation = `slideInUp 0.4s ease-out ${index * 0.1}s forwards`;
  });
}

// Theme Toggle Functionality
function toggleTheme() {
  const isLight = document.documentElement.classList.toggle('light-theme');
  document.body.classList.toggle('light-theme', isLight);
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
}

// Initialise theme classes on DOM load
document.addEventListener('DOMContentLoaded', () => {
  const theme = localStorage.getItem('theme') || 'dark';
  if (theme === 'light') {
    document.documentElement.classList.add('light-theme');
    document.body.classList.add('light-theme');
  }
});

// Custom Styled Premium Modal Alerts System (Matches Screenshot Layout)
function showCustomAlert(message, type = 'warning', title = '') {
  type = type.toLowerCase();
  if (type === 'error' || type === 'danger') type = 'error';
  else if (type === 'success') type = 'success';
  else if (type === 'info') type = 'info';
  else type = 'warning';

  if (!title) {
    if (type === 'error') title = 'Alert Error';
    else if (type === 'success') title = 'Success Notification';
    else if (type === 'info') title = 'Notification';
    else title = 'Alert Warning';
  }

  // Remove existing alert if any
  const existing = document.getElementById('custom-alert-container');
  if (existing) existing.remove();

  // Create overlay container
  const overlay = document.createElement('div');
  overlay.id = 'custom-alert-container';
  overlay.className = 'custom-alert-overlay';

  const btnClass = (type === 'error' || type === 'warning') ? 'error-btn' : '';

  overlay.innerHTML = `
    <div class="custom-alert-modal">
      <div class="custom-alert-header ${type}">
        <span>${title}</span>
      </div>
      <div class="custom-alert-body">
        ${message}
      </div>
      <div class="custom-alert-footer">
        <button class="custom-alert-btn ${btnClass}" id="custom-alert-ok-btn">OK</button>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  // Trigger rendering for transitions
  requestAnimationFrame(() => {
    overlay.classList.add('active');
  });

  const okBtn = overlay.querySelector('#custom-alert-ok-btn');
  if (okBtn) okBtn.focus();

  const closeAlert = () => {
    overlay.classList.remove('active');
    setTimeout(() => {
      overlay.remove();
    }, 250);
  };

  if (okBtn) okBtn.addEventListener('click', closeAlert);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) closeAlert();
  });
  
  const keyHandler = (e) => {
    if (e.key === 'Escape' || e.key === 'Enter') {
      e.preventDefault();
      closeAlert();
      document.removeEventListener('keydown', keyHandler);
    }
  };
  document.addEventListener('keydown', keyHandler);
}

// Override standard browser alert
window.alert = function(message) {
  showCustomAlert(message, 'warning');
};



// ==========================================================================
// Image Zoom Lightbox Modal
// ==========================================================================
let _currentZoomLevel = 1.0;
let _currentPanX = 0;
let _currentPanY = 0;
let _isPanning = false;
let _panStartX = 0;
let _panStartY = 0;

function _updateZoomTransform() {
  const img = document.getElementById('imageZoomImg');
  const display = document.getElementById('zoomLevelDisplay');
  if (img) {
    img.style.transform = `translate(${_currentPanX}px, ${_currentPanY}px) scale(${_currentZoomLevel})`;
  }
  if (display) {
    display.textContent = Math.round(_currentZoomLevel * 100) + '%';
  }
}

window.openImageZoomModal = function(src, title) {
  if (!src) return;
  let modal = document.getElementById('imageZoomModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'imageZoomModal';
    modal.className = 'image-zoom-overlay';
    modal.innerHTML = `
      <div class="image-zoom-header">
        <span class="image-zoom-title" id="imageZoomTitle">📷 Package Photo</span>
        <span class="image-zoom-hint">Scroll mouse wheel or click (+ / −) to Zoom • Drag to Move</span>
        <button type="button" class="image-zoom-close-btn" onclick="closeImageZoomModal()">&times;</button>
      </div>
      <div class="image-zoom-viewport" id="imageZoomViewport">
        <img id="imageZoomImg" src="" alt="Zoom view" draggable="false">
      </div>
      <div class="image-zoom-toolbar">
        <button type="button" class="zoom-btn" onclick="changeImageZoom(-0.25)" title="Zoom Out (Small)">🔍−</button>
        <button type="button" class="zoom-btn" onclick="resetImageZoom()" title="Reset Zoom"><span id="zoomLevelDisplay">100%</span></button>
        <button type="button" class="zoom-btn" onclick="changeImageZoom(0.25)" title="Zoom In (Big)">🔍+</button>
        <button type="button" class="zoom-btn" onclick="fitImageZoom()" title="Fit to Screen">⤢ Fit</button>
        <a id="imageZoomDownloadBtn" href="" download class="zoom-btn" title="Download Image" target="_blank" style="text-decoration:none;">⬇️ Save</a>
        <button type="button" class="zoom-btn zoom-btn-close" onclick="closeImageZoomModal()" title="Close (Esc)">✕ Close</button>
      </div>
    `;
    document.body.appendChild(modal);

    const vp = document.getElementById('imageZoomViewport');
    vp.addEventListener('wheel', function(e) {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 0.2 : -0.2;
      changeImageZoom(delta);
    }, { passive: false });

    vp.addEventListener('mousedown', function(e) {
      if (e.target.id === 'imageZoomImg' || e.target.id === 'imageZoomViewport') {
        _isPanning = true;
        _panStartX = e.clientX - _currentPanX;
        _panStartY = e.clientY - _currentPanY;
        vp.classList.add('dragging');
      }
    });

    window.addEventListener('mousemove', function(e) {
      if (_isPanning) {
        _currentPanX = e.clientX - _panStartX;
        _currentPanY = e.clientY - _panStartY;
        _updateZoomTransform();
      }
    });

    window.addEventListener('mouseup', function() {
      if (_isPanning) {
        _isPanning = false;
        const vp = document.getElementById('imageZoomViewport');
        if (vp) vp.classList.remove('dragging');
      }
    });

    vp.addEventListener('dblclick', function(e) {
      e.preventDefault();
      if (_currentZoomLevel > 1.1) {
        resetImageZoom();
      } else {
        _currentZoomLevel = 2.0;
        _updateZoomTransform();
      }
    });

    vp.addEventListener('click', function(e) {
      if (e.target === vp) {
        closeImageZoomModal();
      }
    });

    document.addEventListener('keydown', function(e) {
      const modal = document.getElementById('imageZoomModal');
      if (!modal || !modal.classList.contains('active')) return;
      if (e.key === 'Escape') {
        closeImageZoomModal();
      } else if (e.key === '+' || e.key === '=') {
        changeImageZoom(0.25);
      } else if (e.key === '-' || e.key === '_') {
        changeImageZoom(-0.25);
      } else if (e.key === '0') {
        resetImageZoom();
      }
    });
  }

  const titleEl = document.getElementById('imageZoomTitle');
  if (titleEl) titleEl.textContent = title || '📷 Package Photo';
  const imgEl = document.getElementById('imageZoomImg');
  if (imgEl) imgEl.src = src;
  const dlBtn = document.getElementById('imageZoomDownloadBtn');
  if (dlBtn) dlBtn.href = src;

  _currentZoomLevel = 1.0;
  _currentPanX = 0;
  _currentPanY = 0;
  _updateZoomTransform();

  modal.classList.add('active');
  document.body.style.overflow = 'hidden';
};

window.closeImageZoomModal = function() {
  const modal = document.getElementById('imageZoomModal');
  if (modal) {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  }
};

window.changeImageZoom = function(delta) {
  _currentZoomLevel = Math.max(0.25, Math.min(5.0, _currentZoomLevel + delta));
  _updateZoomTransform();
};

window.resetImageZoom = function() {
  _currentZoomLevel = 1.0;
  _currentPanX = 0;
  _currentPanY = 0;
  _updateZoomTransform();
};

window.fitImageZoom = function() {
  _currentZoomLevel = 0.85;
  _currentPanX = 0;
  _currentPanY = 0;
  _updateZoomTransform();
};

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.photo-preview-item img, .photo-preview-grid img').forEach(img => {
    img.style.cursor = 'zoom-in';
    if (!img.getAttribute('onclick')) {
      img.addEventListener('click', function() {
        window.openImageZoomModal(this.src, 'Package Photo');
      });
    }
  });
});
