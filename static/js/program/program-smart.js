/* program-smart.js — модалка Smart */
(function(){
    var app = window.SlotApp;
    if (!app) return;

    var smartModal = document.getElementById('smart-modal');
    var smartStatus = document.getElementById('smart-status');

    document.getElementById('btn-smart').addEventListener('click', function(){
        if(!app.selected){ alert('Сначала выберите клиента слева.'); return; }
        smartStatus.style.display = 'none';
        smartModal.style.display = '';
    });

    document.getElementById('smart-modal-close').addEventListener('click', function(){ smartModal.style.display = 'none'; });
    smartModal.addEventListener('click', function(e){ if(e.target === smartModal) smartModal.style.display = 'none'; });

    document.querySelectorAll('#smart-splits .constructor-btn').forEach(function(btn){
        btn.addEventListener('click', function(){
            var split = this.getAttribute('data-split');
            var names = {legs_shoulders:'Ноги+Плечи', chest:'Грудь', back:'Спина', fullbody:'Фулбади'};
            smartStatus.style.display = '';
            smartStatus.textContent = 'Генерирую программу «' + (names[split] || split) + '»...';

            fetch('/api/smart-program', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({slot_id: app.slotId, client_id: parseInt(app.selected), split: split})
            }).then(function(r){ return r.json(); }).then(function(data){
                smartModal.style.display = 'none';
                if(data.ok){ if(typeof app.loadPlanExercises === 'function') app.loadPlanExercises(); }
                else { alert('Ошибка: ' + (data.error || 'неизвестная')); }
            }).catch(function(){ smartModal.style.display = 'none'; alert('Ошибка сети при генерации программы.'); });
        });
    });
})();
