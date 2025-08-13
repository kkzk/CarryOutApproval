// カンバンボードのJavaScript機能

// WebSocket接続
let websocket = null;

document.addEventListener('DOMContentLoaded', function() {
    initializeSortable();
    setupHTMXEvents();
    initializeWebSocket();
});

// WebSocket接続を初期化
function initializeWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/notifications/`;
    
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = function(event) {
        console.log('WebSocket接続が確立されました');
    };
    
    websocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
    
    websocket.onclose = function(event) {
        console.log('WebSocket接続が閉じられました');
        // 5秒後に再接続を試行
        setTimeout(initializeWebSocket, 5000);
    };
    
    websocket.onerror = function(error) {
        console.error('WebSocketエラー:', error);
    };
}

// WebSocketメッセージの処理
function handleWebSocketMessage(data) {
    if (data.type === 'notification') {
        showToast(data.data.title, 'info');
    } else if (data.type === 'kanban_update') {
        handleKanbanUpdate(data);
    }
}

// カンバンボード更新の処理
function handleKanbanUpdate(data) {
    const { action, application } = data;
    
    switch (action) {
        case 'new_application':
            addApplicationCard(application, 'pending');
            showToast(`新しい申請「${application.original_filename}」が追加されました`, 'info');
            break;
        case 'application_approved':
            moveApplicationCard(application.id, 'approved');
            // 申請者と承認者で異なるメッセージ
            if (isApplicantView()) {
                showApprovalNotification(application);
            } else {
                showToast(`申請「${application.original_filename}」が承認されました`, 'success');
            }
            break;
        case 'application_rejected':
            moveApplicationCard(application.id, 'rejected');
            // 申請者と承認者で異なるメッセージ
            if (isApplicantView()) {
                showRejectionNotification(application);
            } else {
                showToast(`申請「${application.original_filename}」が却下されました`, 'warning');
            }
            break;
    }
    
    updateColumnCounts();
}

// 申請者視点かどうかを判定
function isApplicantView() {
    // より確実な判定方法
    const pageTitle = document.querySelector('h2')?.textContent || '';
    const bodyContent = document.body.innerHTML;
    
    // 申請者として、申請状況ボード、申請中 の文字列で判定
    const isApplicant = pageTitle.includes('申請状況ボード') || 
                        pageTitle.includes('申請者として') || 
                        bodyContent.includes('申請中 (') ||
                        window.location.pathname.includes('/my/board/');
    
    console.log('isApplicantView判定:', {
        pageTitle: pageTitle,
        isApplicant: isApplicant,
        pathname: window.location.pathname
    });
    
    return isApplicant;
}

// 申請承認時の特別な通知
function showApprovalNotification(application) {
    // 大きなモーダル通知
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-success">
                <div class="modal-header bg-success text-white">
                    <h5 class="modal-title">
                        <i class="bi bi-check-circle-fill me-2"></i>申請が承認されました！
                    </h5>
                </div>
                <div class="modal-body text-center">
                    <div class="mb-3">
                        <i class="bi bi-check-circle text-success" style="font-size: 4rem;"></i>
                    </div>
                    <h5 class="text-success mb-3">おめでとうございます！</h5>
                    <p class="mb-2">
                        <strong>申請ファイル：</strong>${application.original_filename}
                    </p>
                    <p class="text-muted">
                        承認者によって正式に承認されました。
                    </p>
                </div>
                <div class="modal-footer justify-content-center">
                    <button type="button" class="btn btn-success" data-bs-dismiss="modal">
                        <i class="bi bi-check me-1"></i>確認
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // モーダルが閉じられたら要素を削除
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    });
    
    // 通常のトーストも表示
    showToast(`申請「${application.original_filename}」が承認されました！`, 'success');
}

// 申請却下時の特別な通知
function showRejectionNotification(application) {
    // 情報提供モーダル
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-warning">
                <div class="modal-header bg-warning text-dark">
                    <h5 class="modal-title">
                        <i class="bi bi-exclamation-triangle-fill me-2"></i>申請について
                    </h5>
                </div>
                <div class="modal-body text-center">
                    <div class="mb-3">
                        <i class="bi bi-x-circle text-warning" style="font-size: 4rem;"></i>
                    </div>
                    <p class="mb-2">
                        <strong>申請ファイル：</strong>${application.original_filename}
                    </p>
                    <p class="text-muted">
                        承認者によって却下されました。<br>
                        詳細については承認者にご確認ください。
                    </p>
                </div>
                <div class="modal-footer justify-content-center">
                    <button type="button" class="btn btn-primary" data-bs-dismiss="modal">
                        <i class="bi bi-check me-1"></i>確認
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // モーダルが閉じられたら要素を削除
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    });
    
    // 通常のトーストも表示
    showToast(`申請「${application.original_filename}」が却下されました`, 'warning');
}

// 申請カードを追加
function addApplicationCard(application, status) {
    const column = document.getElementById(`${status}-column`);
    if (!column) return;
    
    // 既存のカードが存在するかチェック
    const existingCard = column.querySelector(`[data-id="${application.id}"]`);
    if (existingCard) return;
    
    // カードHTMLを生成してサーバーから取得
    fetch(`/applications/${application.id}/card/`)
        .then(response => response.text())
        .then(html => {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = html;
            const cardElement = tempDiv.firstElementChild;
            
            // カラムの先頭に追加
            column.insertBefore(cardElement, column.firstChild);
            
            // アニメーション効果
            cardElement.style.opacity = '0';
            cardElement.style.transform = 'translateY(-20px)';
            setTimeout(() => {
                cardElement.style.transition = 'all 0.3s ease';
                cardElement.style.opacity = '1';
                cardElement.style.transform = 'translateY(0)';
            }, 100);
        })
        .catch(error => {
            console.error('カード読み込みエラー:', error);
        });
}

// 申請カードを移動
function moveApplicationCard(applicationId, newStatus) {
    const currentCard = document.querySelector(`[data-id="${applicationId}"]`);
    if (!currentCard) return;
    
    const targetColumn = document.getElementById(`${newStatus}-column`);
    if (!targetColumn) return;
    
    // アニメーション効果付きで移動
    currentCard.style.transition = 'all 0.3s ease';
    currentCard.style.opacity = '0.5';
    
    setTimeout(() => {
        targetColumn.appendChild(currentCard);
        currentCard.style.opacity = '1';
        
        // ステータスの更新
        currentCard.dataset.status = newStatus;
    }, 150);
}

// Sortable.jsでドラッグ&ドロップを初期化
function initializeSortable() {
    const columns = document.querySelectorAll('.kanban-body');
    const isApplicant = isApplicantView();
    
    console.log('Sortable初期化:', { isApplicant: isApplicant, columnCount: columns.length });
    
    columns.forEach((column, index) => {
        const sortableOptions = {
            group: 'kanban-cards',
            animation: 150,
            ghostClass: 'sortable-ghost',
            chosenClass: 'sortable-chosen',
            dragClass: 'sortable-drag',
            
            onStart: function(evt) {
                console.log('ドラッグ開始:', evt.item.dataset.id);
                evt.item.style.transform = 'rotate(5deg)';
                evt.item.style.cursor = 'grabbing';
            },
            
            onEnd: function(evt) {
                console.log('ドラッグ終了:', {
                    itemId: evt.item.dataset.id,
                    fromColumn: evt.from.dataset.status,
                    toColumn: evt.to.dataset.status,
                    moved: evt.from !== evt.to
                });
                
                evt.item.style.transform = '';
                evt.item.style.cursor = 'grab';
                
                // カードが移動した場合の処理
                if (evt.from !== evt.to) {
                    const applicationId = evt.item.dataset.id;
                    const newStatus = evt.to.dataset.status;
                    
                    updateApplicationStatus(applicationId, newStatus, evt.item);
                }
            }
        };
        
        // 申請者視点の場合はドラッグを無効にする
        if (isApplicant) {
            sortableOptions.disabled = true;
            console.log('申請者視点: ドラッグ無効');
            
            // カードにツールチップを追加
            column.querySelectorAll('.application-card').forEach(card => {
                card.setAttribute('title', 'ステータスは承認者によって変更されます');
                card.style.cursor = 'pointer'; // 詳細表示は可能
            });
        } else {
            console.log('承認者視点: ドラッグ有効');
        }
        
        const sortableInstance = new Sortable(column, sortableOptions);
        console.log(`カラム${index + 1} Sortable作成完了:`, { disabled: sortableOptions.disabled });
    });
}

// HTMXイベントの設定
function setupHTMXEvents() {
    document.body.addEventListener('htmx:configRequest', function(evt) {
        // CSRFトークンを自動追加
        evt.detail.headers['X-CSRFToken'] = getCSRFToken();
    });
    
    document.body.addEventListener('htmx:responseError', function(evt) {
        console.error('HTMX Error:', evt.detail);
        showToast('エラーが発生しました', 'error');
    });
    
    document.body.addEventListener('htmx:afterSwap', function(evt) {
        // モーダル内容が更新された後の処理
        if (evt.target.id === 'modal-content') {
            // 必要に応じて追加処理
        }
    });
}

// 申請ステータスを更新
function updateApplicationStatus(applicationId, newStatus, cardElement) {
    console.log('ステータス更新開始:', { applicationId, newStatus });
    
    const formData = new FormData();
    formData.append('application_id', applicationId);
    formData.append('status', newStatus);
    formData.append('csrfmiddlewaretoken', getCSRFToken());
    
    fetch('/applications/update-status/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
        }
    })
    .then(response => {
        console.log('サーバーレスポンス:', response.status);
        if (response.ok) {
            return response.text();
        } else {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
    })
    .then(html => {
        console.log('ステータス更新成功');
        // カードの内容を更新
        cardElement.outerHTML = html;
        showToast('ステータスを更新しました', 'success');
        
        // カウンターを更新
        updateColumnCounts();
    })
    .catch(error => {
        console.error('ステータス更新エラー:', error);
        showToast('更新に失敗しました', 'error');
        
        // カードを元の位置に戻す
        location.reload();
    });
}

// 申請詳細モーダルを表示
function showApplicationDetail(applicationId) {
    const modal = new bootstrap.Modal(document.getElementById('detail-modal'));
    
    // HTMXでモーダル内容を読み込み
    htmx.ajax('GET', `/applications/${applicationId}/detail/`, {
        target: '#modal-content',
        swap: 'innerHTML'
    }).then(() => {
        modal.show();
    });
}

// 新規申請モーダルを表示
function showNewApplicationModal() {
    const modal = new bootstrap.Modal(document.getElementById('newApplicationModal'));
    modal.show();
}

// カラムのカード数を更新
function updateColumnCounts() {
    const columns = ['pending', 'approved', 'rejected'];
    
    columns.forEach(status => {
        const column = document.getElementById(`${status}-column`);
        const cards = column.querySelectorAll('.application-card');
        const header = column.parentElement.querySelector('.kanban-header h5');
        
        // ヘッダーのテキストを更新
        const iconClass = header.querySelector('i').className;
        const baseText = header.textContent.replace(/\(\d+\)/, '');
        header.innerHTML = `<i class="${iconClass}"></i> ${baseText.trim()} (${cards.length})`;
    });
}

// CSRFトークンを取得
function getCSRFToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') {
            return value;
        }
    }
    
    // Metaタグからも試行
    const csrfMeta = document.querySelector('[name=csrfmiddlewaretoken]');
    return csrfMeta ? csrfMeta.value : '';
}

// トースト通知を表示
function showToast(message, type = 'info') {
    // Bootstrap toast の実装
    const toastContainer = getOrCreateToastContainer();
    
    const toastElement = document.createElement('div');
    toastElement.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'} border-0`;
    toastElement.setAttribute('role', 'alert');
    toastElement.setAttribute('aria-live', 'assertive');
    toastElement.setAttribute('aria-atomic', 'true');
    
    toastElement.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi bi-${type === 'error' ? 'exclamation-triangle' : type === 'success' ? 'check-circle' : 'info-circle'}"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    toastContainer.appendChild(toastElement);
    
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: 3000
    });
    toast.show();
    
    // トーストが閉じられたら要素を削除
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

// トーストコンテナを取得または作成
function getOrCreateToastContainer() {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1055';
        document.body.appendChild(container);
    }
    return container;
}

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    // カード数の初期更新
    updateColumnCounts();
    
    // 定期的に更新をチェック（オプション）
    // setInterval(checkForUpdates, 30000); // 30秒ごと
});

// キーボードショートカット
document.addEventListener('keydown', function(e) {
    // Ctrl+N で新規申請モーダル
    if (e.ctrlKey && e.key === 'n') {
        e.preventDefault();
        showNewApplicationModal();
    }
    
    // Escキーでモーダルを閉じる
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal.show');
        modals.forEach(modal => {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) bsModal.hide();
        });
    }
});
