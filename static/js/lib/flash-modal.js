/* flash-modal.js — авто-закрывающаяся модалка с countdown */
(function(){
    var modal = document.getElementById('flash-modal');
    if(!modal) return;
    var close = document.getElementById('flash-close');
    var countdown = document.getElementById('flash-countdown');
    var seconds = parseInt(modal.getAttribute('data-seconds')) || 5;
    function hide(){
        modal.parentNode && modal.parentNode.removeChild(modal);
        if(window.history && window.history.replaceState) window.history.replaceState({}, '', window.location.pathname);
    }
    close && close.addEventListener('click', hide);
    document.addEventListener('keydown', function(e){ if(e.key === 'Escape') hide(); });
    if(countdown) countdown.textContent = seconds;
    var timer = setInterval(function(){
        seconds--;
        if(countdown) countdown.textContent = seconds;
        if(seconds <= 0){ clearInterval(timer); hide(); }
    }, 1000);
})();
