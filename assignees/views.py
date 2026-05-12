from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from .models import Assignee


@login_required
def search(request):
    q = request.GET.get("q", "").strip()
    results = []
    if len(q) >= 2:
        qs = (
            Assignee.objects.filter(is_active=True)
            .filter(
                Q(employee__name_en__icontains=q)
                | Q(employee__section_name_en__icontains=q)
                | Q(employee__office_name_en__icontains=q)
                | Q(mp__name_en__icontains=q)
                | Q(mp__constituency__icontains=q)
                | Q(office__name_en__icontains=q)
                | Q(location__name__icontains=q)
            )
            .select_related("employee", "mp", "office", "location__parent__parent")[:12]
        )
        results = list(qs)

    asset_pk = request.GET.get("asset_pk", "")
    return render(request, "assignees/search_results.html", {
        "results": results,
        "q": q,
        "asset_pk": asset_pk,
    })


@login_required
def select_card(request, pk):
    assignee = get_object_or_404(Assignee, pk=pk)
    asset_pk = request.GET.get("asset_pk", "")
    return render(request, "assignees/selected_card.html", {
        "assignee": assignee,
        "asset_pk": asset_pk,
    })
