/* gallery.js — анимация секций при скролле + модалка просмотра фото */
(function(){
    var header = document.querySelector('.header');
    if (header && window.innerWidth > 768) header.style.display = 'none';

    // Анимация секций при скролле
    var sections = document.querySelectorAll('.gallery-section');
    if (sections.length) {
        var observer = new IntersectionObserver(function(entries){
            entries.forEach(function(entry){
                if (entry.isIntersecting) {
                    entry.target.classList.add('gallery-section--visible');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });
        sections.forEach(function(s){ observer.observe(s); });
    }

    // ====== Модалка просмотра фото ======
    var modal = document.getElementById('photo-modal');
    var modalImg = document.getElementById('photo-modal-img');
    var closeBtn = document.getElementById('photo-modal-close');

    if (!modal || !modalImg) return;

    function openModal(bgUrl) {
        var match = bgUrl.match(/url\(['"]?(.*?)['"]?\)/);
        var src = match ? match[1] : '';
        if (!src) return;
        modalImg.style.backgroundImage = "url('" + src + "')";
        modal.classList.add('photo-modal--open');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modal.classList.remove('photo-modal--open');
        document.body.style.overflow = '';
    }

    document.querySelectorAll('.gallery-photo').forEach(function(photo){
        photo.addEventListener('click', function(e) {
            if (e.target.closest('.gallery-photo__label')) return;
            var bg = window.getComputedStyle(photo).backgroundImage;
            if (bg && bg !== 'none') openModal(bg);
        });
    });

    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', function(e) {
        if (e.target === modal) closeModal();
    });
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeModal();
    });
})();
