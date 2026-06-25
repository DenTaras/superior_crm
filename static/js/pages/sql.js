/* sql.js — автосохранение заметок в localStorage */
(function(){
    var ta = document.getElementById('sql-notes');
    if (!ta) return;
    var status = document.getElementById('notes-status');
    var STORAGE_KEY = 'superior_sql_notes';

    try {
        var saved = localStorage.getItem(STORAGE_KEY);
        if (saved) ta.value = saved;
    } catch(e) {}

    var timeout = null;
    ta.addEventListener('input', function(){
        status.textContent = 'Сохранение...';
        if (timeout) clearTimeout(timeout);
        timeout = setTimeout(function(){
            timeout = null;
            try {
                localStorage.setItem(STORAGE_KEY, ta.value);
                status.textContent = 'Сохранено';
            } catch(e) {
                status.textContent = 'Ошибка сохранения';
            }
            setTimeout(function(){ status.textContent = 'Автосохранение'; }, 1500);
        }, 300);
    });

    window.addEventListener('beforeunload', function(){
        try { localStorage.setItem(STORAGE_KEY, ta.value); } catch(e) {}
    });
})();
