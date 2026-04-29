/**
 * Модуль для работы с выставлением оценок через AJAX
 */

(function() {
    'use strict';

    /**
     * Получение CSRF токена из cookie
     */
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const csrftoken = getCookie('csrftoken');
    const modalCache = new Map();
    const customerSummaryLoaded = new Set();

    /**
     * Показать уведомление об успехе
     */
    function showSuccessMessage(message) {
        // Проверяем наличие библиотеки SweetAlert2
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                icon: 'success',
                title: 'Успешно',
                text: message,
                timer: 2000,
                showConfirmButton: false
            });
        } else {
            // Fallback на простое alert
            alert(message);
        }
    }

    /**
     * Показать уведомление об ошибке
     */
    function showErrorMessage(message) {
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                icon: 'error',
                title: 'Ошибка',
                text: message,
                confirmButtonText: 'OK'
            });
        } else {
            alert('Ошибка: ' + message);
        }
    }

    function replaceCustomerBlock(elementId, htmlString, fallbackParent) {
        if (!htmlString) {
            return;
        }
        const wrapper = document.createElement('div');
        wrapper.innerHTML = htmlString.trim();
        const newElement = wrapper.firstElementChild;
        if (!newElement) {
            return;
        }
        const existing = document.getElementById(elementId);
        if (existing) {
            existing.replaceWith(newElement);
        } else if (fallbackParent) {
            fallbackParent.appendChild(newElement);
        }
    }

    function refreshCustomerSummary(customerId, options = {}) {
        if (!customerId) {
            return;
        }

        const { force = false } = options;
        if (!force && customerSummaryLoaded.has(customerId)) {
            return;
        }

        const contextElement = document.getElementById('attendance-page-context');
        if (!contextElement) {
            return;
        }

        const groupId = contextElement.dataset.groupId;
        if (!groupId) {
            return;
        }

        const params = new URLSearchParams();
        const mode = contextElement.dataset.view || 'month';
        params.append('mode', mode);

        if (mode === 'month') {
            if (contextElement.dataset.year) {
                params.append('year', contextElement.dataset.year);
            }
            if (contextElement.dataset.month) {
                params.append('month', contextElement.dataset.month);
            }
        } else if (mode === 'date') {
            if (contextElement.dataset.selectedDate) {
                params.append('selected_date', contextElement.dataset.selectedDate);
            }
        }

        fetch(`/group/${groupId}/customer/${customerId}/summary/?${params.toString()}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.json()
                    .catch(() => ({}))
                    .then(data => {
                        throw new Error(data.error || 'Не удалось обновить данные клиента');
                    });
            }
            return response.json();
        })
        .then(data => {
            if (!data || !data.success) {
                throw new Error(data && data.error ? data.error : 'Не удалось обновить данные клиента');
            }

            replaceCustomerBlock(`customer-subscriptions-desktop-${customerId}`, data.desktop_html);
            replaceCustomerBlock(`customer-subscriptions-mobile-${customerId}`, data.mobile_html);
            replaceCustomerBlock(
                `customer-subscription-modals-${customerId}`,
                data.modals_html,
                document.body
            );
            customerSummaryLoaded.add(customerId);
        })
        .catch(error => {
            console.error('Ошибка обновления данных клиента:', error);
        });
    }

    function initCustomerSummaryObserver() {
        const containers = document.querySelectorAll('.customer-summary-container');
        if (!containers.length) {
            return;
        }

        const seen = new Set();

        if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (!entry.isIntersecting) {
                        return;
                    }
                    const target = entry.target;
                    const customerId = target.dataset.customerId;
                    if (!customerId || seen.has(customerId)) {
                        return;
                    }
                    seen.add(customerId);
                    refreshCustomerSummary(customerId);
                    observer.unobserve(target);
                });
            }, {
                rootMargin: '0px 0px 150px 0px'
            });

            containers.forEach(container => {
                const customerId = container.dataset.customerId;
                if (!customerId || seen.has(customerId)) {
                    return;
                }
                observer.observe(container);
            });

            setTimeout(() => {
                containers.forEach(container => {
                    const customerId = container.dataset.customerId;
                    if (!customerId || seen.has(customerId) || customerSummaryLoaded.has(customerId)) {
                        return;
                    }
                    seen.add(customerId);
                    refreshCustomerSummary(customerId);
                });
            }, 2000);
        } else {
            const uniqueIds = new Set();
            containers.forEach(container => {
                const customerId = container.dataset.customerId;
                if (!customerId || uniqueIds.has(customerId)) {
                    return;
                }
                uniqueIds.add(customerId);
                refreshCustomerSummary(customerId);
            });
        }
    }

    /**
     * Обновить отображение оценки на странице
     */
    function updateGradeDisplay(attendanceId, displayText, cssClass) {
        // Находим все кнопки с этим attendance ID (новый селектор)
        const buttons = document.querySelectorAll(`button[data-attendance-id="${attendanceId}"]`);
        
        buttons.forEach(button => {
            // Обновляем текст и классы
            button.textContent = displayText;
            
            // Удаляем все старые классы оценок
            button.classList.remove('grade-2', 'grade-3', 'grade-4', 'grade-5', 
                                    'grade-10', 'status-absent', 'status-empty');
            
            // Добавляем новый класс
            button.classList.add(cssClass);
        });
    }

    /**
     * Обновить счетчик оценок в мобильной версии
     */
    function updateGradesCount(customerId) {
        if (window.MobileAttendance && typeof window.MobileAttendance.updateGradesCount === 'function') {
            window.MobileAttendance.updateGradesCount(customerId);
            return;
        }

        const gradesCount = document.getElementById(`grades-count-${customerId}`);
        const cardBody = document.getElementById(`card-body-${customerId}`);
        if (!gradesCount || !cardBody) return;

        const gradePills = cardBody.querySelectorAll('.grade-pill');
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

    /**
     * Склонение слова "оценка"
     */
    function getGradeWord(count) {
        if (count === 0) return 'оценок';
        if (count === 1) return 'оценка';
        if (count >= 2 && count <= 4) return 'оценки';
        return 'оценок';
    }

    /**
     * Отправка AJAX запроса для выставления оценки
     */
    function submitAttendanceAjax(form, attendanceId, customerId, buttonValue) {
        const comment = form.querySelector('textarea[name="comment"]').value;

        console.log('Отправка AJAX запроса:', {
            attendanceId: attendanceId,
            status: buttonValue,
            comment: comment
        });

        // Создаем данные для отправки
        const data = new FormData();
        data.append('status', buttonValue);
        data.append('comment', comment || '');

        // Отправляем AJAX запрос
        fetch(`/group/attendance/${attendanceId}/ajax/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken,
            },
            body: data
        })
        .then(response => {
            console.log('Получен ответ:', response.status);
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || 'Ошибка сервера');
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Данные ответа:', data);
            if (data.success) {
                // Обновляем отображение оценки
                updateGradeDisplay(attendanceId, data.display_text, data.css_class);
                
                // Обновляем счетчик в мобильной версии
                if (customerId) {
                    updateGradesCount(customerId);
                }
                
                // Закрываем универсальное модальное окно
                const modalElement = document.getElementById('attendance-modal');
                if (modalElement) {
                    const modal = bootstrap.Modal.getInstance(modalElement);
                    if (modal) {
                        modal.hide();
                    }
                }

                // Очищаем кэш, чтобы при следующем открытии получить актуальные данные
                clearModalCache(attendanceId);
 
                // Показываем уведомление
                showSuccessMessage(data.message || 'Изменения успешно сохранены');

                if (customerId) {
                    refreshCustomerSummary(customerId, { force: true });
                }
            } else {
                showErrorMessage(data.error || 'Неизвестная ошибка');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showErrorMessage(error.message || 'Ошибка при отправке данных');
        });
    }

// Флаг для предотвращения множественной инициализации
let isInitialized = false;

/**
 * Обработчик клика по кнопкам оценок
 */
function handleButtonClick(e) {
    const button = e.target;
    
    // Проверяем, что это кнопка с именем "status" внутри формы оценок
    if (button.matches('.attendance-form button[name="status"]')) {
        e.preventDefault();
        e.stopPropagation();
        
        const form = button.closest('form.attendance-form');
        if (!form) {
            console.error('Не найдена родительская форма');
            return;
        }
        
        // Получаем ID из data-атрибутов формы
        const attendanceId = form.dataset.attendanceId;
        const customerId = form.dataset.customerId;
        const buttonValue = button.value;
        
        if (!attendanceId) {
            console.error('Не найден attendance_id в форме');
            return;
        }
        
        if (!buttonValue) {
            console.error('Не найдено значение у кнопки');
            return;
        }
        
        console.log('Кнопка оценки нажата:', {
            attendanceId: attendanceId,
            customerId: customerId,
            status: buttonValue
        });
        
        submitAttendanceAjax(form, attendanceId, customerId, buttonValue);
    }
}

/**
 * Динамическая загрузка модального окна для выставления оценки
 */
function initDynamicModalLoading() {
    const modal = document.getElementById('attendance-modal');
    if (!modal) {
        console.warn('Модальное окно attendance-modal не найдено');
        return;
    }

    const modalBody = document.getElementById('attendance-modal-body');
    const modalTitle = document.getElementById('attendance-modal-label');
    const bootstrapModal = new bootstrap.Modal(modal);
    
    // Обработчик для всех кнопок открытия модального окна
    document.addEventListener('click', function(e) {
        const button = e.target.closest('.open-attendance-modal');
        if (!button) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        const attendanceId = button.dataset.attendanceId;
        const grClassId = button.dataset.grClassId;
        const custumerId = button.dataset.custumerId;
        const date = button.dataset.date;
        const customerName = button.dataset.customerName;
        const triggerButton = button;
        
        // Показываем модальное окно с загрузкой
        modalTitle.textContent = customerName || 'Загрузка...';
        
        // Если есть attendance_id - используем его (существующая запись)
        if (attendanceId) {
            // Проверяем кэш
            if (modalCache.has(attendanceId)) {
                modalBody.innerHTML = modalCache.get(attendanceId);
                bootstrapModal.show();
                return;
            }
            
            // Показываем спиннер загрузки
            modalBody.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Загрузка...</span></div></div>';
            bootstrapModal.show();
            
            // Загружаем содержимое через AJAX
            fetch(`/group/attendance/${attendanceId}/modal/`, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrftoken
                },
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.html) {
                    modalBody.innerHTML = data.html;
                    modalTitle.textContent = data.customer_name || customerName;
                    
                    // Сохраняем в кэш
                    modalCache.set(attendanceId, data.html);
                    
                    console.log('Модальное окно загружено для attendance:', attendanceId);
                } else {
                    throw new Error('Нет данных в ответе');
                }
            })
            .catch(error => {
                console.error('Ошибка загрузки модального окна:', error);
                modalBody.innerHTML = `<div class="alert alert-danger">Ошибка загрузки данных: ${error.message}</div>`;
            });
        } 
        // Если нет attendance_id, но есть gr_class_id и custumer_id - создаем/получаем attendance
        else if (grClassId && custumerId) {
            // Показываем спиннер загрузки
            modalBody.innerHTML = '<div class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Загрузка...</span></div></div>';
            bootstrapModal.show();
            
            // Получаем или создаем attendance через AJAX
            const url = `/group/attendance/get-or-create/?gr_class_id=${grClassId}&custumer_id=${custumerId}${date ? '&date=' + date : ''}`;
            fetch(url, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrftoken
                },
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.attendance_id) {
                    const newAttendanceId = data.attendance_id;
                    // Теперь загружаем модальное окно с полученным attendance_id
                    return fetch(`/group/attendance/${newAttendanceId}/modal/`, {
                        method: 'GET',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': csrftoken
                        },
                    })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP ${response.status}`);
                        }
                        return response.json().then(modalData => ({
                            ...modalData,
                            attendance_id: newAttendanceId
                        }));
                    });
                } else {
                    throw new Error('Не удалось получить attendance_id');
                }
            })
            .then(data => {
                if (data.html) {
                    modalBody.innerHTML = data.html;
                    modalTitle.textContent = data.customer_name || customerName;
                    
                    // Сохраняем в кэш с правильным attendance_id
                    if (data.attendance_id) {
                        modalCache.set(data.attendance_id, data.html);
                        triggerButton.dataset.attendanceId = data.attendance_id;
                        triggerButton.removeAttribute('data-gr-class-id');
                        triggerButton.removeAttribute('data-custumer-id');
                        triggerButton.removeAttribute('data-date');
                    }
                    
                    console.log('Модальное окно загружено для нового attendance:', data.attendance_id);
                } else {
                    throw new Error('Нет данных в ответе');
                }
            })
            .catch(error => {
                console.error('Ошибка загрузки модального окна:', error);
                modalBody.innerHTML = `<div class="alert alert-danger">Ошибка загрузки данных: ${error.message}</div>`;
            });
        } else {
            console.error('Не найдены необходимые данные для открытия модального окна');
            modalBody.innerHTML = '<div class="alert alert-danger">Ошибка: не найдены данные для открытия модального окна</div>';
        }
    });
    
    console.log('Динамическая загрузка модальных окон инициализирована');
}

/**
 * Инициализация обработчиков форм оценок через делегирование
 */
function initAttendanceForms() {
    // Предотвращаем множественную установку обработчика
    if (isInitialized) {
        console.log('Обработчики уже установлены, пропускаем');
        return;
    }
    
    // Используем делегирование событий на document для кликов по кнопкам
    document.addEventListener('click', handleButtonClick, true); // Capturing phase
    
    isInitialized = true;
    console.log('AJAX обработчик кнопок оценок установлен и готов');
}

/**
 * Инициализация при загрузке страницы
 */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        console.log('DOM загружен, устанавливаем обработчики оценок');
        initDynamicModalLoading();
        initAttendanceForms();
        initCustomerSummaryObserver();
    });
} else {
    console.log('DOM уже загружен, устанавливаем обработчики оценок');
    initDynamicModalLoading();
    initAttendanceForms();
    initCustomerSummaryObserver();
}

function clearModalCache(attendanceId) {
	if (attendanceId) {
		modalCache.delete(String(attendanceId));
	} else {
		modalCache.clear();
	}
}

// Экспорт функций для использования извне (если нужно)
window.AttendanceModule = {
    updateGradeDisplay: updateGradeDisplay,
    updateGradesCount: updateGradesCount,
    showSuccessMessage: showSuccessMessage,
    showErrorMessage: showErrorMessage,
    initAttendanceForms: initAttendanceForms,
    getGradeWord: getGradeWord,
    clearModalCache: clearModalCache,
    refreshCustomerSummary: refreshCustomerSummary
};

console.log('Модуль attendance.js загружен и готов к работе');

})();
