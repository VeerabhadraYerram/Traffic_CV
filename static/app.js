document.addEventListener('DOMContentLoaded', () => {
    const cameraSelect = document.getElementById('camera-select');
    const canvas = document.getElementById('video-canvas');
    const ctx = canvas.getContext('2d');
    
    const btnDrawEntry = document.getElementById('btn-draw-entry');
    const btnDrawExit = document.getElementById('btn-draw-exit');
    const btnSave = document.getElementById('btn-save');
    const toast = document.getElementById('toast');
    
    let currentImage = null;
    let cameras = [];
    let currentCameraId = null;
    
    let entryLine = null; // {x1, y1, x2, y2} normalized
    let exitLine = null;  // {x1, y1, x2, y2} normalized
    
    let currentTool = null; // 'entry' or 'exit'
    let drawingState = 0; // 0: idle, 1: drawing point 1
    let tempPoint = null;
    
    // Load Cameras
    fetch('/api/cameras')
        .then(r => r.json())
        .then(data => {
            cameras = data;
            cameraSelect.innerHTML = '<option value="">-- Select a Camera --</option>';
            data.forEach(cam => {
                const opt = document.createElement('option');
                opt.value = cam.id;
                opt.textContent = `${cam.name} (${cam.role})`;
                cameraSelect.appendChild(opt);
            });
        });
        
    cameraSelect.addEventListener('change', (e) => {
        currentCameraId = e.target.value;
        if (!currentCameraId) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            return;
        }
        
        const cam = cameras.find(c => c.id === currentCameraId);
        entryLine = cam.entry_line ? {...cam.entry_line} : null;
        exitLine = cam.exit_line ? {...cam.exit_line} : null;
        
        loadImage(currentCameraId);
    });
    
    function loadImage(camId) {
        const img = new Image();
        img.onload = () => {
            currentImage = img;
            canvas.width = img.width;
            canvas.height = img.height;
            redraw();
        };
        img.src = `/api/cameras/${camId}/frame?t=${new Date().getTime()}`;
    }
    
    function redraw() {
        if (!currentImage) return;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(currentImage, 0, 0, canvas.width, canvas.height);
        
        // Draw Entry Line
        if (entryLine) {
            drawLine(
                entryLine.x1 * canvas.width, entryLine.y1 * canvas.height,
                entryLine.x2 * canvas.width, entryLine.y2 * canvas.height,
                '#22c55e'
            );
        }
        
        // Draw Exit Line
        if (exitLine) {
            drawLine(
                exitLine.x1 * canvas.width, exitLine.y1 * canvas.height,
                exitLine.x2 * canvas.width, exitLine.y2 * canvas.height,
                '#ef4444'
            );
        }
    }
    
    function drawLine(x1, y1, x2, y2, color) {
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.strokeStyle = color;
        ctx.lineWidth = 4;
        ctx.stroke();
        
        // Draw endpoints
        ctx.beginPath();
        ctx.arc(x1, y1, 6, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        
        ctx.beginPath();
        ctx.arc(x2, y2, 6, 0, Math.PI * 2);
        ctx.fill();
    }
    
    // Tools
    btnDrawEntry.addEventListener('click', () => {
        currentTool = 'entry';
        drawingState = 0;
        btnDrawEntry.classList.add('active-entry');
        btnDrawExit.classList.remove('active-exit');
    });
    
    btnDrawExit.addEventListener('click', () => {
        currentTool = 'exit';
        drawingState = 0;
        btnDrawEntry.classList.remove('active-entry');
        btnDrawExit.classList.add('active-exit');
    });
    
    // Mouse Interaction
    canvas.addEventListener('mousedown', (e) => {
        if (!currentTool || !currentImage) return;
        
        const rect = canvas.getBoundingClientRect();
        
        // Calculate scale factors because canvas is scaled via CSS object-fit
        // Wait, object-fit is not used on canvas directly if width/height are set.
        // Actually, object-fit: contain scales the canvas element.
        // We need to calculate the actual display size vs intrinsic size.
        
        const displayRatio = rect.width / rect.height;
        const intrinsicRatio = canvas.width / canvas.height;
        
        let drawWidth, drawHeight, offsetX = 0, offsetY = 0;
        
        if (displayRatio > intrinsicRatio) {
            // Letterboxed on sides
            drawHeight = rect.height;
            drawWidth = rect.height * intrinsicRatio;
            offsetX = (rect.width - drawWidth) / 2;
        } else {
            // Letterboxed top/bottom
            drawWidth = rect.width;
            drawHeight = rect.width / intrinsicRatio;
            offsetY = (rect.height - drawHeight) / 2;
        }
        
        // Adjust mouse coordinates
        let mouseX = e.clientX - rect.left - offsetX;
        let mouseY = e.clientY - rect.top - offsetY;
        
        // Normalize
        let normX = mouseX / drawWidth;
        let normY = mouseY / drawHeight;
        
        // Clamp to 0-1
        normX = Math.max(0, Math.min(1, normX));
        normY = Math.max(0, Math.min(1, normY));
        
        if (drawingState === 0) {
            tempPoint = { x: normX, y: normY };
            drawingState = 1;
        } else {
            if (currentTool === 'entry') {
                entryLine = { x1: tempPoint.x, y1: tempPoint.y, x2: normX, y2: normY };
            } else {
                exitLine = { x1: tempPoint.x, y1: tempPoint.y, x2: normX, y2: normY };
            }
            drawingState = 0;
            currentTool = null;
            btnDrawEntry.classList.remove('active-entry');
            btnDrawExit.classList.remove('active-exit');
            redraw();
        }
    });
    
    canvas.addEventListener('mousemove', (e) => {
        if (drawingState === 1 && tempPoint) {
            const rect = canvas.getBoundingClientRect();
            
            const displayRatio = rect.width / rect.height;
            const intrinsicRatio = canvas.width / canvas.height;
            
            let drawWidth, drawHeight, offsetX = 0, offsetY = 0;
            
            if (displayRatio > intrinsicRatio) {
                drawHeight = rect.height;
                drawWidth = rect.height * intrinsicRatio;
                offsetX = (rect.width - drawWidth) / 2;
            } else {
                drawWidth = rect.width;
                drawHeight = rect.width / intrinsicRatio;
                offsetY = (rect.height - drawHeight) / 2;
            }
            
            let mouseX = e.clientX - rect.left - offsetX;
            let mouseY = e.clientY - rect.top - offsetY;
            
            let normX = mouseX / drawWidth;
            let normY = mouseY / drawHeight;
            
            redraw();
            
            const color = currentTool === 'entry' ? '#22c55e' : '#ef4444';
            drawLine(
                tempPoint.x * canvas.width, tempPoint.y * canvas.height,
                normX * canvas.width, normY * canvas.height,
                color
            );
        }
    });
    
    // Save
    btnSave.addEventListener('click', () => {
        if (!currentCameraId) return;
        
        const payload = {
            entry_line: entryLine,
            exit_line: exitLine
        };
        
        btnSave.textContent = 'Saving...';
        
        fetch(`/api/cameras/${currentCameraId}/lines`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(r => r.json())
        .then(() => {
            btnSave.textContent = 'Save Configuration';
            
            // Show toast
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
            
            // Update local camera data
            const cam = cameras.find(c => c.id === currentCameraId);
            cam.entry_line = entryLine;
            cam.exit_line = exitLine;
        })
        .catch(err => {
            console.error(err);
            btnSave.textContent = 'Save Configuration';
            alert('Error saving configuration');
        });
    });
});
