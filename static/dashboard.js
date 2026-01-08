(function(){
  // Shared helpers for charts and UI interactions
  const rand = (min, max) => Math.floor(Math.random()*(max-min+1))+min;

  function monthlyAttendanceDataset() {
    const labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const present = labels.map(()=>rand(18,26));
    const late = labels.map(()=>rand(0,6));
    const absent = labels.map(()=>rand(0,4));
    return { labels, present, late, absent };
  }

  function buildEmployeeCharts() {
    const el1 = document.getElementById('empMonthlyChart');
    const el2 = document.getElementById('empBreakdown');
    if (!el1 || !el2) return;

    const ds = monthlyAttendanceDataset();
    new Chart(el1.getContext('2d'), {
      type: 'line',
      data: {
        labels: ds.labels,
        datasets: [
          { label: 'Present', data: ds.present, borderColor: '#34d399', backgroundColor: 'rgba(52,211,153,0.15)', tension: 0.35, fill: true },
          { label: 'Late', data: ds.late, borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.15)', tension: 0.35, fill: true },
          { label: 'Absent', data: ds.absent, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.15)', tension: 0.35, fill: true }
        ]
      },
      options: { plugins: { legend: { labels: { color: '#e2e8f0' } } }, scales: { x: { ticks: { color: '#94a3b8' } }, y: { ticks: { color: '#94a3b8' } } } }
    });

    new Chart(el2.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: ['On-time','Late','Absent'],
        datasets: [{ data: [24, 3, 2], backgroundColor: ['#22d3ee','#f59e0b','#ef4444'], borderWidth: 0 }]
      },
      options: { plugins: { legend: { position: 'bottom', labels: { color: '#e2e8f0' } } } }
    });
  }

  function buildAdminCharts() {
    const el1 = document.getElementById('orgDailyChart');
    const el2 = document.getElementById('deptStacked');
    if (!el1 || !el2) return;

    const days = Array.from({length: 30}, (_,i)=>`${i+1}`);
    const present = days.map(()=>rand(45,60));
    const late = days.map(()=>rand(3,10));
    const absent = days.map(()=>rand(1,8));

    new Chart(el1.getContext('2d'), {
      type: 'bar',
      data: {
        labels: days,
        datasets: [
          { label: 'Present', data: present, backgroundColor: 'rgba(52,211,153,0.5)', borderColor: '#34d399', borderWidth: 1 },
          { label: 'Late', data: late, backgroundColor: 'rgba(245,158,11,0.5)', borderColor: '#f59e0b', borderWidth: 1 },
          { label: 'Absent', data: absent, backgroundColor: 'rgba(239,68,68,0.5)', borderColor: '#ef4444', borderWidth: 1 }
        ]
      },
      options: { plugins: { legend: { labels: { color: '#e2e8f0' } } }, scales: { x: { stacked: true, ticks: { color: '#94a3b8' } }, y: { stacked: true, ticks: { color: '#94a3b8' } } } }
    });

    const departments = ['IT','HR','Finance','Ops','Sales'];
    const dPresent = departments.map(()=>rand(8,15));
    const dLate = departments.map(()=>rand(0,4));
    const dAbsent = departments.map(()=>rand(0,3));

    new Chart(el2.getContext('2d'), {
      type: 'bar',
      data: {
        labels: departments,
        datasets: [
          { label: 'Present', data: dPresent, backgroundColor: '#34d399' },
          { label: 'Late', data: dLate, backgroundColor: '#f59e0b' },
          { label: 'Absent', data: dAbsent, backgroundColor: '#ef4444' }
        ]
      },
      options: { plugins: { legend: { labels: { color: '#e2e8f0' } } }, scales: { x: { stacked: true, ticks: { color: '#94a3b8' } }, y: { stacked: true, ticks: { color: '#94a3b8' } } } }
    });
  }

  // Basic UI interactivity for mock approvals
  function wireApprovals() {
    document.querySelectorAll('[data-approve]')?.forEach(btn => {
      btn.addEventListener('click', () => {
        const row = btn.closest('tr');
        if (!row) return;
        row.querySelector('[data-status]').innerHTML = '<span class="chip">Approved</span>';
      });
    });
    document.querySelectorAll('[data-reject]')?.forEach(btn => {
      btn.addEventListener('click', () => {
        const row = btn.closest('tr');
        if (!row) return;
        row.querySelector('[data-status]').innerHTML = '<span class="chip">Rejected</span>';
      });
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('page-animate');
    buildEmployeeCharts();
    buildAdminCharts();
    wireApprovals();
    // Reveal-on-scroll for elements with .reveal
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); observer.unobserve(e.target); } });
    }, { threshold: 0.12 });
    document.querySelectorAll('.reveal, .glass-card').forEach(el => observer.observe(el));

    // Button ripple effect (lightweight)
    document.body.addEventListener('click', (e) => {
      const t = e.target.closest('.btn, button');
      if (!t) return;
      const ripple = document.createElement('span');
      ripple.style.position = 'absolute';
      ripple.style.borderRadius = '50%';
      ripple.style.transform = 'scale(0)';
      ripple.style.opacity = '0.45';
      ripple.style.pointerEvents = 'none';
      ripple.style.background = 'currentColor';
      const rect = t.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      ripple.style.width = ripple.style.height = size + 'px';
      ripple.style.left = (e.clientX - rect.left - size/2) + 'px';
      ripple.style.top = (e.clientY - rect.top - size/2) + 'px';
      ripple.style.transition = 'transform .45s ease, opacity .6s ease';
      t.style.position = 'relative';
      t.appendChild(ripple);
      requestAnimationFrame(() => { ripple.style.transform = 'scale(1)'; ripple.style.opacity = '0'; });
      setTimeout(() => ripple.remove(), 650);
    });
  });
})();


