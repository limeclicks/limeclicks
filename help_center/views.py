from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def help_center_view(request):
    context = {
        'page_title': 'Help Center',
    }
    return render(request, 'help_center/index.html', context)
