(() => {
  function escapeHtml(value) {
    if (!value && value !== 0) {
      return '';
    }
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatNumber(value, fractionDigits = 2) {
    if (value === null || value === undefined) {
      return '—';
    }
    const number = Number(value);
    if (Number.isNaN(number)) {
      return '—';
    }
    return number.toLocaleString('ru-RU', {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits
    });
  }

  function formatDateTime(value) {
    if (!value) {
      return '';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return '';
    }
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  }

  function formatTime(value) {
    if (!value) {
      return '—';
    }
    const [hours, minutes] = value.split(':');
    if (!hours) {
      return '—';
    }
    return `${hours}:${minutes || '00'}`;
  }

  function truncateText(text, maxLength = 80) {
    if (!text) {
      return '';
    }
    const normalized = text.trim();
    if (normalized.length <= maxLength) {
      return normalized;
    }
    return `${normalized.slice(0, maxLength - 1).trim()}…`;
  }

  function fetchJson(url) {
    return fetch(url, {
      method: 'GET',
      credentials: 'same-origin',
      headers: {
        'Accept': 'application/json'
      }
    }).then((response) => {
      if (!response.ok) {
        throw new Error(`Запрос завершился с ошибкой ${response.status}`);
      }
      return response.json();
    });
  }

  function showEmptyState(emptyElement, message) {
    if (!emptyElement) {
      return;
    }
    emptyElement.textContent = message;
    emptyElement.classList.remove('d-none');
  }

  function hideEmptyState(emptyElement) {
    if (!emptyElement) {
      return;
    }
    emptyElement.classList.add('d-none');
  }

  function renderError(container, message) {
    if (!container) {
      return;
    }
    container.innerHTML = `<div class="customer-error text-danger small">${escapeHtml(message)}</div>`;
  }

  document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('customer-home');
    if (!root) {
      return;
    }

    const urls = {
      trainings: root.dataset.trainingsUrl,
      subscriptions: root.dataset.subscriptionsUrl,
      news: root.dataset.newsUrl,
      groupRatings: root.dataset.groupRatingsUrl,
      teamMembers: root.dataset.teamMembersUrl,
      distances: root.dataset.distancesUrl
    };

    const patterns = {
      groupDetail: root.dataset.groupDetailTemplate || '',
      teamMemberDetail: root.dataset.teamMemberTemplate || ''
    };

    const state = {
      teamMembers: []
    };

    function loadTrainings(url) {
      const list = document.getElementById('trainings-list');
      const counter = document.getElementById('trainings-count');
      const empty = document.getElementById('trainings-empty-state');
      if (!list || !url) {
        return Promise.resolve();
      }

      return fetchJson(url)
        .then((data) => {
          const trainings = data?.trainings || [];
          list.innerHTML = '';
          hideEmptyState(empty);

          if (!trainings.length) {
            showEmptyState(empty, 'Сегодня нет тренировок.');
            if (counter) {
              counter.classList.add('d-none');
            }
            return;
          }

          trainings.forEach((training) => {
            const li = document.createElement('li');
            li.className = 'd-flex align-items-center mb-3 customer-training-item';
            li.innerHTML = `
              <div class="customer-item-icon">
                <i class="bi bi-geo-alt"></i>
              </div>
              <div class="flex-grow-1">
                <div class="customer-item-title">${escapeHtml(training.name)}</div>
                <div class="text-muted small">${escapeHtml(training.group)}</div>
              </div>
              <div class="text-muted small customer-item-time">
                к ${escapeHtml(formatTime(training.start))}
              </div>
            `;
            list.appendChild(li);
          });

          if (counter) {
            counter.textContent = trainings.length;
            counter.classList.remove('d-none');
          }
        })
        .catch((error) => {
          renderError(list, error.message);
        });
    }

    function loadSubscriptions(url) {
      const container = document.getElementById('subscriptions-list');
      const empty = document.getElementById('subscriptions-empty-state');
      if (!container || !url) {
        return Promise.resolve();
      }

      return fetchJson(url)
        .then((data) => {
          const subscriptions = data?.subscriptions || [];
          container.innerHTML = '';
          hideEmptyState(empty);

          if (!subscriptions.length) {
            showEmptyState(empty, 'Нет активных абонементов.');
            return;
          }

          subscriptions.forEach((subscription) => {
            const wrapper = document.createElement('div');
            wrapper.className = 'customer-subscription mb-4';

            const unlimited = Boolean(subscription.unlimited);
            const remained = subscription.remained ?? '—';
            const total = subscription.number_classes ?? '—';
            const percent = Number(subscription.percent_used ?? 0);
            const daysLeft = subscription.days_left;
            const endDate = subscription.end_date ? formatDateTime(subscription.end_date).split(',')[0] : '';

            let daysLeftLabel = '';
            if (!unlimited && typeof daysLeft === 'number') {
              if (daysLeft > 0) {
                daysLeftLabel = `До конца: ${daysLeft} дн.`;
              } else if (daysLeft === 0) {
                daysLeftLabel = 'Последний день абонемента';
              } else {
                daysLeftLabel = 'Абонемент истёк';
              }
            }

            wrapper.innerHTML = `
              <div class="customer-subscription-title">Абонемент #${escapeHtml(subscription.id)}</div>
              <div class="customer-subscription-info">
                ${unlimited ? 'Безлимит' : `${escapeHtml(remained)} / ${escapeHtml(total)}`}
              </div>
              ${
                daysLeftLabel || endDate
                  ? `<div class="customer-subscription-meta text-muted small">
                      ${escapeHtml(daysLeftLabel)}
                      ${endDate ? `<span class="ms-1">до ${escapeHtml(endDate)}</span>` : ''}
                    </div>`
                  : ''
              }
              ${
                unlimited
                  ? ''
                  : `
                    <div class="customer-progress-wrapper">
                      <div class="customer-progress-label text-muted small mb-1">
                        Использовано ${Math.round(percent)}%
                      </div>
                      <div class="progress customer-progress">
                        <div class="progress-bar" role="progressbar" style="width: ${Math.min(Math.max(percent, 0), 100)}%"></div>
                      </div>
                    </div>
                  `
              }
            `;

            container.appendChild(wrapper);
          });
        })
        .catch((error) => {
          renderError(container, error.message);
        });
    }

    function loadNews(url) {
      const list = document.getElementById('news-list');
      const empty = document.getElementById('news-empty-state');
      if (!list || !url) {
        return Promise.resolve();
      }

      return fetchJson(url)
        .then((data) => {
          const news = data?.news || [];
          list.innerHTML = '';
          hideEmptyState(empty);

          if (!news.length) {
            showEmptyState(empty, 'Нет новостей.');
            return;
          }

          news.forEach((item) => {
            const li = document.createElement('li');
            li.className = 'timeline-item customer-news-item';
            li.dataset.title = item.title || '';
            li.dataset.date = formatDateTime(item.created_at);
            li.dataset.image = item.image || '';
            li.dataset.description = item.description || '';
            li.innerHTML = `
              <span class="timeline-marker"></span>
              <div class="text-muted small mb-1">${escapeHtml(formatDateTime(item.created_at))}</div>
              <div class="customer-news-content">
                ${
                  item.image
                    ? `<div class="customer-news-thumb"><img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.title)}"></div>`
                    : '<div class="customer-news-thumb placeholder-thumb"><i class="bi bi-image"></i></div>'
                }
                <div>
                  <div class="customer-news-title">${escapeHtml(item.title)}</div>
                  ${
                    item.description
                      ? `<div class="text-muted small">${escapeHtml(truncateText(item.description, 100))}</div>`
                      : ''
                  }
                </div>
              </div>
            `;
            li.addEventListener('click', () => openNewsModal(li.dataset));
            list.appendChild(li);
          });
        })
        .catch((error) => {
          renderError(list, error.message);
        });
    }

    function openNewsModal(dataset) {
      const modalElement = document.getElementById('newsModal');
      if (!modalElement) {
        return;
      }
      const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
      const title = document.getElementById('newsModalLabel');
      const date = document.getElementById('newsModalDate');
      const text = document.getElementById('newsModalText');
      const imageWrap = document.getElementById('newsModalImageWrap');
      const image = document.getElementById('newsModalImage');

      if (title) {
        title.textContent = dataset.title || '';
      }
      if (date) {
        date.textContent = dataset.date || '';
      }
      if (text) {
        text.textContent = dataset.description || '';
      }
      if (image && imageWrap) {
        if (dataset.image) {
          image.src = dataset.image;
          imageWrap.classList.remove('d-none');
        } else {
          imageWrap.classList.add('d-none');
          image.src = '';
        }
      }

      modal.show();
    }

    function buildDetailUrl(pattern, id) {
      if (!pattern) {
        return '#';
      }
      return pattern.replace(/0\/?$/, `${id}/`);
    }

    function loadGroupRatings(url) {
      const tableBody = document.getElementById('groups-table-body');
      const empty = document.getElementById('groups-empty-state');
      const bestValueEl = document.querySelector('[data-rating-best-group]');
      const bestPlaceEl = document.querySelector('[data-rating-best-group-place]');
      if (!tableBody || !url) {
        return Promise.resolve();
      }

      return fetchJson(url)
        .then((data) => {
          const groups = data?.groups || [];
          const bestGroup = data?.best_group || {};
          tableBody.innerHTML = '';
          hideEmptyState(empty);

          if (bestValueEl) {
            bestValueEl.textContent = bestGroup.avg !== undefined
              ? formatNumber(bestGroup.avg)
              : '—';
          }
          if (bestPlaceEl) {
            if (bestGroup.place && bestGroup.total) {
              bestPlaceEl.textContent = `Место: ${bestGroup.place}/${bestGroup.total}`;
            } else {
              bestPlaceEl.textContent = 'Место: —';
            }
          }

          if (!groups.length) {
            showEmptyState(empty, 'Нет данных по группам.');
            return;
          }

          groups.forEach((group) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td>${escapeHtml(group.name)}</td>
              <td class="text-center">${formatNumber(group.average)}</td>
              <td class="text-center">${group.place ?? '—'}</td>
              <td class="text-center">${group.total ?? '—'}</td>
              <td class="text-center">
                <a class="btn btn-sm btn-outline-primary" href="${escapeHtml(buildDetailUrl(patterns.groupDetail, group.id))}">
                  <i class="bi bi-eye me-1"></i>Детали
                </a>
              </td>
            `;
            tableBody.appendChild(tr);
          });
        })
        .catch((error) => {
          renderError(tableBody, error.message);
        });
    }

    function renderTeamMembers(members, container) {
      if (!container) {
        return;
      }

      if (!members.length) {
        container.innerHTML = '<div class="customer-empty-state text-center py-5">Нет данных об участниках команды.</div>';
        return;
      }

      const row = document.createElement('div');
      row.className = 'row g-3';

      members.forEach((member) => {
        const card = document.createElement('div');
        card.className = 'col-12 col-md-6 col-lg-4';
        card.innerHTML = `
          <div class="card h-100 border-0 shadow-sm customer-team-card">
            <div class="card-body">
              <div class="d-flex align-items-center mb-3">
                <div class="customer-team-avatar me-3">
                  ${
                    member.photo
                      ? `<img src="${escapeHtml(member.photo)}" alt="${escapeHtml(member.full_name)}">`
                      : '<div class="customer-team-avatar-placeholder"><i class="bi bi-person-fill"></i></div>'
                  }
                  <span class="badge rounded-pill customer-team-place">${member.place}</span>
                </div>
                <div class="flex-grow-1">
                  <div class="customer-team-name">
                    <a href="${escapeHtml(buildDetailUrl(patterns.teamMemberDetail, member.id))}" class="stretched-link text-decoration-none">
                      ${escapeHtml(member.full_name)}
                    </a>
                  </div>
                  <div class="text-muted small">
                    Рейтинг: <span class="fw-semibold">${formatNumber(member.avg_score)}</span>
                  </div>
                  ${
                    member.sport_category
                      ? `<div class="customer-team-category badge">${escapeHtml(member.sport_category)}</div>`
                      : ''
                  }
                </div>
              </div>
              ${
                member.achievements && member.achievements.length
                  ? `
                    <div class="mb-3">
                      <div class="small text-muted mb-1">Достижения</div>
                      <div class="customer-tags">
                        ${member.achievements.map((ach) => `<span class="badge bg-light text-dark border">${escapeHtml(ach.name)}</span>`).join('')}
                      </div>
                    </div>
                  `
                  : ''
              }
              ${
                member.competition_results && member.competition_results.length
                  ? `
                    <div>
                      <div class="small text-muted mb-1">Последние соревнования</div>
                      <ul class="list-unstyled mb-0 customer-competitions">
                        ${member.competition_results
                          .map((result) => `
                            <li class="d-flex justify-content-between small">
                              <span>${escapeHtml(result.name)}</span>
                              <span class="text-muted">${escapeHtml(formatDateTime(result.date))}</span>
                            </li>
                          `)
                          .join('')}
                      </ul>
                    </div>
                  `
                  : ''
              }
            </div>
          </div>
        `;
        row.appendChild(card);
      });

      container.innerHTML = '';
      container.appendChild(row);
    }

    function loadTeamMembers(url) {
      const container = document.getElementById('team-members-container');
      const teamValueEl = document.querySelector('[data-rating-team]');
      const teamPlaceEl = document.querySelector('[data-rating-team-place]');
      if (!container || !url) {
        return Promise.resolve();
      }

      return fetchJson(url)
        .then((data) => {
          state.teamMembers = data?.members || [];
          renderTeamMembers(state.teamMembers, container);

          if (teamValueEl) {
            teamValueEl.textContent = formatNumber(data?.team_avg);
          }
          if (teamPlaceEl) {
            if (data?.team_place && data?.team_total) {
              teamPlaceEl.textContent = `Место: ${data.team_place}/${data.team_total}`;
            } else {
              teamPlaceEl.textContent = 'Место: —';
            }
          }
        })
        .catch((error) => {
          renderError(container, error.message);
        });
    }

    function renderDistanceChart(containerId, value, defaultGoal, unitLabel) {
      const container = document.getElementById(containerId);
      if (!container) {
        return;
      }
      const numericValue = Number(value) || 0;
      const goal = Math.max(defaultGoal, numericValue || 0);
      const percent = goal ? Math.min(100, Math.round((numericValue / goal) * 100)) : 0;
      container.innerHTML = `
        <div class="distance-progress" role="img" aria-label="Выполнено ${percent}%">
          <div class="distance-progress-fill" style="width: ${percent}%;"></div>
        </div>
        <div class="distance-progress-caption text-muted">
          Цель ${goal.toFixed(0)} ${unitLabel} • ${percent}%
        </div>
      `;
    }

    function loadDistances(url) {
      const week = document.getElementById('distance-week');
      const year = document.getElementById('distance-year');
      if (!url) {
        return Promise.resolve();
      }

      return fetchJson(url)
        .then((data) => {
          const weekValue = data?.week;
          const yearValue = data?.year;
          if (week) {
            week.textContent = formatNumber(weekValue);
          }
          if (year) {
            year.textContent = formatNumber(yearValue);
          }
          renderDistanceChart('distance-week-chart', weekValue, 20, 'км');
          renderDistanceChart('distance-year-chart', yearValue, 800, 'км');
        })
        .catch((error) => {
          if (week) {
            week.textContent = '—';
          }
          if (year) {
            year.textContent = '—';
          }
          renderDistanceChart('distance-week-chart', 0, 20, 'км');
          renderDistanceChart('distance-year-chart', 0, 800, 'км');
          console.error(error);
        });
    }

    const loaders = [
      urls.trainings && loadTrainings(urls.trainings),
      urls.subscriptions && loadSubscriptions(urls.subscriptions),
      urls.news && loadNews(urls.news),
      urls.groupRatings && loadGroupRatings(urls.groupRatings),
      urls.teamMembers && loadTeamMembers(urls.teamMembers),
      urls.distances && loadDistances(urls.distances)
    ].filter(Boolean);

    Promise.allSettled(loaders).catch((error) => {
      console.error('Ошибка при загрузке данных клиентского кабинета:', error);
    });
  });
})();

