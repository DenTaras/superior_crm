/* profile-tabs.js — переключение вкладок в профиле клиента */
(function(){
    window.switchTab = function(name) {
        document.querySelectorAll('.tab-content').forEach(function(el){
            el.style.display = 'none';
        });
        document.querySelectorAll('.tab-btn').forEach(function(el){
            el.className = el.className.replace('btn--primary', 'btn--secondary');
        });
        document.getElementById('tab-' + name).style.display = '';
        document.querySelector('.tab-btn[data-tab="' + name + '"]').className =
            'btn btn--primary btn--small tab-btn';

        if (name === 'strength') {
            var sel = document.getElementById('exerciseSelect');
            if (sel && typeof window.buildChart === 'function') {
                setTimeout(function(){ window.buildChart(sel.value); }, 100);
            }
        }
        if (name === 'anthro') {
            var anthroSel = document.getElementById('anthroSelect');
            if (anthroSel && typeof window.buildAnthroChart === 'function') {
                setTimeout(function(){ window.buildAnthroChart(anthroSel.value); }, 100);
            }
        }
    };
})();
