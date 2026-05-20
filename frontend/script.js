// Глобальные переменные
let currentDataSource = 'orm';
const API_BASE = 'http://localhost:8000/api/v1';

// Установка источника данных
function setDataSource(source) {
    currentDataSource = source;
    
    // Обновляем активную кнопку
    document.getElementById('useOrmBtn').classList.toggle('active', source === 'orm');
    document.getElementById('useNativeBtn').classList.toggle('active', source === 'native');
    
    // Показываем уведомление
    showNotification(`Data source switched to: ${source.toUpperCase()}`, 'info');
    
    // Перезагружаем данные
    loadAllData();
}

// Показать уведомление
function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
    notification.style.zIndex = '9999';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(notification);
    setTimeout(() => notification.remove(), 3000);
}

// API запрос с выбором источника данных
async function apiRequest(endpoint, options = {}) {
    let url = endpoint;
    if (!url.startsWith('http')) {
        url = `${API_BASE}${endpoint}`;
    }
    
    const headers = {
        'Content-Type': 'application/json',
        'X-Data-Source': currentDataSource,
        ...options.headers
    };
    
    const response = await fetch(url, { ...options, headers });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || 'API Error');
    }
    
    return response.json();
}

// Загрузка всех данных
async function loadAllData() {
    await loadDepartmentTree();
    await loadCourses();
    await loadStudentsAndTeachers();
}

// 1. Иерархия департаментов
async function loadDepartmentTree() {
    try {
        const tree = await apiRequest('/hierarchy/departments/tree');
        renderDepartmentTree(tree);
    } catch (error) {
        console.error('Error loading departments:', error);
        document.getElementById('departmentTree').innerHTML = 
            '<div class="alert alert-danger">Error loading departments</div>';
    }
}

function renderDepartmentTree(departments, level = 0) {
    if (!departments || departments.length === 0) {
        document.getElementById('departmentTree').innerHTML = 
            '<div class="text-muted">No departments</div>';
        return;
    }
    
    let html = '<ul class="tree" style="list-style:none;padding-left:0;">';
    departments.forEach(dept => {
        html += `
            <li style="margin:8px 0;padding-left:${level * 20}px">
                <i class="fas fa-folder-open text-warning"></i>
                <strong>${dept.name}</strong> (${dept.code})
                <span class="badge bg-secondary">level ${dept.level}</span>
        `;
        if (dept.children && dept.children.length > 0) {
            html += renderDepartmentTree(dept.children, level + 1);
        }
        html += '</li>';
    });
    html += '</ul>';
    document.getElementById('departmentTree').innerHTML = html;
}

// 2. Курсы
async function loadCourses() {
    try {
        const courses = await apiRequest('/courses/list?limit=20');
        renderCourses(courses);
    } catch (error) {
        console.error('Error loading courses:', error);
        renderCourses([]);
    }
}

function renderCourses(courses) {
    if (!courses || courses.length === 0) {
        document.getElementById('coursesList').innerHTML = 
            '<div class="alert alert-info">No courses. Create your first course!</div>';
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
                            <strong>${course.code}</strong> - ${currentVer?.title || 'No version'}
                        </h6>
                        <small class="text-muted">
                            Version ${currentVer?.version_number || 0} | 
                            Credits: ${currentVer?.credits || 0} | 
                            Hours: ${currentVer?.hours_total || 0}
                        </small>
                        <div class="mt-1">
                            <button class="btn btn-sm btn-outline-info" onclick="showVersions(${course.id})">
                                <i class="fas fa-history"></i> Versions (${course.all_versions?.length || 0})
                            </button>
                            <button class="btn btn-sm btn-outline-warning" onclick="openUpdateModal(${course.id})">
                                <i class="fas fa-edit"></i> Update
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteCourse(${course.id})">
                                <i class="fas fa-trash"></i> Delete
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
        
        versions.forEach(ver => {
            html += `
                <div class="timeline-item ${ver.is_current ? 'current' : ''}">
                    <div class="timeline-badge ${ver.is_current ? 'bg-success' : 'bg-secondary'}">
                        v${ver.version_number}
                    </div>
                    <div class="timeline-content">
                        <h6>${ver.title}</h6>
                        <p>${ver.description || 'No description'}</p>
                        <small>
                            Credits: ${ver.credits} | Hours: ${ver.hours_total}<br>
                            Created: ${new Date(ver.created_at).toLocaleString()}
                            ${ver.is_current ? '<span class="badge bg-success ms-2">Current</span>' : ''}
                        </small>
                        <button class="btn btn-sm btn-outline-secondary mt-2" onclick="viewSnapshot(${courseId}, ${ver.version_number})">
                            <i class="fas fa-camera"></i> View Snapshot
                        </button>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        document.getElementById('versionHistoryContent').innerHTML = html;
        new bootstrap.Modal(document.getElementById('versionHistoryModal')).show();
    } catch (error) {
        alert('Error loading versions: ' + error.message);
    }
}

async function viewSnapshot(courseId, versionNumber) {
    try {
        const data = await apiRequest(`/courses/${courseId}/versions/${versionNumber}`);
        alert(JSON.stringify(data.snapshot, null, 2));
    } catch (error) {
        alert('Error loading snapshot: ' + error.message);
    }
}

async function deleteCourse(courseId) {
    if (!confirm('Are you sure you want to delete this course?')) return;
    
    try {
        await apiRequest(`/courses/${courseId}`, { method: 'DELETE' });
        showNotification('Course deleted successfully', 'success');
        await loadCourses();
    } catch (error) {
        alert('Error deleting course: ' + error.message);
    }
}

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
        await apiRequest(`/courses/?code=${formData.get('code')}&created_by=1`, {
            method: 'POST',
            body: JSON.stringify(courseData)
        });
        
        showNotification('Course created successfully!', 'success');
        bootstrap.Modal.getInstance(document.getElementById('createCourseModal')).hide();
        form.reset();
        await loadCourses();
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

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
        document.getElementById('studentsList').innerHTML = '<div class="text-muted">No students</div>';
        return;
    }
    
    let html = '<div class="list-group">';
    students.forEach(student => {
        html += `
            <div class="list-group-item">
                <strong>${student.full_name}</strong><br>
                <small>Group: ${student.group_name} | Card: ${student.student_card_number}</small>
            </div>
        `;
    });
    html += '</div>';
    document.getElementById('studentsList').innerHTML = html;
}

function renderTeachers(teachers) {
    if (!teachers || teachers.length === 0) {
        document.getElementById('teachersList').innerHTML = '<div class="text-muted">No teachers</div>';
        return;
    }
    
    let html = '<div class="list-group">';
    teachers.forEach(teacher => {
        html += `
            <div class="list-group-item">
                <strong>${teacher.full_name}</strong><br>
                <small>${teacher.position || 'Position not set'}</small>
            </div>
        `;
    });
    html += '</div>';
    document.getElementById('teachersList').innerHTML = html;
}

// Инициализация
document.addEventListener('DOMContentLoaded', () => {
    loadAllData();
});