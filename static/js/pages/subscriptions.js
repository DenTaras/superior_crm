/* subscriptions.js — форма оплаты */
document.getElementById('paymentForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    var btn = document.getElementById('payBtn');
    var status = document.getElementById('paymentStatus');
    btn.disabled = true;
    status.textContent = 'Создание платежа…';
    status.style.color = 'var(--text-secondary)';

    try {
        var resp = await fetch('/api/create-payment', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: new URLSearchParams({
                'time_slot': document.getElementById('ts').value,
                'format_name': document.getElementById('fmt').value,
                'package_size': document.getElementById('pkg').value,
            }),
        });
        var data = await resp.json();
        if (data.redirect_url) {
            window.location.href = data.redirect_url;
        } else if (data.error) {
            status.textContent = 'Ошибка: ' + data.error;
            status.style.color = 'var(--danger)';
        }
    } catch (err) {
        status.textContent = 'Ошибка соединения';
        status.style.color = 'var(--danger)';
    } finally {
        btn.disabled = false;
    }
});
