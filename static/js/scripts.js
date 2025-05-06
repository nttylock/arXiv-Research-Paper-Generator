// General scripts for the application

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // File upload validation
    const fileInput = document.getElementById('file');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            const fileSize = this.files[0].size / 1024 / 1024; // in MB
            const fileType = this.files[0].name.split('.').pop().toLowerCase();
            
            const allowedTypes = ['txt', 'pdf', 'docx', 'md'];
            const maxSize = 16; // MB
            
            if (!allowedTypes.includes(fileType)) {
                alert('Invalid file type. Please upload TXT, PDF, DOCX, or MD files only.');
                this.value = '';
                return;
            }
            
            if (fileSize > maxSize) {
                alert(`File size exceeds ${maxSize}MB limit. Please upload a smaller file.`);
                this.value = '';
                return;
            }
        });
    }
});