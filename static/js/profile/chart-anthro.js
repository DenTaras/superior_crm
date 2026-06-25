/* chart-anthro.js — график прогресса антропометрии */
(function(){
    var el = document.getElementById('anthro-chart-data');
    if (!el) return;
    var anthroAllData;
    try { anthroAllData = JSON.parse(el.getAttribute('data-json')); } catch(e) { return; }

    var weightPoints = anthroAllData['Вес'] || [];
    var fatPoints = anthroAllData['Жир'] || [];
    var girthKeys = ['Бедро', 'Талия', 'Грудь', 'Плечи', 'Бицепс', 'Шея', 'Запястье'];
    var girthColors = ['#2ecc71','#e74c3c','#3498db','#f39c12','#9b59b6','#1abc9c','#95a5a6'];
    var skinfoldKeys = ['Складка грудь', 'Складка живот', 'Складка бедро', 'Складка трицепс', 'Складка под лопаткой'];
    var skinfoldColors = ['#e74c3c','#f39c12','#2ecc71','#3498db','#9b59b6'];

    var labelSet = new Set();
    weightPoints.forEach(function(p){ labelSet.add(p.x); });
    fatPoints.forEach(function(p){ labelSet.add(p.x); });
    girthKeys.forEach(function(k){ (anthroAllData[k] || []).forEach(function(p){ labelSet.add(p.x); }); });
    skinfoldKeys.forEach(function(k){ (anthroAllData[k] || []).forEach(function(p){ labelSet.add(p.x); }); });

    var anthroLabels = Array.from(labelSet).sort(function(a,b){
        var da=a.split('.'), db=b.split('.');
        return parseInt(da[1])-parseInt(db[1])||parseInt(da[0])-parseInt(db[0]);
    });

    function buildDict(points) { var d = {}; points.forEach(function(p){ d[p.x] = p.y; }); return d; }

    var anthroChart = null;

    window.buildAnthroChart = function(mode) {
        var datasets = [];
        var scales = { x: { ticks: { color: '#999' }, grid: { color: '#333' } } };

        if (mode === 'weight_fat') {
            var wd = buildDict(weightPoints);
            var fd = buildDict(fatPoints);
            datasets = [
                {
                    label: 'Вес (кг)',
                    data: anthroLabels.map(function(l){ return wd[l] !== undefined ? wd[l] : null; }),
                    borderColor: '#3498db', backgroundColor: 'transparent',
                    yAxisID: 'y', tension: 0.3, spanGaps: true, pointRadius: 4,
                },
                {
                    label: 'Жир (%)',
                    data: anthroLabels.map(function(l){ return fd[l] !== undefined ? fd[l] : null; }),
                    borderColor: '#e74c3c', backgroundColor: 'transparent',
                    yAxisID: 'y1', tension: 0.3, spanGaps: true, pointRadius: 4,
                }
            ];
            scales.y = { type: 'linear', display: true, position: 'left', ticks: { color: '#3498db' }, grid: { color: '#333' }, beginAtZero: false, title: { display: true, text: 'Вес (кг)', color: '#3498db' } };
            scales.y1 = { type: 'linear', display: true, position: 'right', ticks: { color: '#e74c3c' }, grid: { drawOnChartArea: false }, beginAtZero: false, title: { display: true, text: 'Жир (%)', color: '#e74c3c' } };
        } else if (mode === 'girths') {
            girthKeys.forEach(function(k, i){
                var pts = anthroAllData[k] || [];
                var d = buildDict(pts);
                datasets.push({
                    label: k, data: anthroLabels.map(function(l){ return d[l] !== undefined ? d[l] : null; }),
                    borderColor: girthColors[i], backgroundColor: 'transparent',
                    tension: 0.3, spanGaps: true, pointRadius: 3, borderWidth: 2,
                });
            });
            scales.y = { type: 'linear', display: true, position: 'left', ticks: { color: '#999' }, grid: { color: '#333' }, beginAtZero: false, title: { display: true, text: 'Обхваты (см)', color: '#999' } };
        } else if (mode === 'skinfold') {
            skinfoldKeys.forEach(function(k, i){
                var pts = anthroAllData[k] || [];
                var d = buildDict(pts);
                datasets.push({
                    label: k, data: anthroLabels.map(function(l){ return d[l] !== undefined ? d[l] : null; }),
                    borderColor: skinfoldColors[i], backgroundColor: 'transparent',
                    tension: 0.3, spanGaps: true, pointRadius: 3, borderWidth: 2,
                });
            });
            scales.y = { type: 'linear', display: true, position: 'left', ticks: { color: '#999' }, grid: { color: '#333' }, beginAtZero: false, title: { display: true, text: 'Калипер (мм)', color: '#999' } };
        }

        if (anthroChart) anthroChart.destroy();

        anthroChart = new Chart(document.getElementById('anthroChart'), {
            type: 'line',
            data: { labels: anthroLabels, datasets: datasets },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color: '#ccc', boxWidth: 12, padding: 8 } } },
                scales: scales
            }
        });
    };

    var anthroSel = document.getElementById('anthroSelect');
    if (anthroSel) {
        window.buildAnthroChart(anthroSel.value);
        anthroSel.addEventListener('change', function(){ window.buildAnthroChart(this.value); });
    }
})();
