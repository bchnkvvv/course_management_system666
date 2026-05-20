// Глобальные переменные
let currentDataSource = 'orm';
const API_BASE = 'http://localhost:8000/api/v1';

// Установка источника данных
function setDataSource(source) {
    currentDataSource = source;
    document.getElementById('useOrmBtn').classList.toggle('active', source === 'orm');
    document.getElementById('useNativeBtn').classList.toggle('active', source === 'native');
    
    // Перезагружаем данные
    loadAllData();
}

// API запрос с выбором источника данных
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
        'Content-Type': 'application/json',
        'X-Data-Source': currentDataSource,
        ...options.headers
    };
    
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'API Error');
    }
    return response.json();
}

// Загрузка всех данных
async function loadAllData() {
    await loadDepartmentTree();
    await loadCourses();
    await loadStudentsAndTeachers();
    showDataSourceStatus();
}

// 1. Иерархия департаментов
async function loadDepartmentTree() {
    try {
        const tree = await apiRequest('/hierarchy/departments/tree');
        renderDepartmentTree(tree);
    } catch (error) {
        console.error('Error loading departments:', error);
        document.getElementById('departmentTree').innerHTML = 
            '<div class="alert alert-danger">Ошибка загрузки</div>';
    }
}

function renderDepartmentTree(departments, level = 0) {
    if (!departments || departments.length === 0) {
        document.getElementById('departmentTree').innerHTML = 
            '<div class="text-muted">Нет департаментов</div>';
        return;
    }
    
    let html = '<ul class="tree">';
    departments.forEach(dept => {
        const paddingLeft = level * 20;
        html += `
            <li style="padding-left: ${paddingLeft}px;">
                <i class="fas fa-folder-open text-warning"></i>
                <strong>${dept.name}</strong> (${dept.code})
                <span class="badge bg-secondary">ур. ${dept.level}</span>
                ${dept.children && dept.children.length > 0 ? 
                    `<span class="badge bg-info">${dept.children.length} подразделов</span>` : ''}
                ${dept.children ? renderDepartmentTree(dept.children, level + 1) : ''}
            </li>
        `;
    });
    html += '</ul>';
    document.getElementById('departmentTree').innerHTML = html;
}

// 2. Курсы
async function loadCourses() {
    try {
        // Получаем список курсов через специальный эндпоинт
        const response = await fetch(`${API_BASE}/courses/list?limit=20`, {
            headers: { 'X-Data-Source': currentDataSource }
        });
        const courses = await response.json();
        renderCourses(courses);
    } catch (error) {
        console.error('Error loading courses:', error);
        renderCourses([]);
    }
}

function renderCourses(courses) {
    if (!courses || courses.length === 0) {
        document.getElementById('coursesList').innerHTML = 
            '<div class="alert alert-info">Нет курсов. Создайте первый курс!</div>';
        return;
    }
    
    let html = '<div class="list-group">';
    courses.forEach(course => {
        const currentVer = course.current_version;
        html += `
            <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">
                            <strong>${course.code}</strong> - ${currentVer?.title || 'Нет версии'}
                        </h6>
                        <small class="text-muted">
                            Версия ${currentVer?.version_number || 0} | 
                            Кредиты: ${currentVer?.credits || 0} | 
                            Часов: ${currentVer?.hours_total || 0}
                        </small>
                        <div class="mt-1">
                            <button class="btn btn-sm btn-outline-info" onclick="showVersions(${course.id})">
                                <i class="fas fa-history"></i> Версии (${course.all_versions?.length || 0})
                            </button>
                            <button class="btn btn-sm btn-outline-warning" onclick="openUpdateModal(${course.id}, '${currentVer?.title || ''}', '${currentVer?.description || ''}', ${currentVer?.credits || 0}, ${currentVer?.hours_total || 0})">
                                <i class="fas fa-edit"></i> Обновить
                            </button>
                        </div>
                    </div>
                    <span class="badge ${currentVer?.status === 'published' ? 'bg-success' : 'bg-secondary'}">
                        ${currentVer?.status || 'draft'}
                    </span>
                </div>
            </div>
        `;
    });
    html += '</div>';
    document.getElementById('coursesList').innerHTML = html;
}

async function showVersions(courseId) {
    try {
        const versions = await apiRequest(`/courses/${courseId}/versions`);
        let html = '<div class="timeline">';
        
        versions.forEach((ver, index) => {
            html += `
                <div class="timeline-item ${ver.is_current ? 'current' : ''}">
                    <div class="timeline-badge ${ver.is_current ? 'bg-success' : 'bg-secondary'}">
                        v${ver.version_number}
                    </div>
                    <div class="timeline-content">
                        <h6>${ver.title}</h6>
                        <p>${ver.description || 'Нет описания'}</p>
                        <small>
                            Кредиты: ${ver.credits} | Часов: ${ver.hours_total}<br>
                            Создана: ${new Date(ver.created_at).toLocaleString()}
                            ${ver.is_current ? '<span class="badge bg-success ms-2">Актуальная</span>' : ''}
                        </small>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        document.getElementById('versionHistoryContent').innerHTML = html;
        new bootstrap.Modal(document.getElementById('versionHistoryModal')).show();
    } catch (error) {
        alert('Ошибка загрузки версий: ' + error.message);
    }
}

// 3. Расписание
async function loadSchedule() {
    const group = document.getElementById('groupSelect').value;
    try {
        const schedule = await apiRequest(`/schedule/group/${group}`);
        renderSchedule(schedule);
    } catch (error) {
        console.error('Error loading schedule:', error);
    }
}

function renderSchedule(schedule) {
    if (!schedule || schedule.length === 0) {
        document.getElementById('scheduleTable').innerHTML = 
            '<div class="alert alert-info">Нет занятий для этой группы</div>';
        return;
    }
    
    const days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
    let html = '<table class="table table-bordered">';
    html += '<thead><tr><th>Время</th><th>ПН</th><th>ВТ</th><th>СР</th><th>ЧТ</th><th>ПТ</th><th>СБ</th></tr></thead><tbody>';
    
    // Группировка по времени
    const times = [...new Set(schedule.map(s => s.start_time))].sort();
    
    times.forEach(time => {
        html += `<tr><td class="time-col">${time}</td>`;
        for (let day = 1; day <= 6; day++) {
            const entry = schedule.find(s => s.day_of_week === day && s.start_time === time);
            if (entry) {
                html += `
                    <td class="schedule-cell">
                        <strong>${entry.course_title}</strong><br>
                        <small>${entry.room} | ${entry.teacher_name || '?'}</small><br>
                        <span class="badge bg-secondary">${entry.lesson_type}</span>
                    </td>
                `;
            } else {
                html += '<td class="text-muted">-</td>';
            }
        }
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    document.getElementById('scheduleTable').innerHTML = html;
}

// 4. Студенты и преподаватели
async function loadStudentsAndTeachers() {
    try {
        const students = await apiRequest('/users/students');
        const teachers = await apiRequest('/users/teachers');
        
        renderStudents(students);
        renderTeachers(teachers);
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

function renderStudents(students) {
    if (!students || students.length === 0) {
        document.getElementById('studentsList').innerHTML = '<div class="text-muted">Нет студентов</div>';
        return;
    }
    
    let html = '<div class="list-group">';
    students.forEach(student => {
        html += `
            <div class="list-group-item">
                <strong>${student.full_name}</strong><br>
                <small>
                    Группа: ${student.group_name} | 
                    Карта: ${student.student_card_number} |
                    Ср. балл: ${student.average_grade || '—'}
                </small>
            </div>
        `;
    });
    html += '</div>';
    document.getElementById('studentsList').innerHTML = html;
}

function renderTeachers(teachers) {
    if (!teachers || teachers.length === 0) {
        document.getElementById('teachersList').innerHTML = '<div class="text-muted">Нет преподавателей</div>';
        return;
    }
    
    let html = '<div class="list-group">';
    teachers.forEach(teacher => {
        html += `
            <div class="list-group-item">
                <strong>${teacher.full_name}</strong><br>
                <small>
                    ${teacher.position || 'Должность не указана'} | 
                    ${teacher.academic_degree || ''}
                </small>
            </div>
        `;
    });
    html += '</div>';
    document.getElementById('teachersList').innerHTML = html;
}

// CRUD операции
async function createCourse() {
    const form = document.getElementById('createCourseForm');
    const formData = new FormData(form);
    
    const courseData = {
        title: formData.get('title'),
        description: formData.get('description'),
        credits: parseInt(formData.get('credits')),
        hours_total: parseInt(formData.get('hours_total')),
        hours_lecture: 0,
        hours_practice: 0,
        hours_lab: 0,
        status: 'draft'
    };
    
    try {
        const result = await apiRequest(`/courses/?code=${formData.get('code')}&created_by=1`, {
            method: 'POST',
            body: JSON.stringify(courseData)
        });
        
        alert('Курс успешно создан!');
        bootstrap.Modal.getInstance(document.getElementById('createCourseModal')).hide();
        form.reset();
        await loadCourses();
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

function openUpdateModal(courseId, title, description, credits, hoursTotal) {
    document.getElementById('updateCourseId').value = courseId;
    document.getElementById('updateTitle').value = title;
    document.getElementById('updateDescription').value = description || '';
    document.getElementById('updateCredits').value = credits;
    document.getElementById('updateHoursTotal').value = hoursTotal;
    document.getElementById('changeReason').value = '';
    
    new bootstrap.Modal(document.getElementById('updateCourseModal')).show();
}

async function updateCourse() {
    const courseId = document.getElementById('updateCourseId').value;
    const updateData = {
        title: document.getElementById('updateTitle').value,
        description: document.getElementById('updateDescription').value,
        credits: parseInt(document.getElementById('updateCredits').value),
        hours_total: parseInt(document.getElementById('updateHoursTotal').value),
        change_reason: document.getElementById('changeReason').value
    };
    
    try {
        const result = await apiRequest(`/courses/${courseId}?changed_by=1`, {
            method: 'PUT',
            body: JSON.stringify(updateData)
        });
        
        alert(`Создана новая версия ${result.version_number}!`);
        bootstrap.Modal.getInstance(document.getElementById('updateCourseModal')).hide();
        await loadCourses();
        
        // Показываем уведомление о версионировании
        document.getElementById('versionInfo').innerHTML = `
            <div class="alert alert-success alert-dismissible fade show" role="alert">
                <i class="fas fa-code-branch"></i> Создана версия ${result.version_number}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
    } catch (error) {
        alert('Ошибка: ' + error.message);
    }
}

function showDataSourceStatus() {
    const statusHtml = `
        <div class="alert alert-${currentDataSource === 'orm' ? 'primary' : 'info'}">
            <i class="fas ${currentDataSource === 'orm' ? 'fa-database' : 'fa-code'}"></i>
            Текущий источник данных: <strong>${currentDataSource.toUpperCase()}</strong>
            ${currentDataSource === 'orm' ? '(SQLAlchemy ORM)' : '(Native SQL Queries)'}
        </div>
    `;
    // Можно добавить отображение статуса где-нибудь
}

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    loadAllData();
    
    // Периодическое обновление расписания при смене группы
    document.getElementById('groupSelect').addEventListener('change', loadSchedule);
});

// CSS стили для дерева и таймлайна
const style = document.createElement('style');
style.textContent = `
    .tree {
        list-style: none;
        padding-left: 0;
    }
    .tree li {
        margin: 8px 0;
        cursor: pointer;
    }
    .timeline {
        position: relative;
        padding: 20px 0;
    }
    .timeline-item {
        position: relative;
        margin-bottom: 30px;
        display: flex;
        align-items: flex-start;
    }
    .timeline-badge {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: bold;
        margin-right: 20px;
        flex-shrink: 0;
    }
    .timeline-content {
        flex: 1;
        background: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
    }
    .timeline-item.current .timeline-badge {
        background-color: #28a745;
        box-shadow: 0 0 0 3px rgba(40, 167, 69, 0.3);
    }
    .schedule-cell {
        font-size: 0.85rem;
    }
    .time-col {
        font-weight: bold;
        background-color: #f8f9fa;
    }
`;
document.head.appendChild(style);