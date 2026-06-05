(function () {
  function onlyDigits(value) {
    return (value || '').replace(/\D/g, '');
  }

  function formatMoney(value) {
    const digits = onlyDigits(value);
    if (!digits) {
      return '';
    }

    const amount = (parseInt(digits, 10) / 100).toFixed(2);
    const parts = amount.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return parts.join(',');
  }

  document.addEventListener('input', function (event) {
    const input = event.target;
    if (!input.matches('[data-mask="money"]')) {
      return;
    }
    input.value = formatMoney(input.value);
  });
})();
