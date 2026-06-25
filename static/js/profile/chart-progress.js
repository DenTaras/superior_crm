/* chart-progress.js — график прогресса 1ПМ */
(function(){
    var el = document.getElementById('progress-chart-data');
    if (!el) return;
    var allData;
    try { allData = JSON.parse(el.getAttribute('data-json')); } catch(e) { return; }

    var chart = null;
    var colors = ['#e74c3c','#2ecc71','#3498db','#f39c12','#9b59b6','#1abc9c','#e67e22','#2c3e50','#c0392b','#16a085'];

    window.buildChart = function(exName) {
        var points = allData[exName] || [];
        var labels = points.map(function(p){ return p.x; });
        var values = points.map(function(p){ return p.y; });
        var ctx = document.getElementById('progressChart');
        if (!ctx) return;

        if (chart) { chart.destroy(); chart = null; }

        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: exName,
                    data: values,
                    borderColor: colors[Object.keys(allData).indexOf(exName) % colors.length],
                    backgroundColor: 'transparent',
                    fill: false,
                    tension: 0.3,
                    spanGaps: true,
                    pointRadius: 5,
                    pointBackgroundColor: colors[Object.keys(allData).indexOf(exName) % colors.length],
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#999' }, grid: { color: '#333' } },
                    y: { ticks: { color: '#999' }, grid: { color: '#333' }, beginAtZero: false }
                }
            }
        });
    };

    var sel = document.getElementById('exerciseSelect');
    if (sel) {
        sel.addEventListener('change', function(){ window.buildChart(this.value); });
    }
})();
