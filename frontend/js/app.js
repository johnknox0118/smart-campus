const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && window.location.port === '8000'
    ? "http://localhost:5000/api"
    : "/api";

// Application State
let token = sessionStorage.getItem("access_token");
let user = JSON.parse(sessionStorage.getItem("user"));
let activeView = "home";
let maps = {};
let markers = {};
let geofenceCircles = [];
let attendanceChartInstance = null;
let notificationTicker = null;
let busTicker = null;
let activeAlertsTicker = null;
let activeLocationTicker = null;

// Mock Campus Center (Prathyusha Engineering College)
const CAMPUS_COORDS = [13.092233, 79.973900];
const GEOFENCE_CONFIG = {
    "Entire Campus": { lat: 13.092233, lng: 79.973900, radius: 500, color: '#3A5CCC' },
    "Library": { lat: 13.092300, lng: 79.973900, radius: 30, color: '#e74c3c' },
    "Academic Block": { lat: 13.092233, lng: 79.973900, radius: 100, color: '#2ecc71' },
    "Girls Hostel": { lat: 13.091300, lng: 79.972300, radius: 70, color: '#9b59b6' },
    "Parking": { lat: 13.093200, lng: 79.973900, radius: 50, color: '#f1c40f' },
    "Sports Ground": { lat: 13.092200, lng: 79.971500, radius: 90, color: '#1abc9c' },
    "Boys Hostel": { lat: 13.089800, lng: 79.974900, radius: 60, color: '#e67e22' }
};

// Simulated coordinate dictionary for developer simulator panel
const SIM_COORDINATES = {
    "Library": [13.092300, 79.973900],
    "Academic Block": [13.092233, 79.973900],
    "Girls Hostel": [13.091300, 79.972300],
    "Parking": [13.093200, 79.973900],
    "Sports Ground": [13.092200, 79.971500],
    "Boys Hostel": [13.089800, 79.974900],
    "Entire Campus": [13.092500, 79.973900], // Inside campus, outside sub-zones
    "Outside": [13.0450, 80.0210] // Poonamallee Junction
};

document.addEventListener("DOMContentLoaded", () => {
    if (token && user) {
        initSession();
    } else {
        sessionStorage.clear();
        document.getElementById("loginSection").classList.remove("d-none");
        document.getElementById("dashboardSection").classList.add("d-none");
    }
});

// Toast Notifications System
function showToast(message, type = "success") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast-message ${type === 'emergency' ? 'emergency' : type === 'danger' ? 'emergency' : type === 'success' ? 'success' : ''}`;
    
    let icon = "fa-bell";
    if (type === 'emergency' || type === 'danger') icon = "fa-triangle-exclamation";
    if (type === 'success') icon = "fa-circle-check";
    
    toast.innerHTML = `
        <i class="fa-solid ${icon}"></i>
        <div>${message}</div>
    `;
    container.appendChild(toast);
    
    // Auto-remove after 4 seconds
    setTimeout(() => {
        toast.style.animation = "toast-in 0.35s reverse forwards";
        setTimeout(() => toast.remove(), 350);
    }, 4000);
}

// 1. Session Login Handler
async function handleLogin() {
    const usernameInput = document.getElementById("username").value;
    const passwordInput = document.getElementById("password").value;
    const errorDiv = document.getElementById("loginError");
    
    errorDiv.classList.add("d-none");
    
    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username: usernameInput, password: passwordInput })
        });
        
        const data = await response.json();
        
        if (response.status === 200) {
            sessionStorage.setItem("access_token", data.access_token);
            sessionStorage.setItem("refresh_token", data.refresh_token);
            sessionStorage.setItem("user", JSON.stringify(data.user));
            
            token = data.access_token;
            user = data.user;
            
            showToast(`Welcome back, ${user.username}!`, "success");
            initSession();
        } else {
            errorDiv.innerText = data.message || "Failed authentication.";
            errorDiv.classList.remove("d-none");
        }
    } catch (e) {
        errorDiv.innerText = "Connection error. Ensure Flask backend is running.";
        errorDiv.classList.remove("d-none");
    }
}

// Session Initializer
function initSession() {
    document.getElementById("loginSection").classList.add("d-none");
    document.getElementById("dashboardSection").classList.remove("d-none");
    
    // Profile Sidebar Bindings
    document.getElementById("profileName").innerText = user.username;
    document.getElementById("profileRole").innerText = user.role;
    document.getElementById("userAvatar").innerText = user.username[0].toUpperCase();
    
    // Toggle navigation based on role privileges
    const attendanceMenuItem = document.getElementById("menu-attendance");
    if (['Admin', 'Staff'].includes(user.role)) {
        if (attendanceMenuItem) attendanceMenuItem.classList.remove("d-none");
    } else {
        if (attendanceMenuItem) attendanceMenuItem.classList.add("d-none");
    }
    
    const usersMenuItem = document.getElementById("menu-users");
    if (user.role === 'Admin') {
        if (usersMenuItem) usersMenuItem.classList.remove("d-none");
    } else {
        if (usersMenuItem) usersMenuItem.classList.add("d-none");
    }
    
    // Setup dashboard role views
    setupViewsByRole();
    
    // Initialize interactive Leaflet Map viewpoints
    setTimeout(() => {
        initializeMaps();
        loadDashboardData();
        loadBusData();
        
        // Start polling tickers
        startTickers();
    }, 100);
}

// Session Logout Handler
function handleLogout() {
    // Stop timers
    stopTickers();
    
    // Clear storage
    sessionStorage.clear();
    token = null;
    user = null;
    
    // Destroy map objects to avoid binding errors
    for (let key in maps) {
        if (maps[key]) {
            maps[key].remove();
            maps[key] = null;
        }
    }
    
    document.getElementById("loginSection").classList.remove("d-none");
    document.getElementById("dashboardSection").classList.add("d-none");
    showToast("Signed out successfully", "success");
}

function startTickers() {
    stopTickers();
    
    // Poll unread notifications every 10s
    pollNotifications();
    notificationTicker = setInterval(pollNotifications, 10000);
    
    // Poll bus statuses every 15s
    busTicker = setInterval(loadBusData, 15000);
    
    if (['Admin', 'Security'].includes(user.role)) {
        // Poll security alerts feed every 8s
        loadSecurityAlerts();
        activeAlertsTicker = setInterval(loadSecurityAlerts, 8000);
        
        // Poll active users grid coordinates every 15s
        activeLocationTicker = setInterval(refreshActiveTelemetryMap, 10000);
    }
}

function stopTickers() {
    clearInterval(notificationTicker);
    clearInterval(busTicker);
    clearInterval(activeAlertsTicker);
    clearInterval(activeLocationTicker);
    if (window.driverLocationInterval) {
        clearInterval(window.driverLocationInterval);
    }
}

// 2. Navigation Switcher
function switchView(viewName) {
    // Reset active nav link CSS
    document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
    
    // Show view div
    document.querySelectorAll(".dashboard-view").forEach(el => el.classList.remove("active"));
    
    const targetMenu = document.getElementById(`menu-${viewName}`);
    if (targetMenu) targetMenu.classList.add("active");
    
    const viewDiv = document.getElementById(`view-${viewName}`);
    if (viewDiv) viewDiv.classList.add("active");
    
    activeView = viewName;
    
    // Adjust headers
    const titles = {
        "home": "Dashboard Overview",
        "tracking": "Live Interactive Campus Map & Alerts",
        "leaves": "Leave Request & Workflow Log",
        "buses": "Bus Transit & Fleet Center",
        "attendance": "Unified Attendance Center",
        "users": "User Directory & Configuration"
    };
    document.getElementById("viewTitle").innerText = titles[viewName] || "Dashboard";
    
    // Force Leaflet maps recalculation after tab displays
    setTimeout(() => {
        for (let key in maps) {
            if (maps[key]) {
                maps[key].invalidateSize();
            }
        }
        
        // Refresh specific view feeds
        if (viewName === 'leaves') loadLeaveData();
        if (viewName === 'buses') { switchBusSubView('tracker'); loadBusData(); }
        if (viewName === 'tracking') { refreshCampusTrackViewMap(); loadSecurityAlerts(); }
        if (viewName === 'attendance') { switchAttSubView('take'); }
        if (viewName === 'users') loadUserDirectory();
    }, 100);
}

// Initialize HTML panels based on privileges
function setupViewsByRole() {
    const adminVis = document.getElementById("adminVisuals");
    const studentVis = document.getElementById("studentVisuals");
    const leaveApp = document.getElementById("leaveApplicationBlock");
    const leaveApproval = document.getElementById("leaveApprovalPanel");
    const driverPanel = document.getElementById("driverBusPanel");
    
    adminVis.classList.add("d-none");
    studentVis.classList.add("d-none");
    leaveApp.classList.add("d-none");
    leaveApproval.classList.add("d-none");
    driverPanel.classList.add("d-none");
    
    // Adjust live map layout for non-alert monitoring roles
    const alertsPanel = document.getElementById("alertsPanelContainer");
    const mapCol = document.querySelector("#view-tracking .col-lg-8");
    if (['Admin', 'Security'].includes(user.role)) {
        if (alertsPanel) alertsPanel.classList.remove("d-none");
        if (mapCol) {
            mapCol.classList.remove("col-12");
            mapCol.classList.add("col-lg-8");
        }
    } else {
        if (alertsPanel) alertsPanel.classList.add("d-none");
        if (mapCol) {
            mapCol.classList.remove("col-lg-8");
            mapCol.classList.add("col-12");
        }
    }

    // Toggle Bus Management Sub-tab
    const busTabManage = document.getElementById("btnBusTabManage");
    if (user.role === 'Admin') {
        if (busTabManage) busTabManage.classList.remove("d-none");
    } else {
        if (busTabManage) busTabManage.classList.add("d-none");
    }

    // Toggle Attendance Reports Sub-tab
    const attTabReports = document.getElementById("btnAttTabReports");
    if (['Admin', 'Staff'].includes(user.role)) {
        if (attTabReports) attTabReports.classList.remove("d-none");
        
        // Admin-only report elements hiding
        const adminOnlyElems = document.querySelectorAll('.admin-only-report-elem');
        const staffSection = document.getElementById('reportStaffSection');
        if (user.role === 'Admin') {
            adminOnlyElems.forEach(el => el.classList.remove('d-none'));
            if (staffSection) staffSection.classList.remove('d-none');
        } else {
            adminOnlyElems.forEach(el => el.classList.add('d-none'));
            if (staffSection) staffSection.classList.add('d-none');
        }
        
        // Hide Department filter in Take Attendance view for Staff
        const filterAttDeptEl = document.getElementById("filterAttDept");
        if (user.role === 'Staff') {
            if (filterAttDeptEl) filterAttDeptEl.classList.add("d-none");
        } else {
            if (filterAttDeptEl) filterAttDeptEl.classList.remove("d-none");
        }
    } else {
        if (attTabReports) attTabReports.classList.add("d-none");
    }

    if (user.role === 'Admin') {
        adminVis.classList.remove("d-none");
        leaveApproval.classList.remove("d-none");
    } else if (user.role === 'Staff') {
        studentVis.classList.remove("d-none");
        leaveApproval.classList.remove("d-none");
    } else if (user.role === 'Student') {
        studentVis.classList.remove("d-none");
        leaveApp.classList.remove("d-none");
    } else if (user.role === 'Driver') {
        driverPanel.classList.remove("d-none");
    } else if (user.role === 'Security') {
        adminVis.classList.remove("d-none"); // Needs the map view
    }
}

// 3. Leaflet & Charts Configuration
function initializeMaps() {
    // Helper to draw geofence zones
    function drawGeofences(mapInstance) {
        // Drop the exact red Google Maps location pin at the college center
        const collegeIcon = L.icon({
            iconUrl: 'https://maps.google.com/mapfiles/ms/icons/red-dot.png',
            iconSize: [32, 32],
            iconAnchor: [16, 32],
            popupAnchor: [0, -32]
        });
        L.marker([13.092233, 79.973900], { icon: collegeIcon }).addTo(mapInstance)
         .bindPopup("<b>Prathyusha Engineering College (PEC)</b>").openPopup();
    }

    // 1. Admin Map
    if (document.getElementById("adminMap") && !maps["adminMap"]) {
        maps["adminMap"] = L.map("adminMap").setView(CAMPUS_COORDS, 16);
        L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
            maxZoom: 20
        }).addTo(maps["adminMap"]);
        drawGeofences(maps["adminMap"]);
    }
    
    // 2. Student Map
    if (document.getElementById("studentMap") && !maps["studentMap"]) {
        maps["studentMap"] = L.map("studentMap").setView(CAMPUS_COORDS, 16);
        L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
            maxZoom: 20
        }).addTo(maps["studentMap"]);
        drawGeofences(maps["studentMap"]);
        // Place initial mock marker
        const blueIcon = L.icon({
            iconUrl: 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png',
            iconSize: [32, 32],
            iconAnchor: [16, 32],
            popupAnchor: [0, -32]
        });
        markers["studentMarker"] = L.marker(CAMPUS_COORDS, { icon: blueIcon }).addTo(maps["studentMap"]).bindPopup("My Current Location");
    }
    
    // 3. Bus Map
    if (document.getElementById("busMap") && !maps["busMap"]) {
        maps["busMap"] = L.map("busMap").setView(CAMPUS_COORDS, 14);
        L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
            maxZoom: 20
        }).addTo(maps["busMap"]);
        // Draw campus center ring
        L.circle(CAMPUS_COORDS, { color: '#B20716', radius: 500 }).addTo(maps["busMap"]).bindPopup("PEC Main Campus");
    }
    
    // 4. Tracking tab map
    if (document.getElementById("trackingViewMap") && !maps["trackingViewMap"]) {
        maps["trackingViewMap"] = L.map("trackingViewMap").setView(CAMPUS_COORDS, 16);
        L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
            maxZoom: 20
        }).addTo(maps["trackingViewMap"]);
        drawGeofences(maps["trackingViewMap"]);
    }
}

// 4. Simulator Functions (Cybersecurity telemetry mimics)
let lastLoggedTime = null;
let lastLoggedCoords = null;

function loadSimCoordinates() {
    const selector = document.getElementById("simGeofence");
    const selectedZone = selector.value;
    // Simulator visual feedback
}

async function sendSimulatedGPS() {
    const zone = document.getElementById("simGeofence").value;
    const isMocked = document.getElementById("simMockGPS").checked;
    const isSpeedHack = document.getElementById("simSpeedHack").checked;
    
    let coords = [...SIM_COORDINATES[zone]];
    
    // If speed hack is toggled, simulate jumping 2.5 kilometers away instantly
    if (isSpeedHack) {
        coords[0] += 0.02; // Roughly 2.2 km shift north
        coords[1] += 0.02;
    }
    
    try {
        const response = await fetch(`${API_BASE}/gps/track`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({
                latitude: coords[0],
                longitude: coords[1],
                speed: isSpeedHack ? 180.0 : 1.2,
                accuracy: isMocked ? 0.0 : 8.0,
                battery: 88,
                mocked: isMocked
            })
        });
        
        const data = await response.json();
        
        if (response.status === 200) {
            if (data.is_spoofed) {
                showToast(`TELEMETRY ALARM: Spoof detected! Reason: ${data.spoof_reason}`, "danger");
            } else {
                showToast(`Location logged successfully! Current Zone: ${data.geofence}`, "success");
            }
            
            // Update Student personal map viewport
            if (maps["studentMap"] && markers["studentMarker"]) {
                const newLatLng = new L.LatLng(coords[0], coords[1]);
                markers["studentMarker"].setLatLng(newLatLng);
                maps["studentMap"].panTo(newLatLng);
                markers["studentMarker"].bindPopup(`My Location: Inside ${data.geofence}`).openPopup();
            }
            
            // Refresh feeds
            loadDashboardData();
        } else {
            showToast(data.message || "Failed uploading telemetry.", "danger");
        }
    } catch (e) {
        showToast("Error communicating with GPS track endpoint.", "danger");
    }
}

// SOS Trigger
async function triggerPanicSOS() {
    // Get mock current position
    let coords = CAMPUS_COORDS;
    if (markers["studentMarker"]) {
        const currentLatLng = markers["studentMarker"].getLatLng();
        coords = [currentLatLng.lat, currentLatLng.lng];
    }
    
    try {
        const response = await fetch(`${API_BASE}/emergency/sos`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ latitude: coords[0], longitude: coords[1] })
        });
        const data = await response.json();
        if (response.status === 201) {
            showToast("SOS DISTRESS BEACON EMITTED! Security guards notified.", "emergency");
        } else {
            showToast(data.message || "SOS dispatch error.", "danger");
        }
    } catch (e) {
        showToast("Emergency API down. Trigger fail.", "danger");
    }
}

// Helper: formats Authorization Bearer headers
function f(token) { return token; }

// 5. Data Loaders
async function loadDashboardData() {
    if (!token) return;
    
    // Bind generic student attendance histories
    if (user.role === 'Student' || user.role === 'Staff') {
        try {
            const response = await fetch(`${API_BASE}/leave/history`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            const data = await response.json();
            
            // Fetch personal student attendance records
            // We'll write a quick fetch for attendance logs
            const profileResp = await fetch(`${API_BASE}/auth/profile`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            const profile = await profileResp.json();
            
            // Let's populate mock data or call history endpoints if available.
            // For students, we'll fetch locations and attendance directly
        } catch (e) {}
    }
    
    if (user.role === 'Admin') {
        try {
            const response = await fetch(`${API_BASE}/analytics/dashboard`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            const data = await response.json();
            
            if (response.status === 200) {
                // Populate Admin KPI Cards
                const cards = data.cards;
                const grid = document.getElementById("statsGrid");
                grid.innerHTML = `
                    <div class="stat-card glass-panel success">
                        <div class="stat-info">
                            <h4>Students Present</h4>
                            <p>${cards.students_present}</p>
                        </div>
                        <div class="stat-icon"><i class="fa-solid fa-user-check"></i></div>
                    </div>
                    <div class="stat-card glass-panel danger">
                        <div class="stat-info">
                            <h4>Students Absent</h4>
                            <p>${cards.students_absent}</p>
                        </div>
                        <div class="stat-icon"><i class="fa-solid fa-user-xmark"></i></div>
                    </div>
                    <div class="stat-card glass-panel accent">
                        <div class="stat-info">
                            <h4>Buses Operating</h4>
                            <p>${cards.active_buses}/${cards.total_buses}</p>
                        </div>
                        <div class="stat-icon"><i class="fa-solid fa-bus-simple"></i></div>
                    </div>
                    <div class="stat-card glass-panel danger">
                        <div class="stat-info">
                            <h4>Active SOS Alerts</h4>
                            <p id="sosAlertsCardCount">${cards.active_emergencies}</p>
                        </div>
                        <div class="stat-icon" style="color: var(--danger);"><i class="fa-solid fa-kit-medical"></i></div>
                    </div>
                `;
                
                // Draw Chart
                renderCharts(data.charts);
                
                // Fetch active maps telemetry overlay
                refreshActiveTelemetryMap();
            }
        } catch (e) {}
    } else {
        // Populate Student/Staff/Driver Stats Cards
        const grid = document.getElementById("statsGrid");
        if (user.role === 'Student') {
            grid.innerHTML = `
                <div class="stat-card glass-panel success">
                    <div class="stat-info">
                        <h4>My Attendance Rate</h4>
                        <p>94.2%</p>
                    </div>
                    <div class="stat-icon"><i class="fa-solid fa-calendar-check"></i></div>
                </div>
                <div class="stat-card glass-panel accent">
                    <div class="stat-info">
                        <h4>Geofence Zone</h4>
                        <p id="myGeofenceCard">Entire Campus</p>
                    </div>
                    <div class="stat-icon"><i class="fa-solid fa-map-pin"></i></div>
                </div>
                <div class="stat-card glass-panel success">
                    <div class="stat-info">
                        <h4>Approved Leaves</h4>
                        <p>2 Days</p>
                    </div>
                    <div class="stat-icon"><i class="fa-solid fa-plane-departure"></i></div>
                </div>
            `;
            fetchStudentPersonalAttendance();
        } else if (user.role === 'Driver') {
            grid.innerHTML = `
                <div class="stat-card glass-panel success">
                    <div class="stat-info">
                        <h4>Operating Status</h4>
                        <p id="driverStatusCard">Ready</p>
                    </div>
                    <div class="stat-icon"><i class="fa-solid fa-circle-play"></i></div>
                </div>
                <div class="stat-card glass-panel accent">
                    <div class="stat-info">
                        <h4>Bus Fleet Assigned</h4>
                        <p>TEST-BUS-01</p>
                    </div>
                    <div class="stat-icon"><i class="fa-solid fa-bus-simple"></i></div>
                </div>
            `;
        }
    }
    
    // Render dynamic Quick Action Feature Hub Cards
    renderFeatureHub();
}

function renderFeatureHub() {
    const hubGrid = document.getElementById("featureHubGrid");
    if (!hubGrid) return;
    
    hubGrid.innerHTML = "";
    
    const allModules = [
        {
            title: "Live Campus Map & Locator",
            desc: "Track active students, staff and geofences. Search coordinates live.",
            icon: "fa-map-location-dot",
            color: "#3498db",
            view: "tracking",
            roles: ["Admin", "Staff", "Student", "Security"]
        },
        {
            title: "Leave Workflows",
            desc: "File leaves, check progress or approve requests instantly.",
            icon: "fa-calendar-minus",
            color: "#f39c12",
            view: "leaves",
            roles: ["Admin", "Staff", "Student"]
        },
        {
            title: "Bus Tracking & Fleet",
            desc: "Track bus locations, edit routes, manage fleet details and assign drivers.",
            icon: "fa-bus",
            color: "#1abc9c",
            view: "buses",
            roles: ["Admin", "Staff", "Student", "Driver", "Security"]
        },
        {
            title: "Attendance Management",
            desc: "Manually log attendance and download professional reports (Excel & PDF).",
            icon: "fa-clipboard-user",
            color: "#9b59b6",
            view: "attendance",
            roles: ["Admin", "Staff"]
        },
        {
            title: "User Registry & Directory",
            desc: "Add, modify or delete staff, student, security, and driver profiles.",
            icon: "fa-users-gear",
            color: "#e67e22",
            view: "users",
            roles: ["Admin"]
        }
    ];
    
    const userModules = allModules.filter(m => m.roles.includes(user.role));
    
    userModules.forEach(m => {
        hubGrid.innerHTML += `
            <div class="col-md-4 col-sm-6 mb-3">
                <div class="glass-panel p-3 h-100 cursor-pointer feature-hub-card" onclick="switchView('${m.view}')" 
                     style="border: 1px solid rgba(255,255,255,0.05); transition: all 0.3s ease; cursor: pointer;">
                    <div class="d-flex align-items-start gap-3">
                        <div class="p-3 rounded" style="background: rgba(255, 255, 255, 0.03); color: ${m.color}; border: 1px solid rgba(255,255,255,0.05);">
                            <i class="fa-solid ${m.icon} fa-xl"></i>
                        </div>
                        <div>
                            <h4 style="font-size: 0.95rem; font-weight: 600; color: var(--text-main); margin-bottom: 5px;">${m.title}</h4>
                            <p class="text-muted" style="font-size: 0.75rem; margin: 0; line-height: 1.3;">${m.desc}</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
}

// Fetch Personal student attendance list
async function fetchStudentPersonalAttendance() {
    try {
        // Fetch personal profile to get ID
        const profileResp = await fetch(`${API_BASE}/auth/profile`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const profile = await profileResp.json();
        
        const historyResp = await fetch(`${API_BASE}/gps/history/${profile.id}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const historyData = await historyResp.json();
        
        // Build mock visual attendance sheet based on history or insert records
        const tbody = document.getElementById("studentAttendanceTable");
        tbody.innerHTML = "";
        
        // Let's populate past 5 days mock attendance
        const statuses = ["Present", "Late", "Present", "Present", "On Leave"];
        const dates = [
            dateOffset(0), dateOffset(-1), dateOffset(-2), dateOffset(-3), dateOffset(-4)
        ];
        
        for (let i = 0; i < 5; i++) {
            tbody.innerHTML += `
                <tr>
                    <td>${dates[i]}</td>
                    <td>${statuses[i] === 'On Leave' ? '-' : '08:15 AM'}</td>
                    <td>${statuses[i] === 'On Leave' ? '-' : '04:10 PM'}</td>
                    <td>${statuses[i] === 'On Leave' ? '0.0' : '7.9'}</td>
                    <td><span class="badge ${statuses[i].toLowerCase().replace(' ', '-')}">${statuses[i]}</span></td>
                </tr>
            `;
        }
        
        // Update myGeofenceCard from latest logs
        if (historyData.history && historyData.history.length > 0) {
            const latest = historyData.history[0];
            document.getElementById("myGeofenceCard").innerText = latest.geofence_name;
        }
    } catch(e) {}
}

function dateOffset(days) {
    const d = new Date();
    d.setDate(d.getDate() + days);
    return d.toISOString().split('T')[0];
}

// Draw charts using Chart.js
function renderCharts(chartData) {
    const ctx = document.getElementById("attendanceChart");
    if (!ctx) return;
    
    if (attendanceChartInstance) {
        attendanceChartInstance.destroy();
    }
    
    attendanceChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartData.monthly_trends.labels,
            datasets: [{
                label: 'Monthly Attendance Rate (%)',
                data: chartData.monthly_trends.data,
                borderColor: '#B20716',
                backgroundColor: 'rgba(178, 7, 22, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#FFF' }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#A3A7C1' }
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#A3A7C1' },
                    min: 50,
                    max: 100
                }
            }
        }
    });
}

// 6. Security Admin Maps Telemetry refreshes
let adminMarkers = {};

async function refreshActiveTelemetryMap() {
    if (activeView !== 'home' && activeView !== 'tracking') return;
    
    try {
        const response = await fetch(`${API_BASE}/gps/active`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json();
        
        if (response.status === 200 && data.users) {
            activeUsersCache = data.users;
            const map = maps["adminMap"] || maps["trackingViewMap"];
            if (!map) return;
            
            // Clear prior user markers
            for (let key in adminMarkers) {
                map.removeLayer(adminMarkers[key]);
            }
            adminMarkers = {};
            
            data.users.forEach(usr => {
                let color = usr.role === 'Driver' ? '#ED9700' : '#B20716';
                let icon = L.divIcon({
                    className: 'custom-div-icon',
                    html: `<div style="background-color: ${color}; width: 14px; height: 14px; border: 2px solid #FFF; border-radius: 50%; box-shadow: 0 0 10px ${color}"></div>`,
                    iconSize: [14, 14],
                    iconAnchor: [7, 7]
                });
                
                let marker = L.marker([usr.latitude, usr.longitude], { icon: icon }).addTo(map);
                marker.bindPopup(`
                    <b>${usr.username} (${usr.role})</b><br>
                    Zone: ${usr.geofence_name}<br>
                    Speed: ${usr.speed.toFixed(1)} km/h<br>
                    Battery: ${usr.battery}%<br>
                    Last seen: ${usr.timestamp}
                `);
                adminMarkers[usr.user_id] = marker;
            });
        }
    } catch (e) {}
}

function refreshCampusTrackViewMap() {
    const map = maps["trackingViewMap"];
    if (map) {
        map.invalidateSize();
        refreshActiveTelemetryMap();
    }
}

// 7. Leave Applications submission and retrieval
async function submitLeaveRequest() {
    const start = document.getElementById("leaveStart").value;
    const end = document.getElementById("leaveEnd").value;
    const reason = document.getElementById("leaveReason").value;
    
    try {
        const response = await fetch(`${API_BASE}/leave/request`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ start_date: start, end_date: end, reason: reason })
        });
        
        const data = await response.json();
        
        if (response.status === 201) {
            showToast("Leave request filed. Pending approvals.", "success");
            document.getElementById("leaveRequestForm").reset();
            loadLeaveData();
        } else {
            showToast(data.message || "Failed filing leave.", "danger");
        }
    } catch (e) {
        showToast("Server unreachable for leaves.", "danger");
    }
}

async function loadLeaveData() {
    if (!token) return;
    
    // 1. Fetch own leave request logs (Students & Staff)
    if (user.role === 'Student' || user.role === 'Staff') {
        try {
            const response = await fetch(`${API_BASE}/leave/history`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            const data = await response.json();
            
            const tbody = document.getElementById("leaveHistoryTable");
            tbody.innerHTML = "";
            
            if (data.history && data.history.length > 0) {
                data.history.forEach(leave => {
                    tbody.innerHTML += `
                        <tr>
                            <td>${leave.start_date}</td>
                            <td>${leave.end_date}</td>
                            <td>${leave.reason}</td>
                            <td><span class="badge ${leave.status.toLowerCase()}">${leave.status}</span></td>
                        </tr>
                    `;
                });
            } else {
                tbody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-muted">No past leave applications</td></tr>`;
            }
        } catch (e) {}
    }
    
    // 2. Fetch pending student leaves (Admins & Staff)
    if (['Admin', 'Staff'].includes(user.role)) {
        try {
            const response = await fetch(`${API_BASE}/leave/pending`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            const data = await response.json();
            
            const tbody = document.getElementById("pendingLeavesTable");
            tbody.innerHTML = "";
            
            if (data.pending && data.pending.length > 0) {
                data.pending.forEach(leave => {
                    tbody.innerHTML += `
                        <tr>
                            <td><b>${leave.username}</b> (${leave.role})</td>
                            <td>${leave.department || "No Department"}</td>
                            <td>${leave.start_date}</td>
                            <td>${leave.end_date}</td>
                            <td>${leave.reason}</td>
                            <td>
                                <button class="btn btn-sm btn-success me-1 py-1 px-2" style="font-size:0.75rem;" onclick="processLeaveApproval(${leave.id}, 'Approved')">Approve</button>
                                <button class="btn btn-sm btn-danger py-1 px-2" style="font-size:0.75rem;" onclick="processLeaveApproval(${leave.id}, 'Rejected')">Reject</button>
                            </td>
                        </tr>
                    `;
                });
            } else {
                tbody.innerHTML = `<tr><td colspan="6" class="text-center py-3 text-muted">No pending leave requests</td></tr>`;
            }
        } catch(e) {}
    }
}

async function processLeaveApproval(leaveId, decision) {
    try {
        const response = await fetch(`${API_BASE}/leave/approve/${leaveId}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ status: decision })
        });
        
        const data = await response.json();
        
        if (response.status === 200) {
            showToast(`Leave request successfully marked as ${decision}`, "success");
            loadLeaveData();
            loadDashboardData();
        } else {
            showToast(data.message || "Failed processing leave decision.", "danger");
        }
    } catch(e) {
        showToast("Error processing leave approval.", "danger");
    }
}

// 8. Driver bus trip controllers
function toggleTrip(startTrip) {
    const btnStart = document.getElementById("btnStartTrip");
    const btnEnd = document.getElementById("btnEndTrip");
    const nextStopSelect = document.getElementById("driverNextStop");
    const etaInput = document.getElementById("driverEta");
    const cardStatus = document.getElementById("driverStatusCard");
    
    if (startTrip) {
        btnStart.disabled = true;
        btnEnd.disabled = false;
        nextStopSelect.disabled = true;
        etaInput.disabled = true;
        cardStatus.innerText = "Transit Active";
        showToast("Trip started. Live GPS uploads active.", "success");
        
        // Start simulated periodic location uploads (Every 10 seconds)
        let coordsIndex = 0;
        const busRouteCoords = [
            [13.0450, 80.0210], // Poonamallee
            [13.0560, 80.0080],
            [13.0680, 79.9960],
            [13.0800, 79.9840], // Near campus
            [13.089800, 79.974900]  // Boys Hostel
        ];
        
        window.driverLocationInterval = setInterval(async () => {
            if (coordsIndex >= busRouteCoords.length) {
                coordsIndex = busRouteCoords.length - 1;
            }
            
            const currentCoords = busRouteCoords[coordsIndex];
            const nextStop = nextStopSelect.value;
            const eta = Math.max(0, parseInt(etaInput.value) - (coordsIndex * 3));
            
            try {
                await fetch(`${API_BASE}/bus/location`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        latitude: currentCoords[0],
                        longitude: currentCoords[1],
                        speed: 48.0,
                        eta_mins: eta,
                        next_stop: nextStop
                    })
                });
            } catch (e) {}
            
            coordsIndex++;
        }, 10000);
        
    } else {
        btnStart.disabled = false;
        btnEnd.disabled = true;
        nextStopSelect.disabled = false;
        etaInput.disabled = false;
        cardStatus.innerText = "Ready";
        showToast("Trip completed. Telemetry updates stopped.", "success");
        
        clearInterval(window.driverLocationInterval);
    }
}

// 9. Load Bus Telemetry Status & Map overlays
let busMarkers = {};

async function loadBusData() {
    if (activeView !== 'buses' && activeView !== 'home') return;
    
    try {
        const response = await fetch(`${API_BASE}/bus/status`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json();
        
        if (response.status === 200 && data.buses) {
            // Update Table
            const tbody = document.getElementById("busesTable");
            if (tbody) {
                tbody.innerHTML = "";
                
                if (data.buses.length > 0) {
                    data.buses.forEach(bus => {
                        tbody.innerHTML += `
                            <tr>
                                <td><b>${bus.bus_number}</b></td>
                                <td>${bus.route_name}</td>
                                <td>${bus.driver_name}</td>
                                <td>${bus.next_stop}</td>
                                <td>${bus.eta_mins} mins</td>
                                <td>${bus.speed.toFixed(1)} km/h</td>
                                <td><span class="badge ${bus.status === 'Active' ? 'present' : 'leave'}">${bus.status}</span></td>
                            </tr>
                        `;
                    });
                } else {
                    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-3 text-muted">No bus operations logged</td></tr>`;
                }
            }
            
            // Update Bus map markers
            const map = maps["busMap"];
            if (map) {
                // Clear old bus markers
                for (let key in busMarkers) {
                    map.removeLayer(busMarkers[key]);
                }
                busMarkers = {};
                
                data.buses.forEach(bus => {
                    if (bus.latitude && bus.longitude) {
                        let busIcon = L.divIcon({
                            className: 'custom-bus-icon',
                            html: `<div style="background-color: var(--accent); width: 32px; height: 32px; border: 2px solid #FFF; border-radius: 6px; box-shadow: 0 0 10px var(--accent-glow); display:flex; justify-content:center; align-items:center; color:#000;"><i class="fa-solid fa-bus-simple" style="font-size:0.9rem;"></i></div>`,
                            iconSize: [32, 32],
                            iconAnchor: [16, 16]
                        });
                        
                        let marker = L.marker([bus.latitude, bus.longitude], { icon: busIcon }).addTo(map);
                        marker.bindPopup(`
                            <b>Bus: ${bus.bus_number}</b><br>
                            Route: ${bus.route_name}<br>
                            Driver: ${bus.driver_name}<br>
                            Next Stop: ${bus.next_stop}<br>
                            ETA: ${bus.eta_mins} Mins<br>
                            Speed: ${bus.speed.toFixed(1)} km/h<br>
                            Last Update: ${bus.last_updated}
                        `);
                        busMarkers[bus.id] = marker;
                        
                        // Pan to show active buses if there are any
                        map.panTo([bus.latitude, bus.longitude]);
                    }
                });
            }
        }
    } catch(e) {}
}

// 10. Security alerts feed & distress alerts list
async function loadSecurityAlerts() {
    if (!['Admin', 'Security'].includes(user.role)) return;
    
    try {
        // 1. Fetch unread/urgent security notifications
        const notifResponse = await fetch(`${API_BASE}/notifications/unread`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const notifData = await notifResponse.json();
        
        // 2. Fetch active SOS alerts
        const sosResponse = await fetch(`${API_BASE}/emergency/active`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const sosData = await sosResponse.json();
        
        const feedDiv = document.getElementById("securityAlertsList");
        if (!feedDiv) return;
        
        feedDiv.innerHTML = "";
        let totalAlerts = 0;
        
        // Add active SOS alerts first
        if (sosData.alerts && sosData.alerts.length > 0) {
            totalAlerts += sosData.alerts.length;
            sosData.alerts.forEach(alert => {
                feedDiv.innerHTML += `
                    <div class="alert-item critical">
                        <div class="alert-item-content">
                            <h5 style="color: var(--danger);"><i class="fa-solid fa-triangle-exclamation me-2"></i>CRITICAL SOS PANIC ALERT</h5>
                            <p><b>Reporter:</b> ${alert.username} (${alert.role}) | <b>GPS:</b> (${alert.latitude.toFixed(5)}, ${alert.longitude.toFixed(5)})</p>
                            <span class="badge active mt-2">Active distress</span>
                        </div>
                        <div class="d-flex flex-column align-items-end">
                            <span class="alert-time mb-2">${alert.created_at}</span>
                            <button class="btn btn-sm btn-success py-1 px-2" style="font-size:0.75rem;" onclick="resolveEmergencyAlert(${alert.id})">
                                <i class="fa-solid fa-check me-1"></i>Resolve SOS
                            </button>
                        </div>
                    </div>
                `;
            });
        }
        
        // Add other security alerts from notifications feed (e.g. spoof warnings)
        if (notifData.notifications) {
            const securityLogs = notifData.notifications.filter(n => ['Security', 'Emergency'].includes(n.type));
            totalAlerts += securityLogs.length;
            
            securityLogs.forEach(notif => {
                feedDiv.innerHTML += `
                    <div class="alert-item">
                        <div class="alert-item-content">
                            <h5 style="color: var(--accent);"><i class="fa-solid fa-shield-halved me-2"></i>Security Telemetry Warning</h5>
                            <p>${notif.message}</p>
                        </div>
                        <div class="d-flex flex-column align-items-end">
                            <span class="alert-time mb-2">${notif.created_at}</span>
                            <button class="btn btn-sm btn-outline-secondary py-1 px-2" style="font-size:0.7rem; color:var(--text-muted); border-color:var(--glass-border);" onclick="dismissNotification(${notif.id})">Dismiss</button>
                        </div>
                    </div>
                `;
            });
        }
        
        if (totalAlerts === 0) {
            feedDiv.innerHTML = `<div class="text-center py-5 text-muted">No active emergency alerts or security warnings.</div>`;
        }
        
        // Update Admin SOS card counter
        const sosCardCount = document.getElementById("sosAlertsCardCount");
        if (sosCardCount) {
            sosCardCount.innerText = sosData.alerts ? sosData.alerts.length : 0;
        }
    } catch(e) {}
}

async function resolveEmergencyAlert(alertId) {
    try {
        const response = await fetch(`${API_BASE}/emergency/resolve/${alertId}`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (response.status === 200) {
            showToast("Emergency alert resolved successfully.", "success");
            loadSecurityAlerts();
            loadDashboardData();
        }
    } catch (e) {}
}

async function dismissNotification(notifId) {
    try {
        await fetch(`${API_BASE}/notifications/read/${notifId}`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` }
        });
        loadSecurityAlerts();
        pollNotifications();
    } catch (e) {}
}

// 11. Pull Notifications bell drop-downs
async function pollNotifications() {
    if (!token) return;
    
    try {
        const response = await fetch(`${API_BASE}/notifications/unread`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json();
        
        if (response.status === 200 && data.notifications) {
            const badge = document.getElementById("notifBadge");
            const dropdownList = document.getElementById("notifList");
            const unreadCount = data.notifications.length;
            
            if (unreadCount > 0) {
                badge.innerText = unreadCount;
                badge.classList.remove("d-none");
                
                dropdownList.innerHTML = "";
                data.notifications.slice(0, 5).forEach(notif => {
                    let color = "var(--text-main)";
                    if (notif.type === 'Emergency') color = "var(--danger)";
                    if (notif.type === 'Security') color = "var(--accent)";
                    
                    dropdownList.innerHTML += `
                        <li class="py-2 border-bottom border-secondary" style="font-size:0.8rem;">
                            <div class="d-flex justify-content-between">
                                <span style="color: ${color}; font-weight:600;">${notif.type}</span>
                                <span class="text-muted" style="font-size:0.7rem;">${notif.created_at.split(' ')[1]}</span>
                            </div>
                            <p class="mb-1 text-muted mt-1" style="font-size:0.75rem; line-height:1.2;">${notif.message}</p>
                            <a onclick="dismissNotification(${notif.id})" class="text-accent" style="cursor:pointer; font-size:0.7rem; color:var(--accent);">Mark Read</a>
                        </li>
                    `;
                });
            } else {
                badge.classList.add("d-none");
                dropdownList.innerHTML = `<li class="text-center py-3 text-muted">No unread notifications</li>`;
            }
        }
    } catch(e) {}
}

// 7. Manual Attendance Actions (Staff & Admin)
let attendanceDataCache = [];

async function loadAttendanceList() {
    if (activeView !== 'attendance') return;
    const tbody = document.getElementById("attendanceListTableBody");
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted"><i class="fa-solid fa-circle-notch fa-spin me-2"></i>Loading students...</td></tr>`;
    
    try {
        const response = await fetch(`${API_BASE}/attendance/students`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json();
        
        if (response.status === 200 && data.students) {
            attendanceDataCache = data.students;
            renderAttendanceTable(attendanceDataCache);
        } else {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Failed to load student attendance data.</td></tr>`;
        }
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Server connection error.</td></tr>`;
    }
}

function renderAttendanceTable(studentsList) {
    const tbody = document.getElementById("attendanceListTableBody");
    tbody.innerHTML = "";
    
    if (studentsList.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No students found.</td></tr>`;
        return;
    }
    
    studentsList.forEach(stud => {
        let statusClass = stud.attendance_today.status.toLowerCase().replace(" ", "-");
        if (stud.attendance_today.status === 'Not Marked') {
            statusClass = 'text-muted';
        }
        
        const currentStatus = stud.attendance_today.status;
        
        tbody.innerHTML += `
            <tr data-student-id="${stud.student_id}">
                <td style="font-weight: 600;">${stud.name}</td>
                <td>${stud.department}</td>
                <td><i class="fa-solid fa-location-dot me-1 text-muted"></i>${stud.last_seen_geofence}</td>
                <td>${stud.attendance_today.check_in}</td>
                <td>${stud.attendance_today.check_out}</td>
                <td><span class="badge ${statusClass}">${stud.attendance_today.status}</span></td>
                <td>
                    <div class="d-flex gap-2 align-items-center">
                        <button class="btn-att-choice present ${currentStatus === 'Present' ? 'active' : ''}" onclick="markStudentAttendance(${stud.student_id}, 'Present')" title="Mark Present">P</button>
                        <button class="btn-att-choice absent ${currentStatus === 'Absent' ? 'active' : ''}" onclick="markStudentAttendance(${stud.student_id}, 'Absent')" title="Mark Absent">A</button>
                        <button class="btn-att-choice on-duty ${currentStatus === 'On Duty' ? 'active' : ''}" onclick="markStudentAttendance(${stud.student_id}, 'On Duty')" title="Mark On Duty">OD</button>
                        <button class="btn-att-choice on-leave ${currentStatus === 'On Leave' ? 'active' : ''}" onclick="markStudentAttendance(${stud.student_id}, 'On Leave')" title="Mark On Leave">OL</button>
                    </div>
                </td>
            </tr>
        `;
    });
}

function filterAttendanceTable() {
    const query = document.getElementById("attendanceSearch").value.toLowerCase();
    const deptQuery = document.getElementById("filterAttDept").value;
    const yearQuery = document.getElementById("filterAttYear").value;
    const sectQuery = document.getElementById("filterAttSection").value;
    
    let filtered = attendanceDataCache;
    
    if (query) {
        filtered = filtered.filter(stud => 
            stud.username.toLowerCase().includes(query) || 
            stud.name.toLowerCase().includes(query)
        );
    }
    
    if (deptQuery) {
        filtered = filtered.filter(stud => stud.department === deptQuery);
    }
    
    if (yearQuery) {
        filtered = filtered.filter(stud => stud.year === yearQuery);
    }
    
    if (sectQuery) {
        filtered = filtered.filter(stud => stud.section === sectQuery);
    }
    
    renderAttendanceTable(filtered);
}

async function markStudentAttendance(studentId, newStatus) {
    try {
        const response = await fetch(`${API_BASE}/attendance/mark`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ student_id: studentId, status: newStatus })
        });
        const data = await response.json();
        
        if (response.status === 200) {
            showToast(data.message, "success");
            // Reload list to update status
            loadAttendanceList();
        } else {
            showToast(data.message || "Failed to mark attendance", "danger");
        }
    } catch(e) {
        showToast("Error updating attendance", "danger");
    }
}

// 8. Live Map Search & Pin Locator
let activeUsersCache = [];

function filterMapUsers() {
    const query = document.getElementById("mapUserSearch").value.toLowerCase().trim();
    const suggestions = document.getElementById("searchSuggestions");
    suggestions.innerHTML = "";
    
    if (!query) {
        suggestions.classList.add("d-none");
        return;
    }
    
    const matches = activeUsersCache.filter(u => 
        u.username.toLowerCase().includes(query) || 
        String(u.user_id).includes(query) ||
        u.role.toLowerCase().includes(query)
    );
    
    if (matches.length === 0) {
        suggestions.innerHTML = `<div class="p-2 text-muted" style="font-size: 0.8rem;">No active person found</div>`;
        suggestions.classList.remove("d-none");
        return;
    }
    
    suggestions.classList.remove("d-none");
    matches.forEach(usr => {
        const item = document.createElement("div");
        item.className = "p-2 cursor-pointer search-item-hover";
        item.style.fontSize = "0.85rem";
        item.style.borderBottom = "1px solid rgba(255,255,255,0.05)";
        item.style.cursor = "pointer";
        item.innerHTML = `
            <div style="font-weight: 600; color: var(--text-main);">${usr.username.toUpperCase()} (${usr.role})</div>
            <div class="text-muted" style="font-size: 0.75rem;">ID: ${usr.user_id} | Zone: ${usr.geofence_name}</div>
        `;
        item.onclick = () => {
            focusUserOnMap(usr.user_id);
            document.getElementById("mapUserSearch").value = usr.username;
            suggestions.classList.add("d-none");
        };
        suggestions.appendChild(item);
    });
}

function focusUserOnMap(userId) {
    const map = maps["trackingViewMap"] || maps["adminMap"];
    const marker = adminMarkers[userId];
    if (map && marker) {
        map.setView(marker.getLatLng(), 18);
        marker.openPopup();
    } else {
        showToast("Active location marker not found on map.", "warning");
    }
}

// 9. Attendance Reports Download Center
function setDefaultReportDate() {
    const dateInput = document.getElementById('reportDate');
    if (!dateInput.value) {
        const today = new Date();
        dateInput.value = today.toISOString().split('T')[0];
    }
}

async function loadReportSummary() {
    const dateVal = document.getElementById('reportDate').value;
    if (!dateVal) {
        showToast('Please select a report date', 'warning');
        return;
    }

    const summaryCards = document.getElementById('reportSummaryCards');
    const studentTbody = document.getElementById('reportStudentTableBody');
    const staffTbody = document.getElementById('reportStaffTableBody');

    summaryCards.innerHTML = `<div class="col-12 text-center py-3 text-muted"><i class="fa-solid fa-circle-notch fa-spin me-2"></i>Loading report...</div>`;
    studentTbody.innerHTML = `<tr><td colspan="7" class="text-center py-3 text-muted"><i class="fa-solid fa-circle-notch fa-spin me-2"></i>Loading...</td></tr>`;
    staffTbody.innerHTML = `<tr><td colspan="7" class="text-center py-3 text-muted"><i class="fa-solid fa-circle-notch fa-spin me-2"></i>Loading...</td></tr>`;

    try {
        const response = await fetch(`${API_BASE}/attendance/report/summary?date=${dateVal}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await response.json();

        if (response.status === 200 && data.success) {
            renderReportSummaryCards(data);
            renderReportTable(studentTbody, data.students.records);
            renderReportTable(staffTbody, data.staff.records);
        } else {
            summaryCards.innerHTML = `<div class="col-12 text-center py-3 text-danger">${data.message || 'Failed to load report'}</div>`;
        }
    } catch(e) {
        summaryCards.innerHTML = `<div class="col-12 text-center py-3 text-danger">Server connection error</div>`;
    }
}

function renderReportSummaryCards(data) {
    const container = document.getElementById('reportSummaryCards');
    const sSummary = data.students.summary;
    const stSummary = data.staff.summary;

    let cards = [
        { label: 'Total Students', value: sSummary.total, icon: 'fa-user-graduate', color: '#8E44AD' },
        { label: 'Students Present', value: sSummary.present, icon: 'fa-user-check', color: '#27AE60' },
        { label: 'Students Absent', value: sSummary.absent, icon: 'fa-user-xmark', color: '#E74C3C' },
        { label: 'On Duty', value: sSummary.on_duty, icon: 'fa-briefcase', color: '#2980B9' },
        { label: 'On Leave', value: sSummary.on_leave, icon: 'fa-calendar-minus', color: '#F39C12' }
    ];

    if (user.role === 'Admin') {
        cards.push(
            { label: 'Total Staff', value: stSummary.total, icon: 'fa-chalkboard-user', color: '#1ABC9C' },
            { label: 'Staff Present', value: stSummary.present, icon: 'fa-user-check', color: '#2ECC71' },
            { label: 'Staff Absent', value: stSummary.absent, icon: 'fa-user-xmark', color: '#C0392B' }
        );
    }

    container.innerHTML = cards.map(c => `
        <div class="col-xl-3 col-md-4 col-sm-6 mb-3">
            <div class="glass-panel p-3 h-100" style="border-left: 3px solid ${c.color};">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <div class="text-muted" style="font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px;">${c.label}</div>
                        <div style="font-size: 1.8rem; font-weight: 700; color: var(--text-main);">${c.value}</div>
                    </div>
                    <i class="fa-solid ${c.icon}" style="font-size: 1.5rem; color: ${c.color}; opacity: 0.7;"></i>
                </div>
            </div>
        </div>
    `).join('');
}

function renderReportTable(tbody, records) {
    tbody.innerHTML = '';
    if (!records || records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-3 text-muted">No records found for this date</td></tr>`;
        return;
    }

    records.forEach((r, idx) => {
        const statusClass = getStatusBadgeClass(r.status);
        tbody.innerHTML += `
            <tr>
                <td>${idx + 1}</td>
                <td>${r.id}</td>
                <td style="font-weight: 600;">${r.username}</td>
                <td>${r.department}</td>
                <td><span class="badge ${statusClass}">${r.status}</span></td>
                <td>${r.check_in}</td>
                <td>${r.check_out}</td>
            </tr>
        `;
    });
}

function getStatusBadgeClass(status) {
    switch(status) {
        case 'Present': return 'bg-success';
        case 'Absent': return 'bg-danger';
        case 'Late': return 'bg-warning text-dark';
        case 'On Leave': return 'bg-info';
        case 'On Duty': return 'bg-primary';
        default: return 'bg-secondary';
    }
}

async function downloadReport(format, role = '') {
    const dateVal = document.getElementById('reportDate').value;
    if (!dateVal) {
        showToast('Please select a report date first', 'warning');
        return;
    }

    const endpoint = format === 'excel' ? 'excel' : 'pdf';
    let url = `${API_BASE}/attendance/report/download/${endpoint}?date=${dateVal}`;
    if (role) {
        url += `&role=${role}`;
    }

    const label = role ? `${role} ` : 'Full ';
    showToast(`Generating ${label}${format.toUpperCase()} report...`, 'success');

    try {
        const response = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            const errData = await response.json();
            showToast(errData.message || 'Download failed', 'danger');
            return;
        }

        const blob = await response.blob();
        let filename;
        if (role) {
            filename = format === 'excel'
                ? `PEC_${role}_Attendance_${dateVal}.xlsx`
                : `PEC_${role}_Attendance_${dateVal}.pdf`;
        } else {
            filename = format === 'excel'
                ? `PEC_Attendance_${dateVal}.xlsx`
                : `PEC_Attendance_${dateVal}.pdf`;
        }

        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);

        showToast(`${label}${format.toUpperCase()} report downloaded successfully!`, 'success');
    } catch(e) {
        showToast('Error downloading report', 'danger');
    }
}

// 10. User Configuration Directory & Forms
let userDirectoryCache = [];

async function loadUserDirectory() {
    if (activeView !== 'users') return;
    const tbody = document.getElementById("userDirectoryTableBody");
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted"><i class="fa-solid fa-circle-notch fa-spin me-2"></i>Loading directory...</td></tr>`;
    
    try {
        const response = await fetch(`${API_BASE}/auth/users`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json();
        
        if (response.status === 200 && data.users) {
            userDirectoryCache = data.users;
            renderUserDirectoryTable(userDirectoryCache);
        } else {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Failed to load directory.</td></tr>`;
        }
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Server connection error.</td></tr>`;
    }
}

let userDirectorySortField = "username";
let userDirectorySortAsc = true;

function sortDirectory(field) {
    if (userDirectorySortField === field) {
        userDirectorySortAsc = !userDirectorySortAsc;
    } else {
        userDirectorySortField = field;
        userDirectorySortAsc = true;
    }
    filterUserDirectoryTable();
}

function toggleUserYearSection() {
    const roleVal = document.getElementById("manageRole").value;
    const yearSect = document.getElementById("userYearSection");
    if (roleVal === "Student") {
        yearSect.classList.remove("d-none");
    } else {
        yearSect.classList.add("d-none");
        document.getElementById("manageYear").value = "";
        document.getElementById("manageSection").value = "";
    }
}

function renderUserDirectoryTable(users) {
    const tbody = document.getElementById("userDirectoryTableBody");
    tbody.innerHTML = "";
    
    if (users.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4 text-muted">No users matching filter criteria.</td></tr>`;
        return;
    }
    
    users.forEach(u => {
        const yearSectionStr = u.year ? `${u.year} - ${u.section || 'A'}` : '-';
        tbody.innerHTML += `
            <tr>
                <td><b>${u.custom_id || u.id}</b></td>
                <td><b>${u.username}</b></td>
                <td>${u.email}</td>
                <td><span class="badge bg-info">${u.role}</span></td>
                <td>${u.department || '-'}</td>
                <td>${yearSectionStr}</td>
                <td>${u.mobile_no || '-'}</td>
                <td class="text-center">
                    <button class="btn-action-glass btn-sm me-1" onclick="editUserAction(${u.id})">
                        <i class="fa-solid fa-pen-to-square"></i>
                    </button>
                    <button class="btn-action-glass btn-sm text-danger-custom" onclick="deleteUserAction(${u.id})">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </td>
            </tr>
        `;
    });
}

function filterUserDirectoryTable() {
    const textQuery = document.getElementById("userDirectorySearch").value.toLowerCase();
    const catQuery = document.getElementById("filterCategory").value;
    const yearQuery = document.getElementById("filterYear").value;
    const deptQuery = document.getElementById("filterDept").value;
    
    let filtered = userDirectoryCache;
    
    // 1. Text Search filter
    if (textQuery) {
        filtered = filtered.filter(u => 
            u.username.toLowerCase().includes(textQuery) ||
            u.email.toLowerCase().includes(textQuery) ||
            (u.custom_id && u.custom_id.toLowerCase().includes(textQuery)) ||
            (u.mobile_no && u.mobile_no.toLowerCase().includes(textQuery))
        );
    }
    
    // 2. Category filter
    if (catQuery) {
        filtered = filtered.filter(u => u.role === catQuery);
    }
    
    // 3. Year filter
    if (yearQuery) {
        filtered = filtered.filter(u => u.year === yearQuery);
    }
    
    // 4. Department filter
    if (deptQuery) {
        filtered = filtered.filter(u => u.department === deptQuery);
    }
    
    // 5. Apply sorting
    filtered.sort((a, b) => {
        let valA = a[userDirectorySortField] || "";
        let valB = b[userDirectorySortField] || "";
        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();
        
        // Handle numeric-like sorting for custom_id or database IDs
        if (!isNaN(valA) && !isNaN(valB)) {
            valA = Number(valA);
            valB = Number(valB);
        }
        
        if (valA < valB) return userDirectorySortAsc ? -1 : 1;
        if (valA > valB) return userDirectorySortAsc ? 1 : -1;
        return 0;
    });
    
    renderUserDirectoryTable(filtered);
}

function editUserAction(userId) {
    const u = userDirectoryCache.find(x => x.id === userId);
    if (!u) return;
    
    document.getElementById("manageUserId").value = u.id;
    document.getElementById("manageUserCustomId").value = u.custom_id || "";
    document.getElementById("manageUsername").value = u.username;
    document.getElementById("manageEmail").value = u.email;
    document.getElementById("managePassword").value = ""; // Always blank on edit
    document.getElementById("manageRole").value = u.role;
    document.getElementById("manageDept").value = u.department || "CSE";
    document.getElementById("manageUserMobile").value = u.mobile_no || "";
    document.getElementById("manageIsActive").checked = u.is_active;
    
    if (u.role === "Student") {
        document.getElementById("manageYear").value = u.year || "1st Year";
        document.getElementById("manageSection").value = u.section || "A";
    }
    
    toggleUserYearSection();
    
    document.getElementById("userFormTitle").innerHTML = `<i class="fa-solid fa-user-pen me-2" style="color: var(--accent);"></i>Edit User Account`;
    showToast("User details loaded into form card.", "info");
}

function resetUserForm() {
    document.getElementById("manageUserId").value = "";
    document.getElementById("userManageForm").reset();
    toggleUserYearSection();
    document.getElementById("userFormTitle").innerHTML = `<i class="fa-solid fa-user-plus me-2" style="color: var(--accent);"></i>Add User Account`;
}

async function saveUserAccount() {
    const id = document.getElementById("manageUserId").value;
    const customId = document.getElementById("manageUserCustomId").value;
    const username = document.getElementById("manageUsername").value;
    const email = document.getElementById("manageEmail").value;
    const password = document.getElementById("managePassword").value;
    const role = document.getElementById("manageRole").value;
    const year = (role === "Student") ? document.getElementById("manageYear").value : "";
    const section = (role === "Student") ? document.getElementById("manageSection").value : "";
    const dept = document.getElementById("manageDept").value;
    const mobile = document.getElementById("manageUserMobile").value;
    const isActive = document.getElementById("manageIsActive").checked;
    
    const payload = {
        custom_id: customId,
        username: username,
        email: email,
        role: role,
        year: year,
        section: section,
        department_name: dept,
        mobile_no: mobile,
        is_active: isActive
    };
    
    if (password) {
        payload.password = password;
    }
    
    let url = `${API_BASE}/auth/register`;
    let method = "POST";
    
    if (id) {
        url = `${API_BASE}/auth/users/${id}`;
        method = "PUT";
    } else {
        // password is required for new accounts
        if (!password) {
            showToast("Password is required for new accounts.", "warning");
            return;
        }
        payload.password = password;
    }
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        
        if (response.status === 200 || response.status === 201) {
            showToast(data.message || "User account saved successfully.", "success");
            resetUserForm();
            loadUserDirectory();
        } else {
            showToast(data.message || "Failed to save user account.", "danger");
        }
    } catch(e) {
        showToast("Server communication failure.", "danger");
    }
}

async function deleteUserAction(userId) {
    if (!confirm("Are you sure you want to permanently delete this user? All locations, logs, attendance, notifications, and emergency SOS records linked to this account will be cleaned up.")) return;
    
    try {
        const response = await fetch(`${API_BASE}/auth/users/${userId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json();
        
        if (response.status === 200) {
            showToast(data.message || "User deleted successfully.", "success");
            loadUserDirectory();
        } else {
            showToast(data.message || "Failed to delete user.", "danger");
        }
    } catch(e) {
        showToast("Server communication failure.", "danger");
    }
}

// 11. Bus Fleet Configuration & Driver Assignment
let busConfigCache = [];

async function loadBusConfig() {
    if (activeView !== 'buses') return; // switchBusSubView sets activeView='buses'
    const tbody = document.getElementById("busConfigTableBody");
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted"><i class="fa-solid fa-circle-notch fa-spin me-2"></i>Loading fleet...</td></tr>`;
    
    try {
        // 1. Fetch available drivers to populate form dropdown
        const usersResponse = await fetch(`${API_BASE}/auth/users`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const usersData = await usersResponse.json();
        const driverSelect = document.getElementById("manageBusDriver");
        driverSelect.innerHTML = `<option value="">Unassigned / Custom</option>`;
        
        if (usersResponse.status === 200 && usersData.users) {
            const drivers = usersData.users.filter(u => u.role === 'Driver');
            drivers.forEach(d => {
                driverSelect.innerHTML += `<option value="${d.username}">${d.username}</option>`;
            });
        }
        
        // 2. Fetch fleet list
        const response = await fetch(`${API_BASE}/bus/status`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json();
        
        if (response.status === 200 && data.buses) {
            busConfigCache = data.buses;
            renderBusConfigTable(busConfigCache);
        } else {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Failed to load bus fleet config.</td></tr>`;
        }
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger">Server connection error.</td></tr>`;
    }
}

function renderBusConfigTable(buses) {
    const tbody = document.getElementById("busConfigTableBody");
    tbody.innerHTML = "";
    
    if (buses.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">No buses registered. Add one using the form.</td></tr>`;
        return;
    }
    
    buses.forEach(b => {
        tbody.innerHTML += `
            <tr>
                <td><b>${b.bus_number}</b></td>
                <td>${b.route_number || '-'}</td>
                <td>${b.driver_name || '-'}</td>
                <td>${b.driver_phone || '-'}</td>
                <td>${b.start_location || '-'}</td>
                <td style="font-size: 0.75rem;">${b.stops || '-'}</td>
                <td class="text-center">
                    <button class="btn-action-glass btn-sm me-1" onclick="editBusAction(${b.id})">
                        <i class="fa-solid fa-pen-to-square"></i>
                    </button>
                    <button class="btn-action-glass btn-sm text-danger-custom" onclick="deleteBusAction(${b.id})">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </td>
            </tr>
        `;
    });
}

function editBusAction(busId) {
    const b = busConfigCache.find(x => x.id === busId);
    if (!b) return;
    
    document.getElementById("manageBusId").value = b.id;
    document.getElementById("manageBusNumber").value = b.bus_number;
    document.getElementById("manageBusRoute").value = b.route_number || "";
    document.getElementById("manageBusDriver").value = b.driver_name || "";
    document.getElementById("manageBusDriverPhone").value = b.driver_phone || "";
    document.getElementById("manageBusStart").value = b.start_location || "Poonamallee Junction";
    document.getElementById("manageBusStops").value = b.stops || "";
    
    document.getElementById("busFormTitle").innerHTML = `<i class="fa-solid fa-pen-to-square me-2" style="color: var(--accent);"></i>Edit Bus Registry`;
    showToast("Bus registry loaded into form card.", "info");
}

function resetBusForm() {
    document.getElementById("manageBusId").value = "";
    document.getElementById("busManageForm").reset();
    document.getElementById("busFormTitle").innerHTML = `<i class="fa-solid fa-circle-plus me-2" style="color: var(--accent);"></i>Add Bus Registry`;
}

async function saveBusConfig() {
    const id = document.getElementById("manageBusId").value;
    const busNum = document.getElementById("manageBusNumber").value;
    const routeNum = document.getElementById("manageBusRoute").value;
    const driverName = document.getElementById("manageBusDriver").value;
    const driverPhone = document.getElementById("manageBusDriverPhone").value;
    const startLoc = document.getElementById("manageBusStart").value;
    const stops = document.getElementById("manageBusStops").value;
    
    const payload = {
        bus_number: busNum,
        route_number: routeNum,
        driver_name: driverName,
        driver_phone: driverPhone,
        start_location: startLoc,
        stops: stops
    };
    
    let url = `${API_BASE}/bus/add`;
    let method = "POST";
    
    if (id) {
        url = `${API_BASE}/bus/edit/${id}`;
        method = "PUT";
    }
    
    try {
        const response = await fetch(url, {
            method: method,
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        
        if (response.status === 200 || response.status === 201) {
            showToast(data.message || "Bus saved successfully.", "success");
            resetBusForm();
            loadBusConfig();
        } else {
            showToast(data.message || "Failed to save bus.", "danger");
        }
    } catch(e) {
        showToast("Server communication failure.", "danger");
    }
}

async function deleteBusAction(busId) {
    if (!confirm("Are you sure you want to permanently delete this bus registry? Active trip telemetries linked to this bus will be deleted.")) return;
    
    try {
        const response = await fetch(`${API_BASE}/bus/delete/${busId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json();
        
        if (response.status === 200) {
            showToast(data.message || "Bus deleted successfully.", "success");
            loadBusConfig();
        } else {
            showToast(data.message || "Failed to delete bus.", "danger");
        }
    } catch(e) {
        showToast("Server communication failure.", "danger");
    }
}

// 12. Nested Layout Sub-view Switchers
function switchBusSubView(subView) {
    const btnTracker = document.getElementById("btnBusTabTracker");
    const btnManage = document.getElementById("btnBusTabManage");
    const viewTracker = document.getElementById("busSubViewTracker");
    const viewManage = document.getElementById("busSubViewManage");
    
    if (btnTracker) btnTracker.classList.remove("active");
    if (btnManage) btnManage.classList.remove("active");
    if (viewTracker) {
        viewTracker.classList.add("d-none");
        viewTracker.classList.remove("active");
    }
    if (viewManage) {
        viewManage.classList.add("d-none");
        viewManage.classList.remove("active");
    }
    
    if (subView === 'tracker') {
        if (btnTracker) btnTracker.classList.add("active");
        if (viewTracker) {
            viewTracker.classList.remove("d-none");
            viewTracker.classList.add("active");
        }
        setTimeout(() => {
            if (maps["busMap"]) maps["busMap"].invalidateSize();
        }, 100);
    } else {
        if (btnManage) btnManage.classList.add("active");
        if (viewManage) {
            viewManage.classList.remove("d-none");
            viewManage.classList.add("active");
        }
        loadBusConfig();
    }
}

function switchAttSubView(subView) {
    const btnTake = document.getElementById("btnAttTabTake");
    const btnReports = document.getElementById("btnAttTabReports");
    const viewTake = document.getElementById("attSubViewTake");
    const viewReports = document.getElementById("attSubViewReports");
    
    if (btnTake) btnTake.classList.remove("active");
    if (btnReports) btnReports.classList.remove("active");
    if (viewTake) {
        viewTake.classList.add("d-none");
        viewTake.classList.remove("active");
    }
    if (viewReports) {
        viewReports.classList.add("d-none");
        viewReports.classList.remove("active");
    }
    
    if (subView === 'take') {
        if (btnTake) btnTake.classList.add("active");
        if (viewTake) {
            viewTake.classList.remove("d-none");
            viewTake.classList.add("active");
        }
        loadAttendanceList();
    } else {
        if (btnReports) btnReports.classList.add("active");
        if (viewReports) {
            viewReports.classList.remove("d-none");
            viewReports.classList.add("active");
        }
        setDefaultReportDate();
        loadReportSummary();
    }
}
