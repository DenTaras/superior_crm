/* program-table.js — таблица упражнений + перенос из таблицы */
(function(){
    var app = window.SlotApp;
    if (!app) return;

    var section = document.getElementById('plan-exercises-section');
    var tbody = document.getElementById('plan-exercises-body');

    app.loadPlanExercises = function(){
        if(!app.selected){ section.style.display = 'none'; return; }
        fetch('/api/plan-exercises?slot_id=' + app.slotId + '&client_id=' + app.selected)
            .then(function(r){ return r.json(); })
            .then(function(data){
                if(!data || data.length === 0){ section.style.display = 'none'; return; }
                section.style.display = '';
                tbody.innerHTML = '';
                data.forEach(function(ex, idx){
                    var tr = document.createElement('tr');
                    tr.appendChild(cell(idx + 1));
                    tr.appendChild(cell(ex.exercise_name));

                    // Свой вес
                    var tdBW = cell((ex.uses_bodyweight && ex.client_weight) ? ex.client_weight : '');
                    tr.appendChild(tdBW);

                    // Вес снаряда (редактируемый)
                    var tdW = document.createElement('td'); tdW.className = 'plan-table__cell';
                    var wInp = document.createElement('input');
                    wInp.type = 'number'; wInp.className = 'plan-table__input'; wInp.min = '0';
                    wInp.value = ex.weight || ''; wInp.placeholder = '—';
                    wInp.addEventListener('change', function(){
                        var v = this.value !== '' ? parseInt(this.value) : 0;
                        fetch('/api/plan-exercises/update', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({id: ex.id, weight: v})
                        });
                    });
                    tdW.appendChild(wInp); tr.appendChild(tdW);

                    // Цель
                    tr.appendChild(cell(ex.target_reps || '—'));

                    // Факт (редактируемый)
                    var tdA = document.createElement('td'); tdA.className = 'plan-table__cell';
                    var aInp = document.createElement('input');
                    aInp.type = 'number'; aInp.className = 'plan-table__input'; aInp.min = '0';
                    aInp.value = ex.actual_reps !== null && ex.actual_reps !== undefined ? ex.actual_reps : '';
                    aInp.placeholder = '—';
                    aInp.addEventListener('change', function(){
                        var v = this.value !== '' ? parseInt(this.value) : null;
                        fetch('/api/plan-exercises/update', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({id: ex.id, actual_reps: v})
                        });
                    });
                    tdA.appendChild(aInp); tr.appendChild(tdA);

                    // Удалить
                    var tdD = document.createElement('td');
                    var dBtn = document.createElement('button');
                    dBtn.className = 'btn btn--ghost btn--small';
                    dBtn.textContent = '✕'; dBtn.title = 'Удалить';
                    dBtn.addEventListener('click', function(){
                        var csrf = (document.querySelector('input[name="_csrf_token"]') || {}).value || '';
                        fetch('/api/plan-exercises/delete/' + ex.id, {
                            method: 'POST', headers: { 'X-CSRF-Token': csrf, 'Content-Type': 'application/json' }
                        }).then(function(){ if(typeof app.loadPlanExercises === 'function') app.loadPlanExercises(); });
                    });
                    tdD.appendChild(dBtn); tr.appendChild(tdD);
                    tbody.appendChild(tr);
                });
            });
    };

    function cell(text){
        var td = document.createElement('td'); td.className = 'plan-table__cell';
        td.textContent = text; return td;
    }

    // ---------- ПЕРЕНЕСТИ ИЗ ТАБЛИЦЫ ----------
    document.getElementById('btn-from-table').addEventListener('click', function(){
        if(!app.selected) return;
        fetch('/api/plan-exercises?slot_id=' + app.slotId + '&client_id=' + app.selected)
            .then(function(r){ return r.json(); })
            .then(function(data){
                if(!data || data.length === 0){ alert('Нет упражнений в таблице.'); return; }
                var groups = [], currentGroup = null;
                data.forEach(function(ex){
                    if(!currentGroup || currentGroup.name !== ex.exercise_name){
                        currentGroup = {name: ex.exercise_name, sets: []}; groups.push(currentGroup);
                    }
                    currentGroup.sets.push(ex);
                });
                var lines = [];
                groups.forEach(function(g){
                    lines.push(''); lines.push(g.name + ':');
                    g.sets.forEach(function(ex, i){
                        var w = ex.weight ? ex.weight + ' кг' : 'свой вес';
                        var a = ex.actual_reps !== null && ex.actual_reps !== undefined ? ex.actual_reps + ' раз' : '___ раз';
                        var t = ex.target_reps ? ex.target_reps + ' раз' : '';
                        lines.push('  подход ' + (i+1) + ': вес (' + w + '), цель ' + t + ', факт ' + a);
                    });
                });
                lines.push('');
                app.textarea.value = (app.textarea.value || '') + lines.join('\n');
                app.doSave(app.selected);
            });
    });
})();
