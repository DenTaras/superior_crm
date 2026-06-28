/* gallery.js — анимация секций при скролле */
(function(){
    // Скрываем хедер на странице галереи для полного погружения
    var header = document.querySelector('.header');
    if (header) header.style.display = 'none';

    var sections = document.querySelectorAll('.gallery-section');
    if (!sections.length) return;

    var observer = new IntersectionObserver(function(entries){
        entries.forEach(function(entry){
            if (entry.isIntersecting) {
                entry.target.classList.add('gallery-section--visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.15 });

    sections.forEach(function(s){ observer.observe(s); });
})();
