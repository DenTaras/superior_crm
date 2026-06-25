/* nutrition.js — переключение дней, КБЖУ, добавление/замена блюд */
(function(){
    var alternatives = window.__nutrition_alternatives || [];

    // Переключение дней
    document.querySelectorAll('.day-btn').forEach(function(btn){
        btn.addEventListener('click', function(){
            var day = this.dataset.day;
            document.querySelectorAll('.day-table').forEach(function(t){ t.style.display = 'none'; });
            var tab = document.getElementById('day-' + day);
            if (tab) tab.style.display = '';
            document.querySelectorAll('.day-btn').forEach(function(b){ b.classList.remove('btn--primary'); b.classList.add('btn--ghost'); });
            this.classList.remove('btn--ghost'); this.classList.add('btn--primary');
        });
    });

    function recalcItem(item) {
        var baseW = parseFloat(item.dataset.baseWeight) || 1;
        var input = item.querySelector('.meal-weight');
        var newW = parseFloat(input.value) || baseW;
        var ratio = newW / baseW;
        item.querySelector('.meal-protein .meal-value').textContent = Math.round(parseFloat(item.dataset.baseProtein) * ratio);
        item.querySelector('.meal-fat .meal-value').textContent = Math.round(parseFloat(item.dataset.baseFat) * ratio);
        item.querySelector('.meal-carbs .meal-value').textContent = Math.round(parseFloat(item.dataset.baseCarbs) * ratio);
        item.querySelector('.meal-calories .meal-value').textContent = Math.round(parseFloat(item.dataset.baseCalories) * ratio);
        recalcTotalFrom(item.closest('.day-table'));
    }

    function recalcTotalFrom(dayTable) {
        if (!dayTable) return;
        var items = dayTable.querySelectorAll('.meal-item');
        var total = {weight:0, protein:0, fat:0, carbs:0, calories:0};
        items.forEach(function(it){
            var w = parseFloat(it.querySelector('.meal-weight').value) || 0;
            total.weight += w;
            total.protein += parseInt(it.querySelector('.meal-protein .meal-value').textContent) || 0;
            total.fat += parseInt(it.querySelector('.meal-fat .meal-value').textContent) || 0;
            total.carbs += parseInt(it.querySelector('.meal-carbs .meal-value').textContent) || 0;
            total.calories += parseInt(it.querySelector('.meal-calories .meal-value').textContent) || 0;
        });
        dayTable.querySelector('.total-weight').textContent = total.weight;
        dayTable.querySelector('.total-protein').textContent = total.protein;
        dayTable.querySelector('.total-fat').textContent = total.fat;
        dayTable.querySelector('.total-carbs').textContent = total.carbs;
        dayTable.querySelector('.total-calories').textContent = total.calories;
    }

    // Изменение веса
    document.addEventListener('input', function(e){
        if (e.target.classList.contains('meal-weight')) {
            var item = e.target.closest('.meal-item');
            if (item) recalcItem(item);
        }
    });

    // Удаление блюда
    document.addEventListener('click', function(e){
        if (e.target.classList.contains('meal-remove')) {
            var item = e.target.closest('.meal-item');
            if (!item) return;
            var dayTable = item.closest('.day-table');
            item.remove();
            if (dayTable) recalcTotalFrom(dayTable);
        }
    });

    // Добавить блюдо
    document.addEventListener('click', function(e){
        if (!e.target.classList.contains('meal-add')) return;
        var btn = e.target;
        var panel = btn.closest('.panel');
        if (!panel) return;
        var h4 = panel.querySelector('h4');
        var typeMap = {'Завтрак':'breakfast','Перекус':'snack','Обед':'lunch','Ужин':'dinner'};
        var mealType = typeMap[h4 ? h4.textContent.trim() : ''] || '';
        var block = panel.querySelector('.meals-block');
        if (!block) return;

        var select = btn.parentElement.querySelector('.course-select');
        if (!select) return;
        var courseKey = select.value;
        var courseLabel = select.options[select.selectedIndex].text;

        var pool;
        if (mealType === 'snack') {
            if (courseKey === 'drink') {
                pool = alternatives.filter(function(m){ return m.meal_type === 'snack' && m.course === 'drink'; });
            } else {
                pool = alternatives.filter(function(m){ return m.meal_type === 'snack' && (m.course || 'main') === 'main'; });
            }
        } else {
            pool = alternatives.filter(function(m){ return (m.course || 'main') === courseKey; });
        }
        if (pool.length === 0) { alert('Нет подходящих блюд для этой категории.'); return; }
        var pick = pool[Math.floor(Math.random() * pool.length)];

        var html = '<div class="meal-item" style="background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:10px 14px;margin-bottom:6px;"' +
            ' data-meal-id="' + pick.id + '"' +
            ' data-base-weight="' + pick.weight_g + '"' +
            ' data-base-protein="' + pick.protein + '" data-base-fat="' + pick.fat + '"' +
            ' data-base-carbs="' + pick.carbs + '" data-base-calories="' + pick.calories + '"' +
            ' data-ingredients="' + (pick.ingredients||'') + '" data-recipe="' + (pick.recipe||'') + '">' +
            '<div class="flex-row" style="gap:8px;align-items:center;flex-wrap:wrap;">' +
            '<button class="btn btn--small meal-remove" style="padding:2px 6px;color:var(--danger);">−</button>' +
            '<span style="font-weight:600;font-size:0.85rem;min-width:60px;color:var(--text-muted);">' + courseLabel + '</span>' +
            '<span class="meal-name" style="flex:1;cursor:pointer;font-size:0.9rem;">' + pick.name + '</span>' +
            '<span style="font-size:0.8rem;color:var(--text-muted);">' + pick.weight_g + 'г</span>' +
            '<input type="number" class="meal-weight" value="' + pick.weight_g + '" min="1" style="width:50px;padding:2px 4px;border:1px solid var(--border);border-radius:4px;background:var(--bg-card);color:var(--text-primary);font-size:0.8rem;">' +
            '<span class="meal-protein" style="font-size:0.8rem;min-width:45px;"><span style="color:var(--text-muted);font-size:0.7rem;">Б </span><span class="meal-value">' + pick.protein + '</span></span>' +
            '<span class="meal-fat" style="font-size:0.8rem;min-width:45px;"><span style="color:var(--text-muted);font-size:0.7rem;">Ж </span><span class="meal-value">' + pick.fat + '</span></span>' +
            '<span class="meal-carbs" style="font-size:0.8rem;min-width:45px;"><span style="color:var(--text-muted);font-size:0.7rem;">У </span><span class="meal-value">' + pick.carbs + '</span></span>' +
            '<span class="meal-calories" style="font-size:0.85rem;font-weight:600;min-width:55px;"><span style="color:var(--text-muted);font-size:0.7rem;">ккал </span><span class="meal-value">' + pick.calories + '</span></span>' +
            '<button class="btn btn--small meal-prev" style="padding:2px 6px;">◀</button>' +
            '<button class="btn btn--small meal-next" style="padding:2px 6px;">▶</button>' +
            '</div>' +
            '<div class="meal-detail" style="display:none;margin-top:6px;font-size:0.8rem;color:var(--text-secondary);padding-left:70px;">' +
            '<strong>Состав:</strong> ' + (pick.ingredients||'—') + '<br>' +
            '<strong>Приготовление:</strong> ' + (pick.recipe||'—') + '</div></div>';

        block.insertAdjacentHTML('beforeend', html);
        var dt = panel.closest('.day-table');
        if (dt) recalcTotalFrom(dt);
    });

    // Клик по названию — показать/скрыть состав
    document.addEventListener('click', function(e){
        var nameEl = e.target.closest('.meal-name');
        if (!nameEl) return;
        var item = nameEl.closest('.meal-item');
        if (!item) return;
        var detail = item.querySelector('.meal-detail');
        if (detail) {
            detail.style.display = detail.style.display === 'none' ? '' : 'none';
        }
    });

    // Замена блюда (◀ ▶)
    document.addEventListener('click', function(e){
        var btn = e.target.closest('.meal-prev, .meal-next');
        if (!btn) return;
        var item = btn.closest('.meal-item');
        if (!item) return;
        var nameEl = item.querySelector('.meal-name');
        var weightInput = item.querySelector('.meal-weight');

        var mealType = '';
        var parentBlock = item.closest('.panel');
        if (parentBlock) {
            var h4 = parentBlock.querySelector('h4');
            var typeMap = {'Завтрак':'breakfast','Перекус':'snack','Обед':'lunch','Ужин':'dinner'};
            mealType = typeMap[h4 ? h4.textContent.trim() : ''] || '';
        }
        var spans = item.querySelectorAll('.flex-row > span');
        var courseLabel = '';
        for (var s = 0; s < spans.length; s++) {
            var txt = spans[s].textContent.trim();
            if (txt.indexOf('Первое') !== -1) { courseLabel = 'first'; break; }
            if (txt.indexOf('Второе') !== -1) { courseLabel = 'main'; break; }
            if (txt.indexOf('Перекус') !== -1) { courseLabel = 'main'; break; }
            if (txt.indexOf('Напиток') !== -1) { courseLabel = 'drink'; break; }
        }
        var course = courseLabel || 'main';

        var pool;
        if (mealType === 'snack') {
            if (course === 'drink') {
                pool = alternatives.filter(function(m){ return m.meal_type === 'snack' && m.course === 'drink'; });
            } else {
                pool = alternatives.filter(function(m){ return m.meal_type === 'snack' && (m.course || 'main') === 'main'; });
            }
        } else {
            pool = alternatives.filter(function(m){ return (m.course || 'main') === course; });
        }
        if (pool.length < 2) return;

        var direction = btn.classList.contains('meal-next') ? 1 : -1;
        var curId = parseInt(item.dataset.mealId);
        var curIdx = -1;
        if (curId) {
            curIdx = pool.findIndex(function(m){ return m.id === curId; });
        }
        if (curIdx === -1) {
            var curName = nameEl.textContent;
            curIdx = pool.findIndex(function(m){ return m.name === curName; });
        }
        if (curIdx === -1) curIdx = 0;
        var newIdx = (curIdx + direction + pool.length) % pool.length;
        if (newIdx === curIdx) return;
        var pick = pool[newIdx];

        nameEl.textContent = pick.name;
        item.dataset.mealId = pick.id;
        item.dataset.baseWeight = pick.weight_g;
        item.dataset.baseProtein = pick.protein;
        item.dataset.baseFat = pick.fat;
        item.dataset.baseCarbs = pick.carbs;
        item.dataset.baseCalories = pick.calories;
        item.dataset.ingredients = pick.ingredients || '';
        item.dataset.recipe = pick.recipe || '';
        weightInput.value = pick.weight_g;

        var detail = item.querySelector('.meal-detail');
        if (detail) {
            detail.innerHTML = '<strong>Состав:</strong> ' + (pick.ingredients || '—') + '<br>' +
                '<strong>Приготовление:</strong> ' + (pick.recipe || '—');
        }
        recalcItem(item);
    });
})();
