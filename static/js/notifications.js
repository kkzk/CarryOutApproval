class NotificationManager {
    constructor() {
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.pingInterval = null;
        this.notificationContainer = null;
        this.notificationBadge = null;
        this.unreadCount = 0;
        
        this.init();
    }
    
    init() {
        this.createNotificationElements();
        this.loadExistingNotifications();
        this.connect();
        this.setupEventListeners();
    }
    
    createNotificationElements() {
        // 通知バッジを作成
        this.notificationBadge = document.createElement('div');
        this.notificationBadge.id = 'notification-badge';
        this.notificationBadge.className = 'notification-badge hidden';
        this.notificationBadge.innerHTML = '<span class="count">0</span>';
        document.body.appendChild(this.notificationBadge);
        
        // 通知コンテナを作成
        this.notificationContainer = document.createElement('div');
        this.notificationContainer.id = 'notification-container';
        this.notificationContainer.className = 'notification-container';
        document.body.appendChild(this.notificationContainer);
        
        // CSS スタイルを追加
        this.addStyles();
    }
    
    addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .notification-badge {
                position: fixed;
                top: 20px;
                right: 20px;
                background: #dc3545;
                color: white;
                border-radius: 50%;
                width: 30px;
                height: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                font-weight: bold;
                z-index: 1000;
                cursor: pointer;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            }
            
            .notification-badge.hidden {
                display: none;
            }
            
            .notification-container {
                position: fixed;
                top: 60px;
                right: 20px;
                max-width: 350px;
                z-index: 999;
            }
            
            .notification-item {
                background: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                animation: slideIn 0.3s ease-out;
                cursor: pointer;
                position: relative;
            }
            
            .notification-item.unread {
                border-left: 4px solid #007bff;
                background: #f8f9fa;
            }
            
            .notification-item .title {
                font-weight: bold;
                margin-bottom: 5px;
                color: #333;
            }
            
            .notification-item .message {
                color: #666;
                font-size: 14px;
                margin-bottom: 8px;
            }
            
            .notification-item .time {
                color: #999;
                font-size: 12px;
            }
            
            .notification-item .close-btn {
                position: absolute;
                top: 5px;
                right: 10px;
                background: none;
                border: none;
                font-size: 18px;
                color: #999;
                cursor: pointer;
                line-height: 1;
            }
            
            .notification-item .close-btn:hover {
                color: #666;
            }
            
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            
            .notification-sound {
                display: none;
            }
        `;
        document.head.appendChild(style);
        
        // 通知音用のaudio要素を追加
        const audio = document.createElement('audio');
        audio.className = 'notification-sound';
        audio.preload = 'auto';
        // データURIで簡単な通知音を作成（実際の実装では適切な音声ファイルを使用）
        audio.innerHTML = '<source src="data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmUYCD2W2e/JdSIFKn3M7+GNPQQYZF2+4R8=" type="audio/wav">'; 
        document.body.appendChild(audio);
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const wsUrl = `${protocol}://${window.location.host}/ws/notifications/`;
        
        try {
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = (event) => {
                console.log('通知WebSocket接続成功');
                this.reconnectAttempts = 0;
                this.startPing();
            };
            
            this.websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };
            
            this.websocket.onclose = (event) => {
                console.log('通知WebSocket切断');
                this.stopPing();
                this.reconnect();
            };
            
            this.websocket.onerror = (error) => {
                console.error('通知WebSocketエラー:', error);
            };
            
        } catch (error) {
            console.error('WebSocket接続エラー:', error);
            this.reconnect();
        }
    }
    
    reconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
            
            setTimeout(() => {
                console.log(`WebSocket再接続試行 ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
                this.connect();
            }, delay);
        } else {
            console.error('WebSocket再接続試行回数上限に達しました');
        }
    }
    
    startPing() {
        this.pingInterval = setInterval(() => {
            if (this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({type: 'ping'}));
            }
        }, 30000); // 30秒ごとにping
    }
    
    stopPing() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'notification':
                this.displayNotification(data.data);
                break;
            case 'pong':
                // ping応答を受信
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    displayNotification(notification) {
        // 通知を表示
        this.showNotificationItem(notification);
        
        // 未読カウントを更新
        this.updateUnreadCount();
        
        // 通知音を再生
        this.playNotificationSound();
        
        // ブラウザ通知を表示（許可されている場合）
        this.showBrowserNotification(notification);
    }
    
    showNotificationItem(notification) {
        const notificationItem = document.createElement('div');
        notificationItem.className = 'notification-item unread';
        notificationItem.dataset.notificationId = notification.id;
        
        notificationItem.innerHTML = `
            <button class="close-btn" onclick="notificationManager.removeNotification(${notification.id})">&times;</button>
            <div class="title">${this.escapeHtml(notification.title)}</div>
            <div class="message">${this.escapeHtml(notification.message)}</div>
            <div class="time">${notification.time_ago}</div>
        `;
        
        // クリックで既読にする
        notificationItem.addEventListener('click', () => {
            this.markAsRead(notification.id);
        });
        
        this.notificationContainer.insertBefore(notificationItem, this.notificationContainer.firstChild);
        
        // 自動で削除（10秒後）
        setTimeout(() => {
            this.removeNotification(notification.id);
        }, 10000);
    }
    
    markAsRead(notificationId) {
        // サーバーに既読リクエストを送信
        fetch(`/api/notifications/${notificationId}/read/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken(),
            },
        }).then(response => {
            if (response.ok) {
                // UIから削除
                this.removeNotification(notificationId);
            }
        }).catch(error => {
            console.error('既読マークエラー:', error);
        });
        
        // WebSocketでも通知
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'mark_read',
                notification_id: notificationId
            }));
        }
    }
    
    removeNotification(notificationId) {
        const item = document.querySelector(`[data-notification-id="${notificationId}"]`);
        if (item) {
            item.remove();
            this.updateUnreadCount();
        }
    }
    
    updateUnreadCount() {
        const unreadItems = this.notificationContainer.querySelectorAll('.notification-item.unread');
        this.unreadCount = unreadItems.length;
        
        if (this.unreadCount > 0) {
            this.notificationBadge.querySelector('.count').textContent = this.unreadCount;
            this.notificationBadge.classList.remove('hidden');
        } else {
            this.notificationBadge.classList.add('hidden');
        }
    }
    
    playNotificationSound() {
        const audio = document.querySelector('.notification-sound');
        if (audio) {
            audio.play().catch(error => {
                console.log('通知音再生エラー:', error);
            });
        }
    }
    
    showBrowserNotification(notification) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(notification.title, {
                body: notification.message,
                icon: '/static/img/notification-icon.png'
            });
        }
    }
    
    requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    console.log('ブラウザ通知が許可されました');
                }
            });
        }
    }
    
    loadExistingNotifications() {
        // ページ読み込み時に未読通知を取得
        fetch('/api/notifications/unread/')
            .then(response => response.json())
            .then(data => {
                if (data.results) {
                    data.results.forEach(notification => {
                        this.showNotificationItem(notification);
                    });
                    this.updateUnreadCount();
                }
            })
            .catch(error => {
                console.error('通知取得エラー:', error);
            });
    }
    
    setupEventListeners() {
        // 通知バッジクリックで全通知を既読に
        this.notificationBadge.addEventListener('click', () => {
            this.markAllAsRead();
        });
        
        // ページ読み込み時にブラウザ通知許可をリクエスト
        this.requestNotificationPermission();
    }
    
    markAllAsRead() {
        fetch('/api/notifications/mark-all-read/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken(),
            },
        }).then(response => {
            if (response.ok) {
                // 全ての通知アイテムを削除
                const items = this.notificationContainer.querySelectorAll('.notification-item');
                items.forEach(item => item.remove());
                this.updateUnreadCount();
            }
        }).catch(error => {
            console.error('全既読マークエラー:', error);
        });
    }
    
    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// グローバルに通知マネージャーのインスタンスを作成
let notificationManager;

// DOM読み込み完了後に初期化
document.addEventListener('DOMContentLoaded', function() {
    notificationManager = new NotificationManager();
});

// ページ離脱時にWebSocket接続を閉じる
window.addEventListener('beforeunload', function() {
    if (notificationManager && notificationManager.websocket) {
        notificationManager.websocket.close();
    }
});
