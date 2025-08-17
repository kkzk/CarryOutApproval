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
    if (window.USE_KANBAN_POLLING === true) {
        console.log('[Kanban] WebSocket 初期化スキップ (ロングポーリングモード)');
        return;
    }
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
    if (data.type === 'kanban_update') {
        // 重複イベント防止: 同一 (action, application.id) を直近1.5秒以内に処理済みならスキップ
        if (!window.__kanbanEventCache) {
            window.__kanbanEventCache = new Map();
        }
        try {
            const key = data.action + ':' + (data.application && data.application.id);
            const now = Date.now();
            // 期限切れ掃除 (最大50件)
            if (window.__kanbanEventCache.size > 80) {
                for (const [k, v] of window.__kanbanEventCache.entries()) {
                    if (now - v > 3000) window.__kanbanEventCache.delete(k);
                }
            }
            const last = window.__kanbanEventCache.get(key);
            if (last && (now - last) < 5000) {
                console.debug('Duplicate kanban_update skipped', key);
                return;
            }
            window.__kanbanEventCache.set(key, now);
        } catch (e) {
            console.warn('kanban_update dedupe error', e);
        }
        handleKanbanUpdate(data);
    }
}

// カンバンボード更新の処理
function handleKanbanUpdate(data) {
    // 統一後: action は常に application_state
    const { application } = data;
    if (!application) return;
    const status = application.status; // pending / approved / rejected
    const cardExistsInTarget = isCardInColumn(application.id, status);
    const cardExistsAnywhere = document.querySelector(`.application-card[data-id="${application.id}"]`) !== null;

    // 新規 (カードがどのカラムにも無く status=pending)
    if (!cardExistsAnywhere && status === 'pending') {
        addApplicationCard(application, 'pending');
        showToast(`新しい申請「${application.original_filename}」が追加されました`, 'info');
    } else if (status === 'approved' && !cardExistsInTarget) {
        moveApplicationCard(application.id, 'approved');
        showToast(`申請「${application.original_filename}」が承認されました`, 'success');
    } else if (status === 'rejected' && !cardExistsInTarget) {
        moveApplicationCard(application.id, 'rejected');
        showToast(`申請「${application.original_filename}」が却下されました`, 'warning');
    } else if (status === 'pending' && !isCardInColumn(application.id, 'pending')) {
        // 差し戻し (approved/rejected -> pending)
        moveApplicationCard(application.id, 'pending');
        showToast(`申請「${application.original_filename}」が差し戻されました`, 'info');
    } else {
        console.debug('application_state (no-op)', { id: application.id, status });
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

// 承認/却下時のモーダルは廃止しトーストのみ使用

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
                // 追加完了後にカウント更新
                updateColumnCounts();
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
    // 移動後にカウントを更新
    updateColumnCounts();
    // 念のため遅延再計算 (アニメ/再描画後)
    setTimeout(updateColumnCounts, 200);
    }, 150);
}

// 指定IDのカードが特定ステータスカラム内に存在するか
function isCardInColumn(applicationId, status) {
    const column = document.getElementById(`${status}-column`);
    if (!column) return false;
    return !!column.querySelector(`.application-card[data-id="${applicationId}"]`);
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
    const statuses = ['pending', 'approved', 'rejected'];
    statuses.forEach(status => {
        const column = document.getElementById(`${status}-column`);
        if (!column) return;
        const cards = column.querySelectorAll('.application-card');
        let headerWrapper = column.previousElementSibling;
        if (!(headerWrapper && headerWrapper.classList.contains('kanban-header'))) {
            headerWrapper = column.parentElement.querySelector('.kanban-header');
        }
        if (!headerWrapper) return;
        const header = headerWrapper.querySelector('h5');
        if (!header) return;
        const iconElem = header.querySelector('i');
        const iconClass = iconElem ? iconElem.className : 'bi bi-kanban';
        const raw = header.textContent || '';
        // 全角（ ）と半角() の両方を削除
        const base = raw
            .replace(/（\d+）/g, '')
            .replace(/\(\d+\)/g, '')
            .trim();
        header.innerHTML = `<i class="${iconClass}"></i> ${base} (${cards.length})`;
        console.debug('updateColumnCounts:', { status, count: cards.length, base, raw });
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

// ===== 後方互換スタブ =====
// 旧コードで利用されていた showApprovalNotification / showRejectionNotification
// がテンプレートやキャッシュに残っていてもエラーにならないようトースト呼び出しへ委譲
if (typeof window.showApprovalNotification === 'undefined') {
    window.showApprovalNotification = function(application) {
        if (!application) return;
        showToast(`申請「${application.original_filename || ''}」が承認されました`, 'success');
    };
}
if (typeof window.showRejectionNotification === 'undefined') {
    window.showRejectionNotification = function(application) {
        if (!application) return;
        showToast(`申請「${application.original_filename || ''}」が却下されました`, 'warning');
    };
}
if (typeof window.showNewApplicationNotification === 'undefined') {
    window.showNewApplicationNotification = function(application) {
        if (!application) return;
        showToast(`新しい申請「${application.original_filename || ''}」が追加されました`, 'info');
    };
}

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    // カード数の初期更新
    updateColumnCounts();
    // 初期化後に再度 count を安定化 (遅延挿入カードがある場合)
    setTimeout(updateColumnCounts, 300);
    
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

// ===== ロングポーリング (段階的移行) =====
(function(){
    let pollingActive = false;
    let since = null; // ISO8601 (Z)
    let stopped = false;

    function loop(){
        if (!pollingActive || stopped) return;
        const url = new URL('/notifications/poll/kanban/', window.location.origin);
        if (since) url.searchParams.set('since', since);
        fetch(url.toString(), { credentials: 'include' })
            .then(r => r.ok ? r.json() : Promise.reject(r.status))
            .then(data => {
                if (data && Array.isArray(data.applications)) {
                    data.applications.forEach(app => handleKanbanUpdate({ application: app }));
                }
                if (data && data.latest) since = data.latest;
            })
            .catch(err => console.error('[Kanban] poll error', err))
            .finally(() => setTimeout(loop, 50));
    }

    function startKanbanPolling(){
        if (pollingActive) return;
        pollingActive = true;
        console.log('[Kanban] Long polling 開始');
        if (websocket) { try { websocket.close(); } catch(e) {} websocket = null; }
        loop();
    }

    function stopKanbanPolling(){
        pollingActive = false;
        console.log('[Kanban] Long polling 停止要求');
    }

    window.startKanbanPolling = startKanbanPolling;
    window.stopKanbanPolling = stopKanbanPolling;

    if (window.USE_KANBAN_POLLING === true) {
        startKanbanPolling();
    }

    window.addEventListener('beforeunload', () => { stopped = true; pollingActive = false; });
})();
