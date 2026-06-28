/* mobile-menu.js — бургер-меню для мобильных устройств */
(function(){
    var burger = document.getElementById('burger-btn');
    var nav = document.getElementById('mobile-nav');
    var overlay = document.getElementById('mobile-overlay');
    if (!burger || !nav) return;

    function openMenu(){
        nav.classList.add('header__nav--open');
        if (overlay) overlay.classList.add('mobile-overlay--visible');
        burger.classList.add('burger--active');
        document.body.style.overflow = 'hidden';
    }

    function closeMenu(){
        nav.classList.remove('header__nav--open');
        if (overlay) overlay.classList.remove('mobile-overlay--visible');
        burger.classList.remove('burger--active');
        document.body.style.overflow = '';
    }

    burger.addEventListener('click', function(){
        if (nav.classList.contains('header__nav--open')) {
            closeMenu();
        } else {
            openMenu();
        }
    });

    // Закрытие по клику на ссылку
    nav.querySelectorAll('a').forEach(function(link){
        link.addEventListener('click', closeMenu);
    });

    // Закрытие по оверлею
    if (overlay) overlay.addEventListener('click', closeMenu);

    // Закрытие по Escape
    document.addEventListener('keydown', function(e){
        if (e.key === 'Escape') closeMenu();
    });
})();
