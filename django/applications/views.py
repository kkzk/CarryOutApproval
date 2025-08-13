from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction
from django.db import models
from django.template.loader import render_to_string
from django.utils import timezone
from .models import Application, ApprovalStatus
from .serializers import ApplicationSerializer, ApplicationCreateSerializer, ApplicationStatusUpdateSerializer
from .forms import ApplicationCreateForm, ApplicationFilterForm
from audit.models import AuditLog


class ApplicationViewSet(viewsets.ModelViewSet):
    """申請のViewSet"""
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """ユーザーに応じたクエリセットを返す"""
        user = self.request.user
        if user.is_staff:
            # 管理者は全ての申請を閲覧可能
            return Application.objects.all()
        else:
            # 一般ユーザーは自分の申請と自分が承認者の申請のみ
            return Application.objects.filter(
                models.Q(applicant=user) | models.Q(approver=user)
            ).distinct()
    
    def get_serializer_class(self):
        """アクションに応じたシリアライザーを返す"""
        if self.action == 'create':
            return ApplicationCreateSerializer
        elif self.action == 'update_status':
            return ApplicationStatusUpdateSerializer
        return ApplicationSerializer
    
    def perform_create(self, serializer):
        """申請作成時の処理"""
        application = serializer.save(applicant=self.request.user)
        
        # 監査ログを記録
        AuditLog.objects.create(
            user=self.request.user,
            application=application,
            action="create",
            details=f"申請を作成しました。ファイル: {application.original_filename}"
        )
        
        # 承認者に通知を送信
        from notifications.services import NotificationService
        NotificationService.notify_new_application(application)
    
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_status(self, request, pk=None):
        """申請ステータス更新"""
        application = self.get_object()
        
        # 承認権限チェック
        if application.approver != request.user:
            return Response(
                {'error': 'この申請を承認する権限がありません。'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(application, data=request.data, partial=True)
        if serializer.is_valid():
            with transaction.atomic():
                old_status = application.status
                serializer.save()
                
                # 通知サービスのインポート
                from notifications.services import NotificationService
                
                # 監査ログを記録
                if application.status == ApprovalStatus.APPROVED:
                    action = "approve"
                    details = f"申請を承認しました。コメント: {application.approval_comment or 'なし'}"
                    # 承認通知を送信
                    NotificationService.notify_application_approved(application)
                elif application.status == ApprovalStatus.REJECTED:
                    action = "reject"
                    details = f"申請を拒否しました。コメント: {application.approval_comment or 'なし'}"
                    # 却下通知を送信
                    NotificationService.notify_application_rejected(application)
                else:
                    action = "update_status"
                    details = f"ステータスを {old_status} から {application.status} に変更しました。"
                
                AuditLog.objects.create(
                    user=request.user,
                    application=application,
                    action=action,
                    details=details
                )
            
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MyApplicationListView(generics.ListAPIView):
    """自分の申請一覧"""
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Application.objects.filter(applicant=self.request.user)


class PendingApplicationListView(generics.ListAPIView):
    """承認待ち申請一覧"""
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Application.objects.filter(
            approver=self.request.user,
            status=ApprovalStatus.PENDING
        )


# Django Template Views (新規追加)

@login_required
@require_POST
def update_application_status(request):
    """申請のステータス更新（HTMX用）"""
    try:
        application_id = request.POST.get('application_id')
        new_status = request.POST.get('status')
        comment = request.POST.get('comment', '')
        
        application = get_object_or_404(Application, id=application_id)
        
        # 権限チェック
        if application.approver != request.user and not request.user.is_staff:
            return JsonResponse({'error': '権限がありません'}, status=403)
        
        old_status = application.status
        application.status = new_status
        
        if comment:
            application.approval_comment = comment
            
        if new_status == ApprovalStatus.APPROVED:
            application.approved_at = timezone.now()
            
        application.save()
        
        # 通知サービスのインポート
        from notifications.services import NotificationService
        
        # 通知を送信
        if new_status == ApprovalStatus.APPROVED:
            NotificationService.notify_application_approved(application)
        elif new_status == ApprovalStatus.REJECTED:
            NotificationService.notify_application_rejected(application)
        
        # 監査ログを記録
        AuditLog.objects.create(
            user=request.user,
            application=application,
            action=f"status_change_{new_status}",
            details=f"ステータスを {old_status} から {new_status} に変更。コメント: {comment or 'なし'}"
        )
        
        # 更新されたカードのHTMLを返す
        card_html = render_to_string('applications/application_card.html', {
            'application': application
        }, request=request)
        
        return HttpResponse(card_html)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def application_detail_modal(request, pk):
    """申請詳細のモーダル表示（HTMX用）"""
    application = get_object_or_404(Application, pk=pk)
    
    return render(request, 'applications/application_detail_modal.html', {
        'application': application,
        'approval_choices': ApprovalStatus.choices,
    })


@login_required
def application_card(request, pk):
    """申請カード取得（リアルタイム更新用）"""
    application = get_object_or_404(Application, pk=pk)
    
    # アクセス権限チェック
    if not (application.applicant == request.user or 
            application.approver == request.user or 
            request.user.is_staff):
        return JsonResponse({'error': 'アクセス権限がありません'}, status=403)
    
    # カードHTMLを返す
    card_html = render_to_string('applications/application_card.html', {
        'application': application
    }, request=request)
    
    return HttpResponse(card_html, content_type='text/html')


@login_required
def create_application(request):
    """申請作成ページ"""
    if request.method == 'POST':
        form = ApplicationCreateForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    application = form.save()
                    
                    # 監査ログを記録
                    AuditLog.objects.create(
                        user=request.user,
                        application=application,
                        action="create",
                        details=f"申請を作成しました。ファイル: {application.original_filename}"
                    )
                    
                    # 承認者に通知を送信
                    from notifications.services import NotificationService
                    NotificationService.notify_new_application(application)
                    
                    messages.success(request, '申請が正常に作成されました。')
                    return redirect('applications:kanban-board')
                    
            except Exception as e:
                messages.error(request, f'申請の作成中にエラーが発生しました: {str(e)}')
    else:
        form = ApplicationCreateForm(user=request.user)
    
    return render(request, 'applications/create_application.html', {
        'form': form,
        'title': '新規申請作成'
    })


@login_required
def application_list(request):
    """申請一覧ページ（テーブル表示） - 一般ユーザー用"""
    # フィルタフォーム
    filter_form = ApplicationFilterForm(request.GET, user=request.user)
    
    # ベースクエリセット - 自分の申請と自分が承認者の申請のみ
    queryset = Application.objects.filter(
        models.Q(applicant=request.user.username) | models.Q(approver=request.user.username)
    ).distinct().order_by('-created_at')
    
    # フィルタ適用
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            queryset = queryset.filter(status=filter_form.cleaned_data['status'])
        if filter_form.cleaned_data.get('applicant'):
            queryset = queryset.filter(applicant=filter_form.cleaned_data['applicant'])
        if filter_form.cleaned_data.get('approver'):
            queryset = queryset.filter(approver=filter_form.cleaned_data['approver'])
    
    # 承認者としての表示かどうかを判定
    is_approval_view = queryset.filter(approver=request.user.username).exists()
    
    # ページネーション
    from django.core.paginator import Paginator
    paginator = Paginator(queryset, 20)  # 1ページあたり20件
    page_number = request.GET.get('page')
    applications = paginator.get_page(page_number)
    
    context = {
        'applications': applications,
        'filter_form': filter_form,
        'title': '関連申請一覧',
        'is_approval_view': is_approval_view,
    }
    
    return render(request, 'applications/application_list.html', context)


@login_required
def admin_application_list(request):
    """管理者向け全申請一覧"""
    # 管理者権限チェック
    if not request.user.is_staff:
        messages.error(request, '管理者権限が必要です。')
        return redirect('applications:kanban-board')
    
    # フィルタフォーム
    filter_form = ApplicationFilterForm(request.GET, user=request.user)
    
    # 全ての申請を取得
    queryset = Application.objects.all().order_by('-created_at')
    
    # フィルタ適用
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('status'):
            queryset = queryset.filter(status=filter_form.cleaned_data['status'])
        if filter_form.cleaned_data.get('applicant'):
            queryset = queryset.filter(applicant=filter_form.cleaned_data['applicant'])
        if filter_form.cleaned_data.get('approver'):
            queryset = queryset.filter(approver=filter_form.cleaned_data['approver'])
    
    # 統計情報を取得
    from django.db.models import Count
    stats = Application.objects.aggregate(
        total=Count('id'),
        pending=Count('id', filter=models.Q(status='pending')),
        approved=Count('id', filter=models.Q(status='approved')),
        rejected=Count('id', filter=models.Q(status='rejected'))
    )
    
    # ページネーション
    from django.core.paginator import Paginator
    paginator = Paginator(queryset, 20)  # 1ページあたり20件
    page_number = request.GET.get('page')
    applications = paginator.get_page(page_number)
    
    context = {
        'applications': applications,
        'filter_form': filter_form,
        'title': '全申請一覧（管理者）',
        'is_admin_view': True,
        'stats': stats,
    }
    
    return render(request, 'applications/admin_application_list.html', context)


@login_required
def my_applications(request):
    """自分の申請一覧"""
    applications = Application.objects.filter(
        applicant=request.user
    ).order_by('-created_at')
    
    # ページネーション
    from django.core.paginator import Paginator
    paginator = Paginator(applications, 20)
    page_number = request.GET.get('page')
    applications = paginator.get_page(page_number)
    
    context = {
        'applications': applications,
        'title': '自分の申請一覧'
    }
    
    return render(request, 'applications/my_applications.html', context)


@login_required
def my_applications_board(request):
    """自分の申請状況ボード（申請者として）"""
    applications = Application.objects.filter(
        applicant=request.user
    ).order_by('-created_at')
    
    # ステータスごとに分類
    pending_applications = applications.filter(status=ApprovalStatus.PENDING)
    approved_applications = applications.filter(status=ApprovalStatus.APPROVED)
    rejected_applications = applications.filter(status=ApprovalStatus.REJECTED)
    
    context = {
        'pending_applications': pending_applications,
        'approved_applications': approved_applications,
        'rejected_applications': rejected_applications,
        'approval_choices': ApprovalStatus.choices,
        'title': '申請状況ボード',
        'is_applicant_view': True,
    }
    
    return render(request, 'applications/applicant_kanban_board.html', context)


@login_required
def pending_approvals(request):
    """承認待ち申請一覧（承認者として）"""
    applications = Application.objects.filter(
        approver=request.user,
        status=ApprovalStatus.PENDING
    ).order_by('-created_at')
    
    # ページネーション
    from django.core.paginator import Paginator
    paginator = Paginator(applications, 20)
    page_number = request.GET.get('page')
    applications = paginator.get_page(page_number)
    
    context = {
        'applications': applications,
        'title': '承認待ち申請',
        'is_approval_view': True,
    }
    
    return render(request, 'applications/application_list.html', context)


@login_required
def approval_board(request):
    """承認管理ボード（承認者として）"""
    applications = Application.objects.filter(
        approver=request.user
    ).order_by('-created_at')
    
    # ステータスごとに分類
    pending_applications = applications.filter(status=ApprovalStatus.PENDING)
    approved_applications = applications.filter(status=ApprovalStatus.APPROVED)
    rejected_applications = applications.filter(status=ApprovalStatus.REJECTED)
    
    context = {
        'pending_applications': pending_applications,
        'approved_applications': approved_applications,
        'rejected_applications': rejected_applications,
        'approval_choices': ApprovalStatus.choices,
        'title': '承認管理ボード',
        'is_approval_view': True,
    }
    
    return render(request, 'applications/approver_kanban_board.html', context)


@login_required
def my_approval_history(request):
    """承認履歴（承認者として）"""
    applications = Application.objects.filter(
        approver=request.user
    ).exclude(status=ApprovalStatus.PENDING).order_by('-updated_at')
    
    # ページネーション
    from django.core.paginator import Paginator
    paginator = Paginator(applications, 20)
    page_number = request.GET.get('page')
    applications = paginator.get_page(page_number)
    
    context = {
        'applications': applications,
        'title': '承認履歴',
        'is_approval_view': True,
    }
    
    return render(request, 'applications/application_list.html', context)


@login_required
def kanban_board(request):
    """カンバンボード - ユーザーのロールに応じて適切なボードにリダイレクト"""
    # 承認者として何かの申請を持っている場合は承認ボードを表示
    has_approvals = Application.objects.filter(approver=request.user).exists()
    # 申請者として何かの申請を持っている場合は申請ボードを表示
    has_applications = Application.objects.filter(applicant=request.user).exists()
    
    # URLパラメータで表示モードを指定できるようにする
    view_mode = request.GET.get('view', None)
    
    if view_mode == 'approval' or (has_approvals and not has_applications):
        return redirect('applications:approval-board')
    else:
        return redirect('applications:my-applications-board')
