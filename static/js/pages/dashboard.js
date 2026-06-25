/* dashboard.js — графики дашборда (выручка, слоты, форматы) */
(function(){
    var el = document.getElementById('dashboard-chart-data');
    if (!el) return;

    var colors = ['#4e79a7','#f28e2b','#e15759','#76b7b2','#59a14f','#edc948','#b07aa1','#ff9da7','#9c755f','#bab0ac'];

    function parseAttr(name) {
        var v = el.getAttribute(name);
        if (!v) return [];
        try { return JSON.parse(v); } catch(e) { return []; }
    }

    var labels = parseAttr('data-labels');
    var revenues = parseAttr('data-revenues');
    var slotLabels = parseAttr('data-slot-labels');
    var slotData = parseAttr('data-slot-data');
    var fmtLabels = parseAttr('data-fmt-labels');
    var fmtData = parseAttr('data-fmt-data');

    // Выручка
    var ctx = document.getElementById('revenueChart');
    if (ctx && labels.length) {
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{ label: 'Выручка, ₽', data: revenues, backgroundColor: colors[0] }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } }
            }
        });
    }

    // По временным слотам
    var sCtx = document.getElementById('slotChart');
    if (sCtx && slotLabels.length) {
        new Chart(sCtx, {
            type: 'pie',
            data: {
                labels: slotLabels,
                datasets: [{ data: slotData, backgroundColor: colors.slice(0, slotLabels.length) }]
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
        });
    }

    // По форматам
    var fCtx = document.getElementById('formatChart');
    if (fCtx && fmtLabels.length) {
        new Chart(fCtx, {
            type: 'pie',
            data: {
                labels: fmtLabels,
                datasets: [{ data: fmtData, backgroundColor: colors.slice(0, fmtLabels.length) }]
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
        });
    }
})();
