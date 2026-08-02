import os

js_path = r"c:\Users\HP\Desktop\Smart Campus Management System\frontend\js\app.js"

with open(js_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Simplify sidebar roles menu toggling inside initSession
old_init_toggles = """    const alertsMenuItem = document.getElementById("menu-alerts");
    if (['Admin', 'Security'].includes(user.role)) {
        alertsMenuItem.classList.remove("d-none");
    } else {
        alertsMenuItem.classList.add("d-none");
    }
    
    const attendanceMenuItem = document.getElementById("menu-attendance");
    if (['Admin', 'Staff'].includes(user.role)) {
        attendanceMenuItem.classList.remove("d-none");
    } else {
        attendanceMenuItem.classList.add("d-none");
    }
    
    const reportsMenuItem = document.getElementById("menu-reports");
    const usersMenuItem = document.getElementById("menu-users");
    const busesConfigMenuItem = document.getElementById("menu-buses-config");
    if (user.role === 'Admin') {
        if (reportsMenuItem) reportsMenuItem.classList.remove("d-none");
        if (usersMenuItem) usersMenuItem.classList.remove("d-none");
        if (busesConfigMenuItem) busesConfigMenuItem.classList.remove("d-none");
    } else {
        if (reportsMenuItem) reportsMenuItem.classList.add("d-none");
        if (usersMenuItem) usersMenuItem.classList.add("d-none");
        if (busesConfigMenuItem) busesConfigMenuItem.classList.add("d-none");
    }"""

# Alerts, Reports, and Buses-config menu list items are deleted or merged, only User Management is separate Admin page.
# Attendance center is visible to Staff and Admin.
new_init_toggles = """    const attendanceMenuItem = document.getElementById("menu-attendance");
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
    }"""

content = content.replace(old_init_toggles, new_init_toggles)

# 2. Modify switchView header titles and refresh logic
old_titles = """    const titles = {
        "home": "Dashboard Overview",
        "tracking": "Live Interactive Campus Map",
        "leaves": "Leave Request & Workflow Log",
        "buses": "Bus Route Location Tracker",
        "alerts": "Security Alerts Feed",
        "attendance": "Student Attendance Records",
        "reports": "Attendance Reports Download",
        "users": "User Accounts Directory & Admin Configuration",
        "buses-config": "Manage Bus Fleet & Routes"
    };"""

new_titles = """    const titles = {
        "home": "Dashboard Overview",
        "tracking": "Live Interactive Campus Map & Alerts",
        "leaves": "Leave Request & Workflow Log",
        "buses": "Bus Transit & Fleet Center",
        "attendance": "Unified Attendance Center",
        "users": "User Directory & Configuration"
    };"""

content = content.replace(old_titles, new_titles)

old_switch_loads = """        // Refresh specific view feeds
        if (viewName === 'leaves') loadLeaveData();
        if (viewName === 'buses') loadBusData();
        if (viewName === 'alerts') loadSecurityAlerts();
        if (viewName === 'tracking') refreshCampusTrackViewMap();
        if (viewName === 'attendance') loadAttendanceList();
        if (viewName === 'reports') { setDefaultReportDate(); loadReportSummary(); }
        if (viewName === 'users') loadUserDirectory();
        if (viewName === 'buses-config') loadBusConfig();"""

new_switch_loads = """        // Refresh specific view feeds
        if (viewName === 'leaves') loadLeaveData();
        if (viewName === 'buses') { switchBusSubView('tracker'); loadBusData(); }
        if (viewName === 'tracking') { refreshCampusTrackViewMap(); loadSecurityAlerts(); }
        if (viewName === 'attendance') { switchAttSubView('take'); }
        if (viewName === 'users') loadUserDirectory();"""

content = content.replace(old_switch_loads, new_switch_loads)

# 3. Modify setupViewsByRole to configure tracking layouts, sub-view tabs, and menu permissions dynamically
old_setup_role = """    if (user.role === 'Admin') {
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
    }"""

new_setup_role = """    // Adjust live map layout for non-alert monitoring roles
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
    if (user.role === 'Admin') {
        if (attTabReports) attTabReports.classList.remove("d-none");
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
    }"""

content = content.replace(old_setup_role, new_setup_role)

# 4. Append Sub-View Switchers at the end of the file
subview_switchers = """
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
"""

content = content + subview_switchers

with open(js_path, "w", encoding="utf-8") as f:
    f.write(content)

print("app.js logic updated successfully with grouped nested routing!")
