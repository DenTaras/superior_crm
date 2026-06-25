/* program-constructor.js — модалка конструктора тренировки */
(function(){
    var app = window.SlotApp;
    if (!app) return;

    var modal = document.getElementById('constructor-modal');
    var stepGroups = document.getElementById('step-groups');
    var stepExercises = document.getElementById('step-exercises');
    var stepSettings = document.getElementById('step-settings');
    var groupsList = document.getElementById('groups-list');
    var exercisesList = document.getElementById('exercises-list');
    var selectedGroupName = document.getElementById('selected-group-name');
    var selectedExerciseName = document.getElementById('selected-exercise-name');
    var exWeight = document.getElementById('ex-weight');
    var exReps = document.getElementById('ex-reps');
    var exSets = document.getElementById('ex-sets');
    var progressHint = document.getElementById('progress-hint');

    var currentGroupId = null;
    var currentExerciseId = null;

    function showStep(stepId){
        stepGroups.style.display = stepId === 'groups' ? '' : 'none';
        stepExercises.style.display = stepId === 'exercises' ? '' : 'none';
        stepSettings.style.display = stepId === 'settings' ? '' : 'none';
    }

    function loadGroups(){
        fetch('/api/exercise-groups').then(function(r){ return r.json(); }).then(function(data){
            groupsList.innerHTML = '';
            data.forEach(function(g){
                var btn = document.createElement('button');
                btn.className = 'btn btn--secondary constructor-btn';
                btn.textContent = g.name;
                btn.addEventListener('click', function(){ loadExercises(g.id, g.name); });
                groupsList.appendChild(btn);
            });
        });
    }

    function loadExercises(groupId, groupName){
        currentGroupId = groupId;
        selectedGroupName.textContent = groupName;
        fetch('/api/exercises?group_id=' + groupId).then(function(r){ return r.json(); }).then(function(data){
            exercisesList.innerHTML = '';
            data.forEach(function(ex){
                var btn = document.createElement('button');
                btn.className = 'btn btn--secondary constructor-btn';
                btn.textContent = ex.name;
                btn.addEventListener('click', function(){ openSettings(ex.id, ex.name); });
                exercisesList.appendChild(btn);
            });
            showStep('exercises');
        });
    }

    function openSettings(exerciseId, exerciseName){
        currentExerciseId = exerciseId;
        selectedExerciseName.textContent = exerciseName;
        exWeight.value = '0';
        exReps.value = '10';
        exSets.value = '3';
        progressHint.textContent = '';

        if(app.selected){
            fetch('/api/exercise-log?client_id=' + app.selected + '&exercise_id=' + exerciseId)
                .then(function(r){ return r.json(); })
                .then(function(data){
                    if(data.found){
                        exWeight.value = data.suggested_weight;
                        exReps.value = data.suggested_reps;
                        exSets.value = data.last_sets;
                        progressHint.textContent = 'Предыдущий: ' + data.last_weight + ' кг × ' + data.last_reps + ' повт. Прогрессия +5% → ' + data.suggested_weight + ' кг × ' + data.suggested_reps + ' повт.';
                    } else {
                        progressHint.textContent = 'Новое упражнение. Рекомендуется начать с минимального веса.';
                    }
                });
        } else {
            progressHint.textContent = 'Выберите клиента слева, чтобы подгрузить историю.';
        }
        showStep('settings');
    }

    document.getElementById('btn-constructor').addEventListener('click', function(){
        if(!app.selected){ alert('Сначала выберите клиента слева.'); return; }
        loadGroups();
        showStep('groups');
        modal.style.display = '';
    });

    document.getElementById('modal-close').addEventListener('click', function(){ modal.style.display = 'none'; });
    modal.addEventListener('click', function(e){ if(e.target === modal) modal.style.display = 'none'; });
    document.getElementById('btn-back-groups').addEventListener('click', function(){ loadGroups(); showStep('groups'); });
    document.getElementById('btn-back-exercises').addEventListener('click', function(){ loadExercises(currentGroupId, selectedGroupName.textContent); });

    document.getElementById('btn-add-exercise').addEventListener('click', function(){
        var weight = parseInt(exWeight.value) || 0;
        var reps = parseInt(exReps.value) || 0;
        var sets = parseInt(exSets.value) || 0;
        if(weight === 0 && reps === 0){ alert('Заполните вес и/или количество повторений.'); return; }

        var promises = [];
        for(var s = 1; s <= sets; s++){
            promises.push(fetch('/api/plan-exercises/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    slot_id: app.slotId, client_id: parseInt(app.selected),
                    exercise_id: currentExerciseId, weight: weight, target_reps: reps, sets: 1
                })
            }));
        }
        Promise.all(promises).then(function(){ if(typeof app.loadPlanExercises === 'function') app.loadPlanExercises(); });
        modal.style.display = 'none';
    });
})();
