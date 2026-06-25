/* slot-program-core.js — ядро страницы программы тренировки */
(function(){
    var el = document.getElementById('slot-program');
    if (!el) return;

    window.SlotApp = {
        slotId: parseInt(el.getAttribute('data-slot-id')),
        weekOffset: parseInt(el.getAttribute('data-week-offset')) || 0,
        selected: null,
        notes: {},
        textarea: document.getElementById('note-text'),
        status: document.getElementById('save-status'),
        clients: Array.from(document.querySelectorAll('.client-list__item--interactive')),
    };

    var app = window.SlotApp;
    var notesEl = document.getElementById('notes-data');
    if (notesEl) {
        try { app.notes = JSON.parse(notesEl.textContent); } catch(e) {}
    }

    var timeout = null;
    var pendingClient = null;

    app.doSave = function(clientId){
        if (!clientId) return Promise.resolve();
        app.status.textContent = 'Сохранение...';
        return fetch('/slot/' + app.slotId + '/program/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: clientId, text: app.textarea.value || '' })
        }).then(function(r){ return r.json(); }).then(function(j){
            app.notes[clientId] = app.textarea.value || '';
            app.status.textContent = 'Сохранено';
            setTimeout(function(){ app.status.textContent = 'Автосохранение включено'; }, 900);
        }).catch(function(){ app.status.textContent = 'Ошибка сохранения'; });
    };

    app.selectClient = function(el){
        app.clients.forEach(function(it){ it.classList.remove('client-list__item--selected'); });
        el.classList.add('client-list__item--selected');
        app.selected = el.getAttribute('data-client-id');
        app.textarea.value = app.notes[app.selected] || '';
        app.textarea.focus();
        if (typeof app.loadPlanExercises === 'function') app.loadPlanExercises();
    };

    app.clients.forEach(function(el, idx){
        el.addEventListener('click', function(){
            if (timeout){ clearTimeout(timeout); timeout = null; if (app.selected) pendingClient = app.selected; }
            var doSwitch = function(){ app.selectClient(el); };
            if (pendingClient){ app.doSave(pendingClient).then(function(){ pendingClient = null; doSwitch(); }); }
            else { doSwitch(); }
        });
        if (idx === 0) app.selectClient(el);
    });

    app.textarea.addEventListener('input', function(){
        app.status.textContent = 'Сохранение...';
        if (timeout) clearTimeout(timeout);
        timeout = setTimeout(function(){
            var cid = app.selected;
            timeout = null;
            app.doSave(cid);
        }, 300);
    });

    window.addEventListener('beforeunload', function(e){
        if (timeout) { clearTimeout(timeout); timeout = null; }
        if (app.selected){
            var csrf = (document.querySelector('input[name="_csrf_token"]') || {}).value || '';
            var params = new URLSearchParams({client_id: app.selected, text: app.textarea.value, _csrf_token: csrf});
            var blob = new Blob([params], { type: 'application/x-www-form-urlencoded' });
            if (navigator.sendBeacon) navigator.sendBeacon('/slot/' + app.slotId + '/program/save', blob);
        }
    });
})();
