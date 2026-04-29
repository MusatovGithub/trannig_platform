(function () {
  const root = document.getElementById("competitionResultsRoot");
  if (!root) {
    return;
  }

  const reloadBtn = document.getElementById("competitionResultsReload");
  const resultsUrl = root.dataset.resultsUrl;

  const templates = {
    loading() {
      return `
        <div class="text-center py-4">
          <div class="spinner-border" role="status"></div>
          <div>Загрузка результатов...</div>
        </div>`;
    },
    error(message) {
      return `<div class="alert alert-danger mb-0">${message}</div>`;
    },
    empty() {
      return `<div class="alert alert-info mb-0">Результаты ещё не добавлены.</div>`;
    },
  };

  function formatResultRow(participant, result) {
    const timeOrStatus = result.is_disqualified
      ? '<span class="badge bg-danger">Дисквалифицирован</span>'
      : result.result_time || "—";

    const place = result.is_disqualified
      ? '<span class="text-muted">—</span>'
      : result.place || "—";

    const rankBadge = result.sport_category
      ? `<span class="badge bg-success">${result.sport_category}</span>`
      : '<span class="text-muted">—</span>';

    return `
      <tr>
        <td>${participant.name}</td>
        <td>${participant.phone || "—"}</td>
        <td>${result.distance} м</td>
        <td>${result.discipline || "—"}</td>
        <td>${result.style || "—"}</td>
        <td>${timeOrStatus}</td>
        <td>${place}</td>
        <td>${rankBadge}</td>
      </tr>`;
  }

  function formatParticipantWithoutResults(participant) {
    return `
      <tr>
        <td>${participant.name}</td>
        <td>${participant.phone || "—"}</td>
        <td colspan="6" class="text-muted">Результаты отсутствуют</td>
      </tr>`;
  }

  function renderTable(data) {
    if (!data.length) {
      root.innerHTML = templates.empty();
      return;
    }

    let rowsHtml = "";
    data.forEach((item) => {
      if (!item.results.length) {
        rowsHtml += formatParticipantWithoutResults(item.participant);
        return;
      }

      item.results.forEach((result) => {
        rowsHtml += formatResultRow(item.participant, result);
      });
    });

    root.innerHTML = `
      <div class="table-responsive mb-0">
        <table class="table align-middle mb-0">
          <thead>
            <tr>
              <th>Участник</th>
              <th>Телефон</th>
              <th>Дистанция</th>
              <th>Дисциплина</th>
              <th>Бассейн</th>
              <th>Время/Статус</th>
              <th>Место</th>
              <th>Разряд</th>
            </tr>
          </thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>`;
  }

  function loadResults() {
    root.innerHTML = templates.loading();

    fetch(resultsUrl, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Не удалось загрузить результаты");
        }
        return response.json();
      })
      .then((payload) => {
        if (!payload.success) {
          throw new Error(payload.error || "Неизвестная ошибка");
        }
        renderTable(payload.data || []);
      })
      .catch((error) => {
        root.innerHTML = templates.error(error.message);
      });
  }

  if (reloadBtn) {
    reloadBtn.addEventListener("click", loadResults);
  }

  loadResults();
})();

