(function () {
  'use strict';

  function getGradeWord(count) {
    if (window.AttendanceModule && typeof window.AttendanceModule.getGradeWord === 'function') {
      return window.AttendanceModule.getGradeWord(count);
    }

    if (count === 0) return 'оценок';
    if (count === 1) return 'оценка';
    if (count >= 2 && count <= 4) return 'оценки';
    return 'оценок';
  }

  function toggleCard(customerId) {
    const cardBody = document.getElementById(`card-body-${customerId}`);
    const expandIndicator = document.getElementById(`expand-${customerId}`);

    if (!cardBody) {
      return;
    }

    cardBody.classList.toggle('expanded');
    if (expandIndicator) {
      expandIndicator.classList.toggle('expanded');
    }

    if (cardBody.classList.contains('expanded')) {
      updateGradesCount(customerId, cardBody);
    }
  }

  function updateGradesCount(customerId, container) {
    const gradesCount = document.getElementById(`grades-count-${customerId}`);
    if (!container) {
      container = document.getElementById(`card-body-${customerId}`);
    }
    if (!gradesCount || !container) {
      return;
    }

    const gradePills = container.querySelectorAll('.grade-pill');
    let gradeCount = 0;
    let absentCount = 0;

    gradePills.forEach((pill) => {
      const text = pill.textContent.trim();
      if (['2', '3', '4', '5', '10'].includes(text)) {
        gradeCount += 1;
      }
      if (text === 'Н') {
        absentCount += 1;
      }
    });

    gradesCount.textContent = `${gradeCount} ${getGradeWord(gradeCount)} · не был: ${absentCount}`;
  }

  function initialiseCards() {
    const cards = document.querySelectorAll('.mobile-card');

    cards.forEach((card, index) => {
      const customerId = card.dataset.customerId;
      const cardBody = card.querySelector('.mobile-card-body');

      if (!customerId || !cardBody) {
        return;
      }

      updateGradesCount(customerId, cardBody);

      if (index === 0) {
        cardBody.classList.add('expanded');
        const expandIndicator = document.getElementById(`expand-${customerId}`);
        if (expandIndicator) {
          expandIndicator.classList.add('expanded');
        }
      }
    });

    document.querySelectorAll('.mobile-card-header a').forEach((link) => {
      link.addEventListener('click', function (e) {
        e.stopPropagation();
      });
    });

    document.querySelectorAll('.mobile-card-body .btn').forEach((button) => {
      button.addEventListener('click', function (e) {
        e.stopPropagation();
      });
    });
  }

  document.addEventListener('DOMContentLoaded', initialiseCards);

  window.MobileAttendance = {
    toggleCard,
    updateGradesCount,
  };

  document.addEventListener('click', function (event) {
    const toggle = event.target.closest('.mobile-card-header');
    if (toggle && toggle.parentElement?.dataset.customerId) {
      toggleCard(toggle.parentElement.dataset.customerId);
    }
  });

  // Обратная совместимость со старыми шаблонами
  window.toggleCard = toggleCard;
})();
