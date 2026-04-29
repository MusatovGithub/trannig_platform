// Исправляем прокрутку модальных окон программы на мобильных устройствах
document.addEventListener('DOMContentLoaded', function() {
  const programModals = document.querySelectorAll('.program-modal');
  
  programModals.forEach(function(modal) {
    const modalDialog = modal.querySelector('.modal-dialog');
    
    if (!modalDialog) {
      return; // Пропускаем если нет modal-dialog
    }
    
    // Функция для управления классом прокрутки
    function updateScrollClass() {
      if (window.innerWidth <= 767) {
        // На мобильных устройствах убираем modal-dialog-scrollable и modal-dialog-centered
        modalDialog.classList.remove('modal-dialog-scrollable', 'modal-dialog-centered');
      } else {
        // На десктопе возвращаем их
        if (!modalDialog.classList.contains('modal-dialog-scrollable')) {
          modalDialog.classList.add('modal-dialog-scrollable');
        }
        if (!modalDialog.classList.contains('modal-dialog-centered')) {
          modalDialog.classList.add('modal-dialog-centered');
        }
      }
    }
    
    // Применяем при загрузке
    updateScrollClass();
    
    // Применяем при изменении размера окна
    window.addEventListener('resize', updateScrollClass);
    
    // Применяем при открытии модального окна
    modal.addEventListener('show.bs.modal', function() {
      updateScrollClass();
      // Небольшая задержка для применения стилей
      setTimeout(() => {
        if (window.innerWidth <= 767) {
          const modalBody = modal.querySelector('.modal-body');
          if (modalBody) {
            modalBody.style.overflowY = 'auto';
          }
        }
      }, 100);
    });
  });
});

