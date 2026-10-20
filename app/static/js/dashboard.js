/**
 * Dashboard module for Courier Tracking System
 * Handles Chart.js visualization and Socket.IO real-time updates
 */

let trendChart = null;
let statusChart = null;
let branchChart = null;
let socket = null;

document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  connectSocket();
  animateAllCounters();
  setupAutoRefresh(fetchStats, 60); // 60s fallback refresh
});

// --- Chart Initialization ---

function initCharts() {
  // Common Chart Defaults for Dark Theme
  if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.scale.grid.color = 'rgba(255, 255, 255, 0.05)';
    Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(10, 15, 30, 0.9)';
    Chart.defaults.plugins.tooltip.titleColor = '#e8eaf6';
    Chart.defaults.plugins.tooltip.padding = 12;
    Chart.defaults.plugins.tooltip.borderColor = 'rgba(255,255,255,0.1)';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
  }

  // 1. Trend Line Chart
  const trendCanvas = document.getElementById('trendChart');
  if (trendCanvas) {
    const ctx = trendCanvas.getContext('2d');
    
    // Create gradient
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(79, 142, 247, 0.5)');
    gradient.addColorStop(1, 'rgba(79, 142, 247, 0.0)');

    trendChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        datasets: [{
          label: 'Parcels Processed',
          data: [120, 150, 180, 130, 210, 170, 240],
          borderColor: '#4f8ef7',
          backgroundColor: gradient,
          borderWidth: 3,
          tension: 0.4, // Smooth curve
          fill: true,
          pointBackgroundColor: '#0a0f1e',
          pointBorderColor: '#4f8ef7',
          pointBorderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true }
        }
      }
    });
  }

  // 2. Status Doughnut Chart
  const statusCanvas = document.getElementById('statusChart');
  if (statusCanvas) {
    statusChart = new Chart(statusCanvas, {
      type: 'doughnut',
      data: {
        labels: ['Pending', 'In Transit', 'Delivered', 'Failed'],
        datasets: [{
          data: [15, 45, 35, 5],
          backgroundColor: [
            '#f59e0b', // pending
            '#4f8ef7', // in_transit
            '#10b981', // delivered
            '#ef4444'  // failed
          ],
          borderWidth: 0,
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '75%',
        plugins: {
          legend: { position: 'bottom' }
        }
      }
    });
  }

  // 3. Branch Performance Bar Chart
  const branchCanvas = document.getElementById('branchChart');
  if (branchCanvas) {
    branchChart = new Chart(branchCanvas, {
      type: 'bar',
      data: {
        labels: ['North Hub', 'South Hub', 'East Hub', 'West Hub'],
        datasets: [{
          label: 'Volume',
          data: [450, 320, 280, 190],
          backgroundColor: '#8b5cf6',
          borderRadius: 6
        }]
      },
      options: {
        indexAxis: 'y', // Horizontal bar
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true } }
      }
    });
  }
}

function updateChart(chart, newData) {
  if (chart) {
    chart.data.datasets[0].data = newData;
    chart.update();
  }
}

// --- Socket.IO Real-time Updates ---
function connectSocket() {
  if (typeof io !== 'undefined') {
    socket = io({ transports: ['polling'] });
    
    socket.on('connect', () => {
      showConnectionStatus(true);
      console.log('Connected to real-time server');
    });

    socket.on('disconnect', () => {
      showConnectionStatus(false);
      console.log('Disconnected from server');
    });

    socket.on('scan_update', (data) => {
      handleRealtimeScan(data);
    });

    socket.on('stats_update', (data) => {
      updateDashboardStats(data);
    });
  } else {
    console.warn('Socket.IO not loaded, real-time features disabled');
    showConnectionStatus(false);
  }
}

function showConnectionStatus(connected) {
  const dot = document.querySelector('.connection-status-dot');
  if (dot) {
    dot.style.backgroundColor = connected ? 'var(--accent-green)' : 'var(--accent-red)';
    dot.title = connected ? 'Connected to live updates' : 'Disconnected';
  }
}

function handleRealtimeScan(data) {
  // 1. Show Toast
  showToast(`Scanned: ${data.tracking_number} at ${data.branch}`, 'info');
  
  // 2. Add to Activity Feed
  addActivityRow(data);
  
  // 3. Update related counters on screen (simplified)
  const totalCounter = document.getElementById('stat-total-scans');
  if (totalCounter) {
    const current = parseInt(totalCounter.innerText.replace(/,/g, ''));
    animateCounter(totalCounter, current, current + 1, 500);
  }
}

function updateDashboardStats(data) {
  // Expected data: { total: 1000, delivered: 500, pending: 200, ... }
  for (const [key, value] of Object.entries(data)) {
    const el = document.getElementById(`stat-${key}`);
    if (el) {
      const current = parseInt(el.innerText.replace(/,/g, '')) || 0;
      if (current !== value) {
        animateCounter(el, current, value, 1000);
      }
    }
  }
  
  // Update charts if data provided
  if (data.trendData) updateChart(trendChart, data.trendData);
  if (data.statusData) updateChart(statusChart, data.statusData);
}

// --- Stats Animation ---
function animateAllCounters() {
  const counters = document.querySelectorAll('.stat-value');
  counters.forEach(counter => {
    const target = parseInt(counter.getAttribute('data-target')) || parseInt(counter.innerText.replace(/,/g, ''));
    counter.innerText = '0';
    animateCounter(counter, 0, target, 1500);
  });
}

function animateCounter(element, start, end, duration) {
  let startTimestamp = null;
  const step = (timestamp) => {
    if (!startTimestamp) startTimestamp = timestamp;
    const progress = Math.min((timestamp - startTimestamp) / duration, 1);
    
    // Easing function (easeOutQuad)
    const easeProgress = progress * (2 - progress);
    const currentVal = Math.floor(easeProgress * (end - start) + start);
    
    element.innerText = currentVal.toLocaleString();
    
    if (progress < 1) {
      window.requestAnimationFrame(step);
    } else {
      element.innerText = end.toLocaleString();
    }
  };
  window.requestAnimationFrame(step);
}

// --- Activity Feed ---
function addActivityRow(data) {
  const tbody = document.querySelector('#activity-feed-table tbody');
  if (!tbody) return;
  
  const tr = document.createElement('tr');
  tr.style.opacity = '0';
  tr.style.transform = 'translateX(-20px)';
  tr.style.transition = 'all 0.3s ease-out';
  
  tr.innerHTML = `
    <td><strong>${data.tracking_number}</strong></td>
    <td><span class="badge badge-${data.status}">${getStatusLabel(data.status)}</span></td>
    <td>${data.branch}</td>
    <td>${formatRelativeTime(new Date())}</td>
  `;
  
  tbody.insertBefore(tr, tbody.firstChild);
  
  // Trigger animation
  setTimeout(() => {
    tr.style.opacity = '1';
    tr.style.transform = 'translateX(0)';
  }, 10);
  
  // Remove oldest if more than 20
  if (tbody.children.length > 20) {
    tbody.removeChild(tbody.lastChild);
  }
}

// --- Fallback Fetch ---
async function fetchStats() {
  if (socket && socket.connected) return; // Let socket handle it if connected
  
  try {
    // const data = await apiFetch('/api/dashboard/stats');
    // updateDashboardStats(data);
    console.log('Fetched fallback stats');
  } catch (e) {
    console.error('Failed to fetch stats', e);
  }
}
