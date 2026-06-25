/* schedule.js — клик по пустой ячейке → автозаполнение формы */
(function(){
    var days = window.__schedule_days || [];
    if (!days.length) return;
    document.querySelectorAll('.calendar__cell--empty').forEach(function(el){
        el.style.cursor = 'pointer';
        el.title = 'Кликните, чтобы создать слот';
        el.addEventListener('click', function(){
            var d = parseInt(this.dataset.day);
            var h = parseInt(this.dataset.hour);
            var date = days[d];
            var startInput = document.querySelector('input[name="start_time"]');
            var endInput = document.querySelector('input[name="end_time"]');
            if (startInput && endInput) {
                startInput.value = date + 'T' + ('0' + h).slice(-2) + ':00';
                endInput.value = date + 'T' + ('0' + (h + 1)).slice(-2) + ':00';
                startInput.scrollIntoView({behavior:'smooth',block:'center'});
                startInput.focus();
            }
        });
    });
})();
