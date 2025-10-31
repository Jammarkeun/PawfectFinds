// Rider Dashboard JavaScript

// Variables set by Jinja2 template
let csrfTokenValue = window.csrfTokenValue;
let updateStatusUrl = window.updateStatusUrl;

// Filter deliveries by status
function filterDeliveries() {
    const filter = document.getElementById('statusFilter').value.toLowerCase();
    const rows = document.querySelectorAll('.delivery-row');

    rows.forEach(function(row) {
        const status = row.getAttribute('data-status').toLowerCase();
        if (filter === '' || status === filter) {
            row.style.display = 'table-row';
        } else {
            row.style.display = 'none';
        }
    });
}

// View delivery details
function viewDeliveryDetail(deliveryId) {
    const modal = new bootstrap.Modal(document.getElementById('deliveryDetailModal'));
    const content = document.getElementById('deliveryDetailContent');

    content.innerHTML = '<div class="text-center py-4"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div><p class="mt-2">Loading delivery details...</p></div>';

    modal.show();

    fetch('/rider/delivery/' + deliveryId + '/details')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            content.innerHTML = data.html;
        })
        .catch(function(error) {
            content.innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> Error loading delivery details. Please try again.</div>';
        });
}

// Update delivery status
function updateDeliveryStatus(deliveryId, status) {
    if (!confirm('Are you sure you want to mark this delivery as ' + status + '?')) {
        return;
    }

    const form = document.createElement('form');
    form.method = 'POST';
    form.action = updateStatusUrl;

    const csrfToken = document.createElement('input');
    csrfToken.type = 'hidden';
    csrfToken.name = 'csrf_token';
    csrfToken.value = csrfTokenValue;
    form.appendChild(csrfToken);

    const deliveryIdInput = document.createElement('input');
    deliveryIdInput.type = 'hidden';
    deliveryIdInput.name = 'delivery_id';
    deliveryIdInput.value = deliveryId;
    form.appendChild(deliveryIdInput);

    const statusInput = document.createElement('input');
    statusInput.type = 'hidden';
    statusInput.name = 'status';
    statusInput.value = status;
    form.appendChild(statusInput);

    document.body.appendChild(form);
    form.submit();
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // View delivery detail buttons
    document.querySelectorAll('.view-delivery-detail').forEach(function(button) {
        button.addEventListener('click', function() {
            const deliveryId = this.getAttribute('data-delivery-id');
            viewDeliveryDetail(deliveryId);
        });
    });

    // Update delivery status buttons
    document.querySelectorAll('.update-delivery-status').forEach(function(button) {
        button.addEventListener('click', function() {
            const deliveryId = this.getAttribute('data-delivery-id');
            const status = this.getAttribute('data-status');
            updateDeliveryStatus(deliveryId, status);
        });
    });
});
