from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import transaction
from django.db import models
import os
from .models import Application, ApprovalStatus, ApplicationFile
from .serializers import ApplicationSerializer, ApplicationCreateSerializer, ApplicationStatusUpdateSerializer
from .forms import ApplicationCreateForm, ApplicationFilterForm
from audit.models import AuditLog
from . import state_machine
from .state_machine import broadcast_application_state


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
                models.Q(applicant=user.username) | models.Q(approver=user.username)
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
        application = serializer.save(applicant=self.request.user.username)
        # 監査ログ
        AuditLog.objects.create(
            user=self.request.user,
            application=application,
            action="create",
            details=f"申請を作成しました。ファイル: {application.original_filename}"
        )
        # 初期状態通知 (Long Polling 用 no-op フック)
        broadcast_application_state(application)
    
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_status(self, request, pk=None):
        """申請ステータス更新"""
        application = self.get_object()
        # 権限チェック
        if application.approver != request.user.username:
            return Response({'error': 'この申請を承認する権限がありません。'}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(application, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        new_status = serializer.validated_data.get('status', application.status)
        try:
            state_machine.change_status(
                application,
                new_status,
                request.user,
                comment=serializer.validated_data.get('approval_comment')
            )
        except state_machine.InvalidTransition as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        refreshed = Application.objects.get(pk=application.pk)
        return Response(ApplicationSerializer(refreshed).data)


class MyApplicationListView(generics.ListAPIView):
    """自分の申請一覧"""
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Application.objects.filter(applicant=self.request.user.username)


# Django Template Views (新規追加)

@login_required
def application_detail_modal(request, pk):
    """申請詳細のモーダル表示（HTMX用）"""
    application = get_object_or_404(Application, pk=pk)
    
    if request.method == 'POST':
        # 状態更新処理
        new_status = request.POST.get('status')
        comment = request.POST.get('comment', '')

        if application.approver != request.user.username and not request.user.is_staff:
            messages.error(request, '権限がありません')
            return redirect('applications:default-view')

        try:
            state_machine.change_status(application, new_status, request.user, comment=comment)
            if new_status == ApprovalStatus.APPROVED:
                messages.success(request, f'申請 #{application.id} を承認しました。')
            elif new_status == ApprovalStatus.REJECTED:
                messages.success(request, f'申請 #{application.id} を却下しました。')
            return redirect('applications:default-view')
        except state_machine.InvalidTransition as e:
            messages.error(request, str(e))
            return redirect('applications:default-view')
    
    return render(request, 'applications/application_detail_modal.html', {
        'application': application,
        'approval_choices': ApprovalStatus.choices,
    })


@login_required
def create_application(request):
    """申請作成ページ"""
    if request.method == 'POST':
        form = ApplicationCreateForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    application = form.save()
                    
                    # 複数ファイルの保存
                    files = request.FILES.getlist('attachments')
                    for file in files:
                        ApplicationFile.objects.create(
                            application=application,
                            file=file,
                            original_filename=file.name,
                            file_size=file.size,
                            content_type=getattr(file, 'content_type', 'application/octet-stream')
                        )
                    
                    # 持出先所属の保存（多対多関係のため、フォーム保存後に設定）
                    if form.cleaned_data.get('carry_out_destinations'):
                        application.carry_out_destinations.set(form.cleaned_data['carry_out_destinations'])
                    
                    # 監査ログを記録
                    file_names = [f.name for f in files] if files else []
                    destinations = [dest.name for dest in application.carry_out_destinations.all()]
                    details = f"申請を作成しました。ファイル数: {len(file_names)}, ファイル: {', '.join(file_names)}"
                    if destinations:
                        details += f", 持出先所属: {', '.join(destinations)}"
                    
                    AuditLog.objects.create(
                        user=request.user,
                        application=application,
                        action="create",
                        details=details
                    )
                    
                    # 通知は post_save シグナルで処理（ここでは重複送信しない）
                    
                    messages.success(request, '申請が正常に作成されました。')
                    return redirect('applications:default-view')
                    
            except Exception as e:
                messages.error(request, f'申請の作成中にエラーが発生しました: {str(e)}')
    else:
        form = ApplicationCreateForm(user=request.user)
    # 同一OU階層の承認者候補を取得
    from users.utils import get_approvers_for_user
    approver_candidates = []
    if request.user.is_authenticated:
        approver_candidates = get_approvers_for_user(request.user) or []
    # 自分自身は除外
    approver_candidates = [a for a in approver_candidates if a.get('username') != request.user.username]

    # JSONシリアライズ可能な形だけに整理（念のため）
    safe_candidates = [
        {
            'username': c.get('username') or '',
            'display_name': c.get('display_name') or c.get('username') or '',
            'email': c.get('email') or '',
            'ou': c.get('ou') or ''
        } for c in approver_candidates
    ]

    return render(request, 'applications/create_application.html', {
        'form': form,
        'title': '新規申請作成',
        'approver_candidates': safe_candidates
    })


@login_required
def admin_application_list(request):
    """管理者向け全申請一覧"""
    # 管理者権限チェック
    if not request.user.is_staff:
        messages.error(request, '管理者権限が必要です。')
        return redirect('applications:default-view')
    
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
def my_applications_list(request):
    """自分の申請一覧（申請者として）"""
    from django.db.models import Q
    from .forms import ApplicationFilterForm
    
    # 基本クエリ
    applications = Application.objects.filter(applicant=request.user.username)
    
    # 検索フォームの処理
    filter_form = ApplicationFilterForm(request.GET)
    search_query = request.GET.get('search', '').strip()
    
    if search_query:
        # 検索条件を適用
        applications = applications.filter(
            Q(applicant__icontains=search_query) |
            Q(approver__icontains=search_query) |
            Q(comment__icontains=search_query) |
            Q(files__original_filename__icontains=search_query)
        ).distinct()
    
    # 並び順
    applications = applications.order_by('-created_at')
    
    # ページネーション
    from django.core.paginator import Paginator
    paginator = Paginator(applications, 20)
    page_number = request.GET.get('page')
    applications = paginator.get_page(page_number)
    
    context = {
        'applications': applications,
        'filter_form': filter_form,
        'search_query': search_query,
        'title': '自分の申請一覧',
        'is_applicant_view': True,
    }
    
    return render(request, 'applications/application_list.html', context)


@login_required
def approval_list(request, status=None):
    """承認管理一覧（承認者として）"""
    from django.db.models import Q
    from .forms import ApplicationFilterForm
    
    # 基本クエリ
    applications = Application.objects.filter(approver=request.user.username)
    
    # 状態フィルター（URLパラメータまたはGETパラメータ）
    status_filter = status or request.GET.get('status', '').strip()
    if status_filter:
        applications = applications.filter(status=status_filter)
    
    # 検索フォームの処理
    filter_form = ApplicationFilterForm(request.GET)
    search_query = request.GET.get('search', '').strip()
    
    if search_query:
        # 検索条件を適用
        applications = applications.filter(
            Q(applicant__icontains=search_query) |
            Q(approver__icontains=search_query) |
            Q(comment__icontains=search_query) |
            Q(files__original_filename__icontains=search_query)
        ).distinct()
    
    # 並び順
    applications = applications.order_by('-created_at')
    
    # ページネーション
    from django.core.paginator import Paginator
    paginator = Paginator(applications, 20)
    page_number = request.GET.get('page')
    applications = paginator.get_page(page_number)
    
    # タイトルを状態に応じて変更
    if status_filter == ApprovalStatus.PENDING:
        title = '承認待ち申請'
    else:
        title = '承認管理一覧'
    
    context = {
        'applications': applications,
        'filter_form': filter_form,
        'search_query': search_query,
        'status_filter': status_filter,
        'approval_status_choices': ApprovalStatus.choices,
        'title': title,
        'is_approval_view': True,
    }
    
    return render(request, 'applications/approval_list.html', context)


@login_required
def my_approval_history(request):
    """承認履歴（承認者として）"""
    from django.db.models import Q
    from .forms import ApplicationFilterForm
    
    # 基本クエリ
    applications = Application.objects.filter(approver=request.user.username).exclude(status=ApprovalStatus.PENDING)
    
    # 検索フォームの処理
    filter_form = ApplicationFilterForm(request.GET)
    search_query = request.GET.get('search', '').strip()
    
    if search_query:
        # 検索条件を適用
        applications = applications.filter(
            Q(applicant__icontains=search_query) |
            Q(approver__icontains=search_query) |
            Q(comment__icontains=search_query) |
            Q(files__original_filename__icontains=search_query)
        ).distinct()
    
    # 並び順
    applications = applications.order_by('-updated_at')
    
    # ページネーション
    from django.core.paginator import Paginator
    paginator = Paginator(applications, 20)
    page_number = request.GET.get('page')
    applications = paginator.get_page(page_number)
    
    context = {
        'applications': applications,
        'filter_form': filter_form,
        'search_query': search_query,
        'title': '承認履歴',
        'is_approval_view': True,
    }
    
    return render(request, 'applications/approval_list.html', context)


@login_required
def default_view(request):
    """デフォルト表示 - ユーザーのロールに応じて適切な一覧にリダイレクト"""
    # 承認者として何かの申請を持っている場合は承認一覧を表示
    has_approvals = Application.objects.filter(approver=request.user.username).exists()
    # 申請者として何かの申請を持っている場合は申請一覧を表示
    has_applications = Application.objects.filter(applicant=request.user.username).exists()
    
    # URLパラメータで表示モードを指定できるようにする
    view_mode = request.GET.get('view', None)
    
    if view_mode == 'approval' or (has_approvals and not has_applications):
        return redirect('applications:approval-list')
    else:
        return redirect('applications:my-applications-list')


@login_required
@require_POST
def mark_file_reviewed(request):
    """ファイル確認済みマーク"""
    try:
        application_id = request.POST.get('application_id')
        file_id = request.POST.get('file_id')
        
        application = get_object_or_404(Application, id=application_id)
        
        # 承認者権限チェック
        if application.approver != request.user.username:
            return JsonResponse({'error': '権限がありません'}, status=403)
        
        # ファイル確認状況を記録
        from applications.models import FileReviewStatus, ApplicationFile
        
        if file_id:
            app_file = get_object_or_404(ApplicationFile, id=file_id, application=application)
            review, created = FileReviewStatus.objects.get_or_create(
                application=application,
                file=app_file,
                approver=request.user.username
            )
        else:
            # 旧形式のファイルの場合
            review, created = FileReviewStatus.objects.get_or_create(
                application=application,
                file=None,
                approver=request.user.username
            )
        
        return JsonResponse({
            'success': True,
            'reviewed': True,
            'all_files_reviewed': application.get_all_files_reviewed_by(request.user.username)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def open_file(request, application_id, file_id=None):
    """ファイルを開く（ダウンロード）"""
    application = get_object_or_404(Application, id=application_id)
    
    # アクセス権限チェック
    if not (application.applicant == request.user.username or 
            application.approver == request.user.username or 
            request.user.is_staff):
        messages.error(request, 'アクセス権限がありません')
        return redirect('applications:my-applications-list')
    
    try:
        if file_id:
            # 新形式のファイル
            from applications.models import ApplicationFile
            app_file = get_object_or_404(ApplicationFile, id=file_id, application=application)
            file_path = app_file.file.path
            filename = app_file.original_filename
            content_type = app_file.content_type
        else:
            # 旧形式のファイル
            if not application.file:
                messages.error(request, 'ファイルが見つかりません')
                return redirect('applications:my-applications-list')
            
            file_path = application.file.path
            filename = application.original_filename
            content_type = application.content_type
        
        # ファイルが存在するかチェック
        if not os.path.exists(file_path):
            messages.error(request, 'ファイルが見つかりません')
            return redirect('applications:my-applications-list')
        
        # ファイルレスポンスを返す
        from django.http import FileResponse
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=content_type,
            as_attachment=True,
            filename=filename
        )
        
        return response
        
    except Exception as e:
        messages.error(request, f'ファイルの読み込み中にエラーが発生しました: {str(e)}')
        return redirect('applications:my-applications-list')
