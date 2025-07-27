let qrCodeGenerated = false;

function showSettings() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) {
        alert('Please select a file first');
        return;
    }
    document.getElementById('settingsModal').style.display = 'flex';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

function showError(message) {
    const errorModal = document.getElementById('errorModal');
    document.getElementById('errorTextModal').textContent = message;
    errorModal.style.display = 'flex';
}

function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const password = document.getElementById('passwordInput').value;
    const days = document.getElementById('daysInput').value;
    
    if (!days) {
        alert('Please select storage duration');
        return;
    }
    
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('password', password);
    formData.append('days', days);
    
    closeModal('settingsModal');
    const progressModal = document.getElementById('progressModal');
    progressModal.style.display = 'flex';
    
    document.getElementById('fileName').textContent = file.name;
    
    const xhr = new XMLHttpRequest();
    let startTime = Date.now();
    let totalProgress = 0;
    const uploadWeight = 0.6; // 60% веса для загрузки, 40% для симуляции шифрования
    
    xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const uploadPercent = (e.loaded / e.total) * 100;
            const elapsedTime = (Date.now() - startTime) / 1000;
            const speed = e.loaded / elapsedTime;
            const speedText = speed > 1024 * 1024 
                ? `${(speed / (1024 * 1024)).toFixed(2)} MB/s`
                : `${(speed / 1024).toFixed(2)} KB/s`;
            
            // Комбинированный прогресс: 60% загрузка + 40% симуляция шифрования
            totalProgress = (uploadPercent * uploadWeight) + (Math.min((elapsedTime / 5) * 100 * (1 - uploadWeight), 100 * (1 - uploadWeight)));
            document.getElementById('progressBar').value = totalProgress;
            document.getElementById('progressText').textContent = `${Math.round(totalProgress)}%`;
            document.getElementById('speedText').textContent = speedText;
        }
    });
    
    xhr.startTime = Date.now();
    xhr.open('POST', '/upload', true);
    xhr.onload = () => {
        closeModal('progressModal');
        if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText);
            const resultModal = document.getElementById('resultModal');
            document.getElementById('downloadLink').href = response.url;
            document.getElementById('downloadLink').textContent = `Ссылка для скачивания: ${response.url}`;
            
            if (!qrCodeGenerated) {
                new QRCode(document.getElementById('qrCode'), {
                    text: response.url,
                    width: 200,
                    height: 200
                });
                qrCodeGenerated = true;
            }
            
            resultModal.style.display = 'flex';
        } else {
            const error = JSON.parse(xhr.responseText).error;
            showError(error);
        }
    };
    
    xhr.send(formData);
}

function downloadFile(fileId) {
    const password = document.getElementById('downloadPassword') ? document.getElementById('downloadPassword').value : '';
    const downloadModal = document.getElementById('downloadModal');
    downloadModal.style.display = 'flex';

    // Симуляция комбинированного процесса
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const speedText = document.getElementById('speedText');
    let startTime = Date.now();
    const totalTime = 3; // Общее время симуляции (3 секунды)
    const interval = setInterval(() => {
        const elapsedTime = (Date.now() - startTime) / 1000;
        const percent = Math.min((elapsedTime / totalTime) * 100, 100);
        progressBar.value = percent;
        progressText.textContent = `${Math.round(percent)}%`;

        const speed = (percent / 100) * 1024 * 1024 / (elapsedTime || 1); // Симуляция скорости
        speedText.textContent = speed > 1024 * 1024 
            ? `${(speed / (1024 * 1024)).toFixed(2)} MB/s`
            : `${(speed / 1024).toFixed(2)} KB/s`;

        if (percent >= 100) {
            clearInterval(interval);
            startDownload(fileId, password);
        }
    }, 100);
}

function startDownload(fileId, password) {
    const xhr = new XMLHttpRequest();
    xhr.responseType = 'blob';
    xhr.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
            const percent = (e.loaded / e.total) * 100;
            document.getElementById('progressBar').value = percent;
            document.getElementById('progressText').textContent = `${Math.round(percent)}%`;
            
            const speed = e.loaded / ((new Date().getTime() - xhr.startTime) / 1000);
            const speedText = speed > 1024 * 1024 
                ? `${(speed / (1024 * 1024)).toFixed(2)} MB/s`
                : `${(speed / 1024).toFixed(2)} KB/s`;
            document.getElementById('speedText').textContent = speedText;
        }
    });

    xhr.startTime = Date.now();
    xhr.open('POST', `/download/${fileId}/file`, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onload = () => {
        if (xhr.status === 200) {
            const blob = xhr.response;
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = document.getElementById('filename').textContent || 'file';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            closeModal('downloadModal');
        } else {
            const error = JSON.parse(xhr.responseText).error;
            showError(error);
            closeModal('downloadModal');
        }
    };
    xhr.send(JSON.stringify({ password: password }));
}